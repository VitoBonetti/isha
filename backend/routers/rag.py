import os
import json
import asyncio
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import UUID4
from google import genai
from google.genai import types
from database import get_db_cursor, db_cursor_context
from routers.auth import require_admin
from utils.document_parser import extract_text_from_drive_file
from utils.secret_manager import get_secret
from audit_logger import log_audit_event
from schema import RagChatRequest, RagAIResponse

router = APIRouter(prefix="/api/rag", tags=["RAG Intelligence"])

# Initialize the Gemini Client
client = genai.Client(api_key=get_secret(os.environ.get("LUIGI_KEY_NAME")))


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Splits a large text block into smaller chunks of ~500 words."""
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


def extract_relevant_snippet(text: str, query: str, snippet_length: int = 200) -> str:
    """Finds the 200-character window in a chunk that best matches the user's query."""
    text = " ".join(text.split())
    if len(text) <= snippet_length:
        return text

    # Extract meaningful words from the query
    stop_words = {"can", "you", "the", "a", "is", "what", "how", "give", "me", "some", "about", "please", "for", "of",
                  "in", "to"}
    query_words = set(re.findall(r'\w+', query.lower())) - stop_words

    if not query_words:
        return text[:snippet_length] + "..."

    best_score = 0
    best_start = 0

    # Slide a 200-character window across the text, stepping by 50 characters
    for i in range(0, len(text) - snippet_length, 50):
        window_text = text[i:i + snippet_length]
        window_words = set(re.findall(r'\w+', window_text.lower()))

        # Score based on how many unique query words appear in this window
        score = len(query_words.intersection(window_words))

        if score > best_score:
            best_score = score
            best_start = i

    snippet = text[best_start:best_start + snippet_length]
    prefix = "..." if best_start > 0 else ""
    suffix = "..." if best_start + snippet_length < len(text) else ""

    return prefix + snippet.strip() + suffix


def process_test_documents_background(test_id: str, user_id: str, user_role: str):
    """Background task to extract, embed, and store document chunks."""
    with db_cursor_context() as cursor:
        try:
            # 1. Fetch all documents associated with this test
            cursor.execute("""
                SELECT id, drive_file_id, mime_type, file_name, doc_type 
                FROM test_documents 
                WHERE test_id = %s
            """, (test_id,))
            documents = cursor.fetchall()

            if not documents:
                log_audit_event(
                    user_id=str(user_id),
                    role=str(user_role),
                    action="RAG_SYNC_SKIPPED",
                    resource_type="RAG",
                    resource_id=str(test_id),
                    details="No documents found in the database for this test to index."
                )
                return

            # 2. Wipe existing chunks for this test to prevent duplicates on resync
            cursor.execute("DELETE FROM document_chunks WHERE test_id = %s", (test_id,))

            for doc in documents:
                doc_id, drive_file_id, mime_type, file_name, doc_type = doc
                chunks = []

                # Handle Virtual LLM_ANALYSIS (Stored in Postgres) vs Drive Files
                if doc_type == 'LLM_ANALYSIS' or drive_file_id.startswith("analysis_"):
                    cursor.execute("SELECT analysis_text FROM test_analyses WHERE test_id = %s", (test_id,))
                    analysis_row = cursor.fetchone()
                    raw_text = analysis_row[0] if analysis_row and analysis_row[0] else ""

                    if not raw_text.strip():
                        continue

                    # Split strictly by the Markdown separator so each chunk is exactly 1 complete vuln analysis
                    # We look for "---" which is what your Cloud Run stitching uses
                    raw_chunks = raw_text.split("\n\n---\n\n")
                    chunks = [c.strip() for c in raw_chunks if c.strip()]
                else:
                    # 3. Extract text from Google Drive
                    try:
                        raw_text = extract_text_from_drive_file(drive_file_id, mime_type)
                        log_audit_event(user_id=str(user_id), role=str(user_role), action="EXTRACT_TEXT_FROM_DOCUMENT",
                                        resource_type="RAG", resource_id=str(doc_id),
                                        details=f"Extract text from Google Drive Document: {file_name}")
                    except Exception as e:
                        log_audit_event(user_id=str(user_id), role=str(user_role),
                                        action="EXTRACT_TEXT_FROM_DOCUMENT_FAILED", resource_type="RAG",
                                        resource_id=str(doc_id), details=f"Failed to parse {file_name}: {e}")
                        continue

                    if not raw_text or not raw_text.strip():
                        continue

                    chunks = chunk_text(raw_text)
                    log_audit_event(user_id=str(user_id), role=str(user_role), action="CHUCK_TEXT", resource_type="RAG",
                                    resource_id=str(doc_id),
                                    details=f"Split into 500-word chunks Document: {file_name}")

                if not chunks:
                    continue

                # 4. Generate embeddings using Gemini API
                try:
                    response = client.models.embed_content(
                        model='gemini-embedding-2',
                        contents=chunks,
                        config=types.EmbedContentConfig(output_dimensionality=768)
                    )
                except Exception as e:
                    log_audit_event(user_id=str(user_id), role=str(user_role), action="GEMINI_MODEL_FAILED",
                                    resource_type="RAG", resource_id=str(doc_id),
                                    details=f"Generate embeddings using Gemini API failed for test {doc_id}: {str(e)}")
                    continue

                # 5. Insert chunks and their vectors into the database
                for index, (chunk_text_content, embedding_obj) in enumerate(zip(chunks, response.embeddings)):
                    vector_str = json.dumps(embedding_obj.values)
                    cursor.execute("""
                        INSERT INTO document_chunks (id, document_id, test_id, chunk_index, text_content, embedding, created_at)
                        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s::vector, CURRENT_TIMESTAMP)
                    """, (doc_id, test_id, index, chunk_text_content, vector_str))

            cursor.connection.commit()
            log_audit_event(user_id=str(user_id), role=str(user_role), action="CHUNK_TEXT_EMBEDED", resource_type="RAG",
                            resource_id=str(test_id),
                            details=f"Generate embeddings using Gemini API Successful for test {test_id}")
        except Exception as e:
            cursor.connection.rollback()
            log_audit_event(user_id=str(user_id), role=str(user_role), action="RAG_SYNC_FAILED", resource_type="RAG",
                            resource_id=str(test_id), details=f"RAG Sync failed for test {test_id}: {str(e)}")


@router.get("/", summary="[Admin] Testing endpoint for check the chunck")
def check_chunks(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("""
    SELECT dc.id, td.file_name, t.name, dc.chunk_index, dc.text_content, dc.embedding::text, dc.created_at
    FROM document_chunks dc
    LEFT JOIN test_documents td ON dc.document_id = td.id
    LEFT JOIN tests t ON td.test_id = t.id

    """)
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/tests/{test_id}/sync", summary="[Admin] Sync test documents to AI Knowledge Base")
def sync_test_to_rag(
        test_id: UUID4,
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_admin)
):
    background_tasks.add_task(process_test_documents_background, str(test_id), str(current_user["id"]),
                              str(current_user["role"]))
    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SYNC_TEST_TO_RAG_STARTED",
        resource_type="RAG",
        resource_id=str(test_id),
        details=f"Test with ID: {test_id} sync with RAG started."
    )
    return {
        "message": "RAG synchronization started in the background. This may take a few minutes depending on document size."}


# --- GLOBAL SYNC WORKER ---
def sync_all_active_tests_background(user_id: str, user_role: str):
    with db_cursor_context() as cursor:
        cursor.execute("SELECT id FROM tests WHERE drive_folder_id IS NOT NULL")
        test_rows = cursor.fetchall()

    print(f"[{datetime.now(timezone.utc)}] Starting nightly RAG sync for {len(test_rows)} tests...")
    for (t_id,) in test_rows:
        try:
            process_test_documents_background(str(t_id), user_id, user_role)
        except Exception as e:
            log_audit_event(
                user_id=user_id,
                role=user_role,
                action="SYNC_ALL_TEST_TO_RAG_FAILED",
                resource_type="RAG",
                resource_id=str(t_id),
                details=f"Nightly sync failed for test {t_id}: {e}."
            )
    log_audit_event(
        user_id=user_id,
        role=user_role,
        action="SYNC_ALL_TEST_TO_RAG_COMPLETED",
        resource_type="RAG",
        resource_id="ALL TESTS",
        details=f"[{datetime.now(timezone.utc)}] Nightly RAG sync complete."
    )


@router.post("/sync-all", summary="[Admin] Manually trigger full system Drive sync")
def trigger_global_rag_sync(
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_admin)
):
    background_tasks.add_task(sync_all_active_tests_background, str(current_user["id"]), str(current_user["role"]))
    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SYNC_TEST_TO_RAG_STARTED",
        resource_type="RAG",
        resource_id="ALL TESTS",
        details=f"Global RAG sync initiated in the background."
    )
    return {"message": "Global RAG sync initiated in the background."}


# --- NIGHTLY SCHEDULER TASK ---
async def start_nightly_rag_scheduler():
    """Runs the sync_all worker once every 24 hours at 02:00 AM UTC."""
    while True:
        now = datetime.now(timezone.utc)
        # Calculate seconds until 02:00 AM UTC tomorrow
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target.replace(day=now.day + 1)

        sleep_seconds = (target - now).total_seconds()
        await asyncio.sleep(sleep_seconds)

        # Execute the sync
        sync_all_active_tests_background("SYSTEM", "SYSTEM")


# --- CHATS ---
@router.get("/filters", summary="Get autocomplete filters for RAG chat")
def get_rag_filters(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    filters = []

    # 1. Doc Types (Trigger: /)
    filters.extend([
        {"type": "doc_type", "id": "FULL_TEST_REPORT", "name": "Full-Test-Report", "trigger": "/"},
        {"type": "doc_type", "id": "LLM_ANALYSIS", "name": "LLM-Quality-Analysis", "trigger": "/"},
        {"type": "doc_type", "id": "VULN_REPORT", "name": "Vulnerability-Report", "trigger": "/"},
        {"type": "doc_type", "id": "PRESENTATION", "name": "Presentation", "trigger": "/"},
        {"type": "doc_type", "id": "MANUAL_UPLOAD", "name": "Manual-Upload", "trigger": "/"},
    ])

    # 2. Assets (Trigger: @)
    cursor.execute("""
        SELECT DISTINCT ra.id, ra.name
        FROM raw_assets ra
        JOIN assets a ON ra.id = a.raw_asset_id
        JOIN test_assets ta ON a.id = ta.asset_id
        JOIN tests t ON ta.test_id = t.id
        WHERE t.drive_folder_id IS NOT NULL
        ORDER BY ra.name ASC;
    """)
    for row in cursor.fetchall():
        name = row[1].replace(" ", "-")
        filters.append({"type": "asset", "id": str(row[0]), "name": name, "trigger": "@"})

    # 3. Tests (Trigger: $)
    cursor.execute("SELECT id, name FROM tests WHERE drive_folder_id IS NOT NULL ORDER BY name ASC")
    for row in cursor.fetchall():
        name = row[1].replace(" ", "-")
        filters.append({"type": "test", "id": str(row[0]), "name": name, "trigger": "$"})

    return filters


@router.get("/stats", summary="Get RAG knowledge base statistics")
def get_rag_stats(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Count unique documents currently indexed in the vector space
    cursor.execute("SELECT COUNT(DISTINCT document_id) FROM document_chunks")
    total = cursor.fetchone()[0]
    return {"total_sources": total or 0}


@router.post("/chat", summary="Query the RAG Knowledge Base (Streaming)")
def chat_with_documents(
        req: RagChatRequest,
        current_user: dict = Depends(require_admin)
):
    # 1. Embed the user's question
    try:
        query_response = client.models.embed_content(
            model='gemini-embedding-2',
            contents=req.query,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        query_vector = json.dumps(query_response.embeddings[0].values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to embed query: {str(e)}")

    # 2. Perform Vector Similarity Search
    with db_cursor_context() as cursor:
        query_sql = """
            SELECT dc.text_content, td.file_name, td.file_url, td.doc_type, 1 - (dc.embedding <=> %s::vector) as similarity, dc.test_id
            FROM document_chunks dc
            JOIN test_documents td ON dc.document_id = td.id
        """

        where_clauses = []
        params = [query_vector]

        # If filtering by asset, we must JOIN the test_assets table
        if req.asset_id:
            query_sql = """
                SELECT dc.text_content, td.file_name, td.file_url, td.doc_type, 1 - (dc.embedding <=> %s::vector) as similarity, dc.test_id
                FROM document_chunks dc
                JOIN test_documents td ON dc.document_id = td.id
                JOIN test_assets ta ON dc.test_id = ta.test_id
            """
            where_clauses.append("ta.asset_id = %s")
            params.append(str(req.asset_id))
        elif req.test_id:
            where_clauses.append("dc.test_id = %s")
            params.append(str(req.test_id))

        # Stack the document type filter if requested via '/'
        if req.doc_type:
            where_clauses.append("td.doc_type = %s")
            params.append(req.doc_type)

        # Append WHERE clauses dynamically
        if where_clauses:
            query_sql += " WHERE " + " AND ".join(where_clauses)

        # Finalize the order and limit
        query_sql += " ORDER BY dc.embedding <=> %s::vector LIMIT 30"
        params.append(query_vector)

        cursor.execute(query_sql, tuple(params))
        raw_results = cursor.fetchall()

        cursor.execute("""
            SELECT question, answer 
            FROM rag_chat_logs 
            WHERE session_id = %s 
            ORDER BY timestamp ASC LIMIT 10
        """, (str(req.session_id),))
        history_rows = cursor.fetchall()

    # 3. Apply Metadata De-duplication Rules
    has_full_report_for_test = set()
    for _, _, _, doc_type, similarity, t_id in raw_results:
        if similarity > 0.35 and doc_type == 'FULL_TEST_REPORT':
            has_full_report_for_test.add(t_id)

    filtered_results = []
    for text_content, file_name, file_url, doc_type, similarity, t_id in raw_results:
        if similarity <= 0.35:
            continue
        if doc_type == 'VULN_REPORT' and t_id in has_full_report_for_test:
            continue
        filtered_results.append((text_content, file_name, file_url, doc_type))

    # 4. Assemble Context & Map
    context_text = ""
    citations_map = {}  # Maps '1', '2', etc. to their data payload

    # Enumerate starting at 1 to give each chunk a clear ID
    for idx, (text_content, file_name, file_url, doc_type) in enumerate(filtered_results[:15], start=1):
        context_text += f"\n--- Source Document [{idx}]: [{doc_type}] {file_name} ---\n{text_content}\n"

        # USE THE SMART SNIPPET EXTRACTOR HERE
        snippet = extract_relevant_snippet(text_content, req.query, 200)

        citations_map[str(idx)] = {
            "id": idx,
            "file_name": file_name,
            "url": file_url,
            "snippet": snippet
        }

    if not context_text:
        context_text = "No relevant context documents were found in the database for this specific query."

    gemini_history = []
    for past_q, past_a in history_rows:
        gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=past_q)]))
        gemini_history.append(types.Content(role="model", parts=[types.Part.from_text(text=past_a)]))

    system_instruction = """
    Your name is Luigi. You are an expert cybersecurity assistant for the Global Offensive Security Team.
    Answer the user's question based strictly on the provided Context Documents and your previous conversation history.
    If the context does not contain the answer, politely state that you do not have that information.

    DOCUMENT TAXONOMY & ROUTING RULES:
    1. Documents tagged [FULL_TEST_REPORT] are the canonical source for overall pentest scope, vulnerability summaries, and official findings.
    2. Documents tagged [LLM_ANALYSIS] represent deep quality checks. ALWAYS prioritize [LLM_ANALYSIS] when answering questions about vulnerability quality, false positive status, or grades.

    CITATION INSTRUCTIONS:
    When using information from the context, you MUST append an inline citation directly after the relevant sentence. 
    Format the citation EXACTLY as a Markdown link pointing to '#cite-ID'.
    For example: "The vulnerability allows privilege escalation [[1]](#cite-1)."
    """

    config = types.GenerateContentConfig(
        system_instruction=system_instruction
    )

    # 5. Define the NDJSON Generator
    def event_generator():
        try:
            chat = client.chats.create(model='gemini-3.5-flash', history=gemini_history, config=config)
            prompt_with_context = f"Context Documents:\n{context_text}\n\nUser Question: {req.query}"

            response_stream = chat.send_message_stream(prompt_with_context)
            full_answer = ""
            for chunk in response_stream:
                if chunk.text:
                    full_answer += chunk.text
                    yield json.dumps({"text": chunk.text}) + "\n"

            # Evaluate which sources were actually mentioned (look for 'cite:X' in output)
            confirmed_citations = []
            for cite_id, cite_data in citations_map.items():
                if f"#cite-{cite_id}" in full_answer:
                    confirmed_citations.append(cite_data)
                    log_audit_event(user_id="LUIGI", role="LUIGI", action="CHECK_CITATIONS",
                                    resource_type="RAG", resource_id=str(cite_id),
                                    details=f"[RAG DEBUG] Confirmed Citation {cite_id}: {cite_data['file_name']}. Snippet: {cite_data['snippet']}")

            yield json.dumps({"citations": confirmed_citations}) + "\n"

            with db_cursor_context() as stream_cursor:
                stream_cursor.execute("""
                    INSERT INTO rag_chat_logs (id, session_id, user_id, test_id, asset_id, question, answer, timestamp)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    str(req.session_id), str(current_user["id"]),
                    str(req.test_id) if req.test_id else None, str(req.asset_id) if req.asset_id else None,
                    req.query, full_answer
                ))
                stream_cursor.connection.commit()

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.get('/rag_chat_logs', summary='{Admin only] Rag Chat Logs')
def rag_chat_logs(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute(
        "SELECT * FROM rag_chat_logs")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]