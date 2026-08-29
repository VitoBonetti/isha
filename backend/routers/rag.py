import os
import json
import asyncio
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
        if req.test_id:
            query_sql += " WHERE dc.test_id = %s ORDER BY dc.embedding <=> %s::vector LIMIT 30"
            cursor.execute(query_sql, (query_vector, str(req.test_id), query_vector))
        elif req.asset_id:
            query_sql += " JOIN test_assets ta ON dc.test_id = ta.test_id WHERE ta.asset_id = %s ORDER BY dc.embedding <=> %s::vector LIMIT 30"
            cursor.execute(query_sql, (query_vector, str(req.asset_id), query_vector))
        else:
            query_sql += " ORDER BY dc.embedding <=> %s::vector LIMIT 30"
            cursor.execute(query_sql, (query_vector, query_vector))

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
    source_url_map = {}
    for text_content, file_name, file_url, doc_type in filtered_results[:15]:
        context_text += f"\n--- Source Document: [{doc_type}] {file_name} ---\n{text_content}\n"
        source_url_map[file_name] = file_url

    if not context_text:
        context_text = "No relevant context documents were found in the database for this specific query."

    gemini_history = []
    for past_q, past_a in history_rows:
        gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=past_q)]))
        gemini_history.append(types.Content(role="model", parts=[types.Part.from_text(text=past_a)]))

    system_instruction = """
    You are an expert cybersecurity assistant for the Global Offensive Security Team.
    Answer the user's question based strictly on the provided Context Documents and your previous conversation history.
    If the context does not contain the answer, politely state that you do not have that information.

    DOCUMENT TAXONOMY & ROUTING RULES:
    1. Documents tagged [FULL_TEST_REPORT] are the canonical source for overall pentest scope, vulnerability summaries, and official findings.
    2. Documents tagged [LLM_ANALYSIS] represent deep quality checks. ALWAYS prioritize [LLM_ANALYSIS] when answering questions about vulnerability quality, false positive status, or grades.

    CITATION INSTRUCTIONS:
    When using information from the context, explicitly mention the document filename directly in your text (e.g., 'According to LLM_Vulnerability_Analysis.md...'). 
    """

    config = types.GenerateContentConfig(
        system_instruction=system_instruction
    )

    # 5. Define the NDJSON Generator
    def event_generator():
        try:
            chat = client.chats.create(
                model='gemini-3.5-flash',
                history=gemini_history,
                config=config
            )

            prompt_with_context = f"Context Documents:\n{context_text}\n\nUser Question: {req.query}"

            # Use send_message_stream instead of send_message
            response_stream = chat.send_message_stream(prompt_with_context)

            full_answer = ""
            for chunk in response_stream:
                if chunk.text:
                    full_answer += chunk.text
                    # Yield each text token as a JSON string
                    yield json.dumps({"text": chunk.text}) + "\n"

            # Evaluate which sources were actually mentioned in the final text
            confirmed_citations = []
            for file_name, file_url in source_url_map.items():
                if file_name in full_answer:
                    confirmed_citations.append({"file_name": file_name, "url": file_url})

            # Fallback: if it didn't explicitly cite inline but we provided context, attach the context sources
            if not confirmed_citations and source_url_map:
                for file_name, file_url in source_url_map.items():
                    confirmed_citations.append({"file_name": file_name, "url": file_url})

            # Yield the final citations payload
            yield json.dumps({"citations": confirmed_citations}) + "\n"

            # Open a new cursor inside the generator to save the finalized answer
            with db_cursor_context() as stream_cursor:
                stream_cursor.execute("""
                    INSERT INTO rag_chat_logs (id, session_id, user_id, test_id, asset_id, question, answer, timestamp)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    str(req.session_id),
                    str(current_user["id"]),
                    str(req.test_id) if req.test_id else None,
                    str(req.asset_id) if req.asset_id else None,
                    req.query,
                    full_answer
                ))
                stream_cursor.connection.commit()

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    # Return the stream with x-ndjson content type
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.get('/rag_chat_logs', summary='{Admin only] Rag Chat Logs')
def rag_chat_logs(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute(
        "SELECT * FROM rag_chat_logs")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]