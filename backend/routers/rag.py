import os
import json
import asyncio
import re
import uuid
import time
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
from utils.drive_manager import DriveManager
from utils.kiss24_service import get_test_vulns_info
from audit_logger import log_audit_event
from schema import RagChatRequest, RagAIResponse, RagChatBulkDeleteRequest, FeedbackRequest


router = APIRouter(prefix="/api/rag", tags=["RAG Intelligence"])

# Initialize the Gemini Client
client = genai.Client(api_key=get_secret(os.environ.get("LUIGI_KEY_NAME")))


def structure_aware_chunking(text: str, max_words: int = 500, overlap_words: int = 100) -> list[str]:
    """
    Splits documents based on semantic boundaries (Markdown headers, titles) rather than blind word counts.
    Massive sections are sub-chunked, but the section header is retained across all sub-chunks.
    """
    chunks = []

    # Split on Markdown headers (# to ######) or specific report keywords
    # (?m) enables multiline mode so ^ matches the start of any line
    pattern = r'(?m)(?=^(?:#{1,6}\s+|Title:\s*|Original finding\s*))'
    sections = [s.strip() for s in re.split(pattern, text) if s.strip()]

    if not sections:
        # Fallback if no structure is found
        sections = [text]

    for section in sections:
        words = section.split()
        if len(words) <= max_words:
            chunks.append(section)
        else:
            # Recursive overlap for massive sections, preserving the header context
            header = " ".join(words[:15])  # Extract the heading line
            step = max(1, max_words - overlap_words)
            for i in range(0, len(words), step):
                sub_chunk = " ".join(words[i:i + max_words])

                # If this is a subsequent sub-chunk, prepend the section header
                if i > 0 and not sub_chunk.startswith(header):
                    sub_chunk = f"[Section Context: {header}...]\n{sub_chunk}"

                chunks.append(sub_chunk)

    return chunks


def process_test_documents_background(test_id: str, user_id: str, user_role: str):
    """Background task to extract, embed, and store document chunks using structural splitting."""
    with db_cursor_context() as cursor:
        try:
            # 1. Fetch documents EXACTLY how you originally had it to guarantee it works
            # (Added a safeguard just in case test_id is passed as the string "None")
            if test_id and test_id != "None":
                cursor.execute("""
                    SELECT id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified 
                    FROM test_documents 
                    WHERE test_id = %s
                """, (test_id,))
            else:
                cursor.execute("""
                    SELECT id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified 
                    FROM test_documents 
                    WHERE test_id IS NULL AND doc_type = 'KNOWLEDGE_BASE'
                """)

            all_documents = cursor.fetchall()

            if not all_documents:
                log_audit_event(
                    user_id=str(user_id), role=str(user_role), action="RAG_NO_DOC_FOUND",
                    resource_type="RAG", resource_id=str(test_id) if test_id else "KNOWLEDGE_BASE",
                    details="No documents found in the database for this test to index."
                )
                return

            # 2. Incremental Sync Check (Done safely one-by-one so SQL doesn't drop rows)
            docs_to_process = []
            for doc in all_documents:
                doc_id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified = doc

                # Check when this specific document was last embedded
                cursor.execute("SELECT MAX(created_at) FROM document_chunks WHERE document_id = %s", (doc_id,))
                chunk_row = cursor.fetchone()
                last_chunked = chunk_row[0] if chunk_row else None

                # If chunks exist and the document hasn't been modified in Drive since, skip it!
                if last_chunked and last_modified and last_modified <= last_chunked:
                    continue

                docs_to_process.append(doc)

            if not docs_to_process:
                log_audit_event(
                    user_id=str(user_id), role=str(user_role), action="RAG_NO_UPDATE",
                    resource_type="RAG", resource_id="Documents",
                    details=f"[{datetime.now(timezone.utc)}] Skipping RAG sync: All documents are already up to date."
                )
                return

            # 3. Delete chunks ONLY for the documents we are actively updating
            for doc in docs_to_process:
                cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc[0],))

            # 4. Extract and Embed
            for doc in docs_to_process:
                doc_id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified = doc
                chunks = []

                # Safely route virtual docs without faking Google Drive IDs
                if is_virtual:
                    cursor.execute("SELECT analysis_text FROM test_analyses WHERE test_id = %s", (test_id,))
                    analysis_row = cursor.fetchone()
                    raw_text = analysis_row[0] if analysis_row and analysis_row[0] else ""

                    if not raw_text.strip():
                        continue

                    raw_text = f"# [LLM QUALITY ANALYSIS]\n{raw_text}"
                    chunks = structure_aware_chunking(raw_text)

                else:
                    # External Google Drive file
                    try:
                        raw_text = extract_text_from_drive_file(drive_file_id, mime_type)
                    except Exception as e:
                        log_audit_event(
                            user_id=str(user_id), role=str(user_role), action="EXTRACT_TEXT_FROM_DOCUMENT_FAILED",
                            resource_type="RAG", resource_id=str(doc_id),
                            details=f"Failed to parse {file_name}: {e}"
                        )
                        continue

                    if not raw_text or not raw_text.strip():
                        continue

                    chunks = structure_aware_chunking(raw_text)

                if not chunks:
                    continue

                # 5. Rate-Limited Embedding Loop
                for index, chunk_text_content in enumerate(chunks):
                    max_retries = 3
                    base_delay = 5  # Start with a 5-second wait if rate-limited

                    for attempt in range(max_retries):
                        try:
                            response = client.models.embed_content(
                                model='gemini-embedding-2',
                                contents=chunk_text_content,
                                config=types.EmbedContentConfig(output_dimensionality=768)
                            )

                            embedding_obj = response.embeddings[0]
                            vector_str = json.dumps(embedding_obj.values)

                            cursor.execute("""
                                INSERT INTO document_chunks (id, document_id, test_id, chunk_index, text_content, embedding, created_at)
                                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s::vector, CURRENT_TIMESTAMP)
                            """, (doc_id, test_id, index, chunk_text_content, vector_str))

                            break  # Success! Exit the retry loop.

                        except Exception as e:
                            error_str = str(e)
                            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                                if attempt < max_retries - 1:
                                    sleep_time = base_delay * (2 ** attempt)
                                    print(f"Rate limited by Google (429). Retrying chunk {index} in {sleep_time}s...")
                                    time.sleep(sleep_time)
                                    continue
                                else:
                                    log_audit_event(
                                        user_id=str(user_id), role=str(user_role), action="RAG_EMBEDDING_FAILED_429",
                                        resource_type="RAG", resource_id=str(doc_id),
                                        details=f"Hit max retries for 429 Rate Limit on chunk {index}."
                                    )
                                    break
                            else:
                                log_audit_event(
                                    user_id=str(user_id), role=str(user_role), action="RAG_EMBEDDING_FAILED",
                                    resource_type="RAG", resource_id=str(doc_id),
                                    details=f"Generate embedding failed for chunk {index}: {error_str}"
                                )
                                break

            cursor.connection.commit()

            # Only log success if we actually processed something
            log_audit_event(
                user_id=str(user_id), role=str(user_role), action="CHUNK_TEXT_EMBEDDED",
                resource_type="RAG", resource_id=str(test_id) if test_id else "KNOWLEDGE_BASE",
                details=f"Generate embeddings using Gemini API Successful."
            )
        except Exception as e:
            cursor.connection.rollback()
            log_audit_event(
                user_id=str(user_id), role=str(user_role), action="RAG_SYNC_FAILED",
                resource_type="RAG", resource_id=str(test_id) if test_id else "KNOWLEDGE_BASE",
                details=f"RAG Sync failed: {str(e)}"
            )


def sync_knowledge_base_background(user_id: str, user_role: str):
    """Background worker specifically for the Global Knowledge Base."""
    print(f"[{datetime.now(timezone.utc)}] Starting Knowledge Base Drive & RAG sync...")

    # 1. Fetch new files from Google Drive
    try:
        DriveManager().sync_global_knowledge_base()
    except Exception as e:
        log_audit_event(
            user_id=user_id, role=user_role, action="SYNC_KB_DRIVE_FAILED",
            resource_type="RAG", resource_id="KNOWLEDGE_BASE",
            details=f"Failed to fetch new files from Google Drive: {e}"
        )
        return

    # 2. Embed the files into the AI Vector DB (Passing None for test_id)
    try:
        process_test_documents_background(None, user_id, user_role)
        log_audit_event(
            user_id=user_id, role=user_role, action="SYNC_KB_RAG_COMPLETED",
            resource_type="RAG", resource_id="KNOWLEDGE_BASE",
            details="Knowledge Base successfully synced and embedded."
        )
    except Exception as e:
        log_audit_event(
            user_id=user_id, role=user_role, action="SYNC_KB_RAG_FAILED",
            resource_type="RAG", resource_id="KNOWLEDGE_BASE",
            details=f"Failed to embed Knowledge Base: {e}"
        )


@router.post("/knowledge-base/sync", summary="[Admin] Sync Global Knowledge Base")
def trigger_knowledge_base_sync(
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_admin)
):
    """Admin endpoint to instantly sync only the Global Knowledge Base."""
    background_tasks.add_task(sync_knowledge_base_background, str(current_user["id"]), str(current_user["role"]))

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"],
        action="SYNC_KB_RAG_STARTED", resource_type="RAG", resource_id="KNOWLEDGE_BASE",
        details="Manual sync of Global Knowledge Base initiated."
    )
    return {"message": "Knowledge Base sync started in the background."}


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

    sync_knowledge_base_background(user_id, user_role)

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

        # Execute the sync in a background thread to prevent freezing FastAPI
        await asyncio.to_thread(sync_all_active_tests_background, "SYSTEM", "SYSTEM")


# --- CHATS ---
@router.get("/filters", summary="Get autocomplete filters for RAG chat")
def get_rag_filters(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    filters = []

    # 1. Doc Types (Trigger: /)
    filters.extend([
        {"type": "doc_type", "id": "KNOWLEDGE_BASE", "name": "Knowledge-Base", "trigger": "/"},
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
    try:
        query_response = client.models.embed_content(
            model='gemini-embedding-2',
            contents=req.query,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        query_vector = json.dumps(query_response.embeddings[0].values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to embed query: {str(e)}")

    with db_cursor_context() as cursor:
        #  We now explicitly SELECT dc.id (the permanent UUID of the chunk)
        query_sql = """
            SELECT dc.id, dc.text_content, td.id, td.file_name, td.file_url, td.doc_type, 1 - (dc.embedding <=> %s::vector) as similarity, dc.test_id
            FROM document_chunks dc
            JOIN test_documents td ON dc.document_id = td.id
        """

        where_clauses = []
        params = [query_vector]

        if req.doc_type == 'KNOWLEDGE_BASE':
            # ONLY search the global knowledge base
            where_clauses.append("dc.test_id IS NULL")
            where_clauses.append("td.doc_type = 'KNOWLEDGE_BASE'")
        else:
            # EXCLUDE the global knowledge base from normal test chats
            where_clauses.append("dc.test_id IS NOT NULL")

            if req.asset_id:
                query_sql = """
                    SELECT dc.id, dc.text_content, td.id, td.file_name, td.file_url, td.doc_type, 1 - (dc.embedding <=> %s::vector) as similarity, dc.test_id
                    FROM document_chunks dc
                    JOIN test_documents td ON dc.document_id = td.id
                    JOIN test_assets ta ON dc.test_id = ta.test_id
                """
                where_clauses.append("ta.asset_id = %s")
                params.append(str(req.asset_id))
            elif req.test_id:
                where_clauses.append("dc.test_id = %s")
                params.append(str(req.test_id))

            if req.doc_type:
                where_clauses.append("td.doc_type = %s")
                params.append(req.doc_type)

            if where_clauses:
                query_sql += " WHERE " + " AND ".join(where_clauses)

        query_sql += " ORDER BY dc.embedding <=> %s::vector LIMIT 30"
        params.append(query_vector)

        cursor.execute(query_sql, tuple(params))
        raw_results = cursor.fetchall()

        # Limit history to the last 3 turns (6 messages) to prevent 30k token blowout.
        # We order by DESC to get the latest, then reverse in Python to keep chronological order.
        cursor.execute("""
            SELECT question, answer 
            FROM rag_chat_logs 
            WHERE session_id = %s AND user_id = %s
            ORDER BY timestamp DESC LIMIT 3
        """, (str(req.session_id), str(current_user["id"])))
        history_rows = reversed(cursor.fetchall())

    has_full_report_for_test = set()
    # Unpack the new td.id (doc_id)
    for chunk_id, text_content, doc_id, file_name, file_url, doc_type, similarity, t_id in raw_results:
        if similarity > 0.5 and doc_type == 'FULL_TEST_REPORT':
            has_full_report_for_test.add(t_id)

    filtered_results = []
    for chunk_id, text_content, doc_id, file_name, file_url, doc_type, similarity, t_id in raw_results:
        if similarity <= 0.5:
            continue
        if doc_type == 'VULN_REPORT' and t_id in has_full_report_for_test:
            continue
        filtered_results.append((text_content, str(doc_id), file_name, file_url, doc_type))

    context_text = ""
    citations_map = {}
    doc_uuid_to_index = {}
    current_idx = 1

    for text_content, doc_id_str, file_name, file_url, doc_type in filtered_results[:15]:
        # Assign a clean sequential index (1, 2, 3...) to each UNIQUE document
        if doc_id_str not in doc_uuid_to_index:
            doc_uuid_to_index[doc_id_str] = current_idx
            current_idx += 1

        doc_idx = doc_uuid_to_index[doc_id_str]

        # Pass the clean index and the permanent doc ID to the LLM
        context_text += f"\n--- Source Document [{doc_idx}] (ID: {doc_id_str}): [{doc_type}] {file_name} ---\n{text_content}\n"

        # Key the map by Document UUID. This naturally deduplicates chunks from the same file!
        citations_map[doc_id_str] = {
            "id": doc_id_str,
            "file_name": file_name,
            "url": file_url
        }

    # --- START KEEP SECURE 24 LIVE INJECTION ---
    live_ks24_context = ""
    if req.test_id:
        # Look up the KS24 UUID directly using the existing test_id
        with db_cursor_context() as ks_cursor:
            ks_cursor.execute("SELECT kiss24 FROM tests WHERE id = %s", (str(req.test_id),))
            row = ks_cursor.fetchone()
            kiss24_uuid = str(row[0]) if row and row[0] else None

        if kiss24_uuid:
            try:
                # Reuse the existing utility function from kiss24.py
                raw_data = get_test_vulns_info(kiss24_uuid)

                if raw_data and raw_data.get("items"):
                    summary = []
                    for item in raw_data["items"]:
                        title = item.get("description", "Unknown")
                        severity = item.get("severity", "Unrated")
                        state = item.get("state", "Open")
                        vid = item.get("id", "N/A")

                        summary.append(f"- [{severity}] {title} (ID: {vid}, Current State: {state})")

                    live_ks24_context = "\n\n--- LIVE KEEP SECURE 24 STATUS ---\n" + "\n".join(summary) + "\n"

                    log_audit_event(
                        user_id=str(current_user["id"]),
                        role=str(current_user["role"]),
                        action="CHAT_VULN_LIVE_FETCH_INFO",
                        resource_type="RAG",
                        resource_id=f"{kiss24_uuid}",
                        details=f"LIVE KEEP SECURE 24 STATUS SUCCESS"
                    )
            except Exception as e:
                log_audit_event(
                    user_id=str(current_user["id"]),
                    role=str(current_user["role"]),
                    action="CHAT_VULN_LIVE_FETCH_INFO",
                    resource_type="RAG",
                    resource_id=f"{kiss24_uuid}",
                    details=f"Failed to fetch live KS24 data for RAG: {e}"
                )

    # Assemble final context
    if not context_text and not live_ks24_context:
        context_text = "No relevant context documents or live status were found for this query."
    else:
        context_text += live_ks24_context
    # --- END KEEP SECURE 24 LIVE INJECTION ---

    gemini_history = []
    for past_q, past_a in history_rows:
        gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=past_q)]))
        gemini_history.append(types.Content(role="model", parts=[types.Part.from_text(text=past_a)]))

    # Strict UUID enforcement via Markdown
    system_instruction = """
    Your name is Luigi. You are an expert cybersecurity assistant for the Global Offensive Security Team.
    Answer the user's question based strictly on the provided Context Documents and your previous conversation history.
    If the context does not contain the answer, politely state that you do not have that information.

    DOCUMENT TAXONOMY & ROUTING RULES:
    1. Documents tagged [FULL_TEST_REPORT] are the canonical source for overall pentest scope, vulnerability summaries, and official findings.
    2. Documents tagged [LLM_ANALYSIS] represent deep quality checks. ALWAYS prioritize [LLM_ANALYSIS] when answering questions about vulnerability quality, false positive status, or grades.
    3. If [LIVE KEEP SECURE 24 STATUS] is provided in the context, it represents the absolute latest real-time state of the test. ALWAYS prioritize this live data over static PDF reports regarding current state, remediation, or open/closed status.

    CITATION INSTRUCTIONS:
    When using information from the context, you MUST append an inline citation directly after the relevant sentence. 
    Format the citation EXACTLY as a Markdown link pointing to '#cite-ID', using the bracketed Document Index for the display text and the Document ID for the link URL.
    For example: "The vulnerability allows privilege escalation [[1]](#cite-123e4567-e89b-12d3-a456-426614174000)."
    DO NOT invent citation IDs. Only use the exact Document Indexes and IDs provided in the Source Document headers..
    """

    config = types.GenerateContentConfig(system_instruction=system_instruction)

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

            #  Safely regex extract the exact UUIDs the model decided to cite
            confirmed_citations = []
            cited_uuids = set(re.findall(r'#cite-([a-f0-9\-]{36})', full_answer))
            for cid in cited_uuids:
                if cid in citations_map:
                    confirmed_citations.append(citations_map[cid])

            new_log_id = str(uuid.uuid4())
            citations_json = json.dumps(confirmed_citations)

            yield json.dumps({"citations": confirmed_citations, "log_id": new_log_id}) + "\n"

            with db_cursor_context() as stream_cursor:
                # Store the exact citations array into our new JSONB column
                stream_cursor.execute("""
                        INSERT INTO rag_chat_logs (id, session_id, user_id, test_id, asset_id, question, answer, timestamp, citations)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    """, (
                    new_log_id, str(req.session_id), str(current_user["id"]),
                    str(req.test_id) if req.test_id else None, str(req.asset_id) if req.asset_id else None,
                    req.query, full_answer, citations_json
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


# --- SESSIONS ---
@router.get("/sessions", summary="Get user chat sessions")
def get_chat_sessions(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Groups chat logs by session, uses the first question as the title, and sorts by newest
    cursor.execute("""
        SELECT session_id, MAX(timestamp) as last_updated,
               (ARRAY_AGG(question ORDER BY timestamp ASC))[1] as title
        FROM rag_chat_logs
        WHERE user_id = %s AND is_session_active = TRUE
        GROUP BY session_id
        ORDER BY last_updated DESC
        LIMIT 50
    """, (str(current_user["id"]),))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.get("/sessions/{session_id}", summary="Get messages for a specific session")
def get_session_messages(session_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    #  Read the stored citations JSON directly so links survive page reloads
    cursor.execute("""
        SELECT id, question, answer, timestamp, user_feedback, citations 
        FROM rag_chat_logs 
        WHERE session_id = %s AND user_id = %s AND is_session_active = TRUE
        ORDER BY timestamp ASC
    """, (session_id, str(current_user["id"])))

    messages = []
    for log_id, q, a, t, feedback, citations in cursor.fetchall():
        time_str = t.strftime("%I:%M %p") if t else ""
        messages.append({
            "role": "user",
            "content": q,
            "timestamp": time_str
        })
        messages.append({
            "role": "assistant",
            "content": a,
            "citations": citations if citations else [],
            "timestamp": time_str,
            "log_id": str(log_id),
            "feedback": feedback
        })
    return messages


@router.post("/logs/{log_id}/feedback", summary="Submit feedback for a response")
def submit_rag_feedback(log_id: str, request: FeedbackRequest, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("""
        UPDATE rag_chat_logs 
        SET user_feedback = %s 
        WHERE id = %s AND user_id = %s
    """, (request.is_good, log_id, str(current_user["id"])))
    cursor.connection.commit()
    return {"status": "success"}


@router.delete("/sessions/{session_id}", summary="Soft delete a single chat session")
def delete_chat_session(session_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    if session_id == "all":
        # Bulk delete all
        cursor.execute("""
            UPDATE rag_chat_logs 
            SET is_session_active = FALSE 
            WHERE user_id = %s
        """, (str(current_user["id"]),))
    else:
        # Delete single session
        cursor.execute("""
            UPDATE rag_chat_logs 
            SET is_session_active = FALSE 
            WHERE session_id = %s AND user_id = %s
        """, (session_id, str(current_user["id"])))

    cursor.connection.commit()
    return {"status": "success"}


@router.post("/sessions/bulk-delete", summary="Soft delete multiple chat sessions")
def bulk_delete_chat_sessions(request: RagChatBulkDeleteRequest, current_user: dict = Depends(require_admin),
                              cursor=Depends(get_db_cursor)):
    if not request.session_ids:
        return {"status": "success"}

    if "all" in request.session_ids:
        # Delete all
        cursor.execute("""
            UPDATE rag_chat_logs 
            SET is_session_active = FALSE 
            WHERE user_id = %s
        """, (str(current_user["id"]),))
    else:
        # Delete selected
        format_strings = ','.join(['%s'] * len(request.session_ids))
        cursor.execute(f"""
            UPDATE rag_chat_logs 
            SET is_session_active = FALSE 
            WHERE session_id IN ({format_strings}) AND user_id = %s
        """, tuple(request.session_ids + [str(current_user["id"])]))

    cursor.connection.commit()
    return {"status": "success"}


@router.get("/sessions/shared/{session_id}", summary="Get messages for a shared session (Read-Only)")
def get_shared_session_messages(session_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Allows any authenticated team member with the unique session URL
    to view a shared chat transcript in read-only mode.
    """
    cursor.execute("""
        SELECT id, question, answer, timestamp, user_feedback, citations 
        FROM rag_chat_logs 
        WHERE session_id = %s AND is_session_active = TRUE
        ORDER BY timestamp ASC
    """, (session_id,))

    rows = cursor.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Shared session not found or has been deactivated.")

    messages = []
    for log_id, q, a, t, feedback, citations in rows:
        time_str = t.strftime("%I:%M %p") if t else ""
        messages.append({
            "role": "user",
            "content": q,
            "timestamp": time_str
        })
        messages.append({
            "role": "assistant",
            "content": a,
            "citations": citations if citations else [],
            "timestamp": time_str,
            "log_id": str(log_id),
            "feedback": feedback
        })
    return messages