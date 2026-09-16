import os
import json
import re
import uuid
import time
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from database import db_cursor_context
from utils.document_parser import extract_text_from_drive_file
from utils.secret_manager import get_secret
from utils.drive_manager import DriveManager
from utils.kiss24_service import get_test_vulns_info
from audit_logger import log_audit_event

# Initialize the Gemini Client
client = genai.Client(api_key=get_secret(os.environ.get("LUIGI_KEY_NAME")))


def structure_aware_chunking(text: str, max_words: int = 500, overlap_words: int = 100) -> list[str]:
    chunks = []
    pattern = r'(?m)(?=^(?:#{1,6}\s+|Title:\s*|Original finding\s*))'
    sections = [s.strip() for s in re.split(pattern, text) if s.strip()]

    if not sections:
        sections = [text]

    for section in sections:
        words = section.split()
        if len(words) <= max_words:
            chunks.append(section)
        else:
            header = " ".join(words[:15])
            step = max(1, max_words - overlap_words)
            for i in range(0, len(words), step):
                sub_chunk = " ".join(words[i:i + max_words])
                if i > 0 and not sub_chunk.startswith(header):
                    sub_chunk = f"[Section Context: {header}...]\n{sub_chunk}"
                chunks.append(sub_chunk)
    return chunks


def process_test_documents_background(test_id: str, user_id: str, user_role: str):
    with db_cursor_context() as cursor:
        try:
            if test_id and test_id != "None":
                cursor.execute(
                    "SELECT id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified, folder_path FROM test_documents WHERE test_id = %s",
                    (test_id,))
            else:
                cursor.execute(
                    "SELECT id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified, folder_path FROM test_documents WHERE test_id IS NULL AND doc_type = 'KNOWLEDGE_BASE'")

            all_documents = cursor.fetchall()
            if not all_documents:
                log_audit_event(str(user_id), str(user_role), "RAG_NO_DOC_FOUND", "RAG",
                                str(test_id) if test_id else "KNOWLEDGE_BASE", "No documents found to index.")
                return

            docs_to_process = []
            for doc in all_documents:
                doc_id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified, folder_path = doc
                cursor.execute("SELECT MAX(created_at) FROM document_chunks WHERE document_id = %s", (doc_id,))
                chunk_row = cursor.fetchone()
                last_chunked = chunk_row[0] if chunk_row else None

                if last_chunked and last_modified and last_modified <= last_chunked:
                    continue
                docs_to_process.append(doc)

            if not docs_to_process:
                log_audit_event(str(user_id), str(user_role), "RAG_NO_UPDATE", "RAG", "Documents",
                                f"[{datetime.now(timezone.utc)}] Skipping RAG sync: All up to date.")
                return

            for doc in docs_to_process:
                cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc[0],))

            for doc in docs_to_process:
                doc_id, drive_file_id, mime_type, file_name, doc_type, is_virtual, last_modified, folder_path = doc
                chunks = []

                if is_virtual:
                    cursor.execute("SELECT analysis_text FROM test_analyses WHERE test_id = %s", (test_id,))
                    analysis_row = cursor.fetchone()
                    raw_text = analysis_row[0] if analysis_row and analysis_row[0] else ""
                    if not raw_text.strip(): continue
                    raw_text = f"# [LLM QUALITY ANALYSIS]\n{raw_text}"
                    chunks = structure_aware_chunking(raw_text)
                else:
                    try:
                        raw_text = extract_text_from_drive_file(drive_file_id, mime_type)
                    except Exception as e:
                        log_audit_event(str(user_id), str(user_role), "EXTRACT_TEXT_FAILED", "RAG", str(doc_id),
                                        f"Failed to parse {file_name}: {e}")
                        continue
                    if not raw_text or not raw_text.strip(): continue
                    chunks = structure_aware_chunking(raw_text)

                if not chunks: continue

                taxonomy_string = f"SOURCE TYPE: [{doc_type}] | FILENAME: {file_name}"
                if folder_path: taxonomy_string += f" | FOLDER PATH: {folder_path}"
                taxonomy_string = f"[{taxonomy_string}]\n\n"

                for index, chunk_text_content in enumerate(chunks):
                    contextualized_chunk = taxonomy_string + chunk_text_content
                    max_retries, base_delay = 3, 5

                    for attempt in range(max_retries):
                        try:
                            response = client.models.embed_content(model='gemini-embedding-2',
                                                                   contents=contextualized_chunk,
                                                                   config=types.EmbedContentConfig(
                                                                       output_dimensionality=768))
                            vector_str = json.dumps(response.embeddings[0].values)
                            cursor.execute(
                                "INSERT INTO document_chunks (id, document_id, test_id, chunk_index, text_content, embedding, created_at) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s::vector, CURRENT_TIMESTAMP)",
                                (doc_id, test_id, index, contextualized_chunk, vector_str))
                            break
                        except Exception as e:
                            error_str = str(e)
                            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                                if attempt < max_retries - 1:
                                    time.sleep(base_delay * (2 ** attempt))
                                    continue
                                else:
                                    log_audit_event(str(user_id), str(user_role), "RAG_EMBEDDING_FAILED_429", "RAG",
                                                    str(doc_id), f"Max retries for chunk {index}.")
                                    break
                            else:
                                log_audit_event(str(user_id), str(user_role), "RAG_EMBEDDING_FAILED", "RAG",
                                                str(doc_id), f"Failed chunk {index}: {error_str}")
                                break
            cursor.connection.commit()
            log_audit_event(str(user_id), str(user_role), "CHUNK_TEXT_EMBEDDED", "RAG",
                            str(test_id) if test_id else "KNOWLEDGE_BASE", "Embeddings successful.")
        except Exception as e:
            cursor.connection.rollback()
            log_audit_event(str(user_id), str(user_role), "RAG_SYNC_FAILED", "RAG",
                            str(test_id) if test_id else "KNOWLEDGE_BASE", f"Sync failed: {str(e)}")


def sync_knowledge_base_background(user_id: str, user_role: str):
    try:
        DriveManager().sync_global_knowledge_base(user_id, user_role)
    except Exception as e:
        log_audit_event(user_id, user_role, "SYNC_KB_DRIVE_FAILED", "RAG", "KNOWLEDGE_BASE", f"Drive sync failed: {e}")
        return
    try:
        process_test_documents_background(None, user_id, user_role)
        log_audit_event(user_id, user_role, "SYNC_KB_RAG_COMPLETED", "RAG", "KNOWLEDGE_BASE", "KB embedded.")
    except Exception as e:
        log_audit_event(user_id, user_role, "SYNC_KB_RAG_FAILED", "RAG", "KNOWLEDGE_BASE", f"Embed failed: {e}")


def sync_all_active_tests_background(user_id: str, user_role: str):
    sync_knowledge_base_background(user_id, user_role)
    with db_cursor_context() as cursor:
        cursor.execute("SELECT id FROM tests WHERE drive_folder_id IS NOT NULL")
        test_rows = cursor.fetchall()

    for (t_id,) in test_rows:
        try:
            process_test_documents_background(str(t_id), user_id, user_role)
        except Exception as e:
            log_audit_event(user_id, user_role, "SYNC_ALL_TEST_TO_RAG_FAILED", "RAG", str(t_id),
                            f"Nightly sync failed: {e}")
    log_audit_event(user_id, user_role, "SYNC_ALL_TEST_TO_RAG_COMPLETED", "RAG", "ALL TESTS", "Nightly sync complete.")


def get_rag_filters(cursor):
    filters = [
        {"type": "doc_type", "id": "KNOWLEDGE_BASE", "name": "Knowledge-Base", "trigger": "/"},
        {"type": "doc_type", "id": "FULL_TEST_REPORT", "name": "Full-Test-Report", "trigger": "/"},
        {"type": "doc_type", "id": "LLM_ANALYSIS", "name": "LLM-Quality-Analysis", "trigger": "/"},
        {"type": "doc_type", "id": "VULN_REPORT", "name": "Vulnerability-Report", "trigger": "/"},
        {"type": "doc_type", "id": "PRESENTATION", "name": "Presentation", "trigger": "/"},
        {"type": "doc_type", "id": "MANUAL_UPLOAD", "name": "Manual-Upload", "trigger": "/"},
    ]
    cursor.execute("""
        SELECT DISTINCT ra.id, ra.name FROM raw_assets ra JOIN assets a ON ra.id = a.raw_asset_id JOIN test_assets ta ON a.id = ta.asset_id JOIN tests t ON ta.test_id = t.id WHERE t.drive_folder_id IS NOT NULL ORDER BY ra.name ASC;
    """)
    for row in cursor.fetchall(): filters.append(
        {"type": "asset", "id": str(row[0]), "name": row[1].replace(" ", "-"), "trigger": "@"})

    cursor.execute("SELECT id, name FROM tests WHERE drive_folder_id IS NOT NULL ORDER BY name ASC")
    for row in cursor.fetchall(): filters.append(
        {"type": "test", "id": str(row[0]), "name": row[1].replace(" ", "-"), "trigger": "$"})
    return filters


def get_rag_stats(cursor):
    cursor.execute("SELECT COUNT(DISTINCT document_id) FROM document_chunks")
    return {"total_sources": cursor.fetchone()[0] or 0}


def chat_with_documents(cursor, req, current_user: dict):
    try:
        query_vector = json.dumps(client.models.embed_content(model='gemini-embedding-2', contents=req.query,
                                                              config=types.EmbedContentConfig(
                                                                  output_dimensionality=768)).embeddings[0].values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to embed query: {str(e)}")

    query_sql = "SELECT dc.id, dc.text_content, td.id, td.file_name, td.file_url, td.doc_type, 1 - (dc.embedding <=> %s::vector) as similarity, dc.test_id FROM document_chunks dc JOIN test_documents td ON dc.document_id = td.id"
    where_clauses, params = [], [query_vector]

    if req.doc_type == 'KNOWLEDGE_BASE':
        where_clauses.extend(["dc.test_id IS NULL", "td.doc_type = 'KNOWLEDGE_BASE'"])
    else:
        where_clauses.append("dc.test_id IS NOT NULL")
        if req.asset_id:
            query_sql += " JOIN test_assets ta ON dc.test_id = ta.test_id"
            where_clauses.append("ta.asset_id = %s")
            params.append(str(req.asset_id))
        elif req.test_id:
            where_clauses.append("dc.test_id = %s")
            params.append(str(req.test_id))
        if req.doc_type:
            where_clauses.append("td.doc_type = %s")
            params.append(req.doc_type)

    if where_clauses: query_sql += " WHERE " + " AND ".join(where_clauses)
    query_sql += " ORDER BY dc.embedding <=> %s::vector LIMIT 30"
    params.append(query_vector)

    cursor.execute(query_sql, tuple(params))
    raw_results = cursor.fetchall()

    cursor.execute(
        "SELECT question, answer FROM rag_chat_logs WHERE session_id = %s AND user_id = %s ORDER BY timestamp DESC LIMIT 3",
        (str(req.session_id), str(current_user["id"])))
    history_rows = reversed(cursor.fetchall())

    has_full_report = {t_id for _, _, _, _, _, dt, sim, t_id in raw_results if sim > 0.5 and dt == 'FULL_TEST_REPORT'}
    filtered_results = [(tc, str(did), fn, url, dt) for _, tc, did, fn, url, dt, sim, t_id in raw_results if
                        sim > 0.5 and not (dt == 'VULN_REPORT' and t_id in has_full_report)]

    context_text, citations_map, doc_uuid_to_index, current_idx = "", {}, {}, 1
    for tc, did_str, fn, url, dt in filtered_results[:15]:
        if did_str not in doc_uuid_to_index: doc_uuid_to_index[did_str] = current_idx; current_idx += 1
        doc_idx = doc_uuid_to_index[did_str]
        context_text += f"\n--- Source Document [{doc_idx}] (ID: {did_str}): [{dt}] {fn} ---\n{tc}\n"
        citations_map[did_str] = {"id": did_str, "file_name": fn, "url": url}

    live_ks24_context = ""
    if req.test_id:
        cursor.execute("SELECT kiss24 FROM tests WHERE id = %s", (str(req.test_id),))
        row = cursor.fetchone()
        if kiss24_uuid := str(row[0]) if row and row[0] else None:
            try:
                if raw_data := get_test_vulns_info(kiss24_uuid):
                    if raw_data.get("items"):
                        summary = [
                            f"- [{i.get('severity', 'Unrated')}] {i.get('description', 'Unknown')} (ID: {i.get('id', 'N/A')}, Current State: {i.get('state', 'Open')})"
                            for i in raw_data["items"]]
                        live_ks24_context = "\n\n--- LIVE KEEP SECURE 24 STATUS ---\n" + "\n".join(summary) + "\n"
                        log_audit_event(str(current_user["id"]), str(current_user["role"]), "CHAT_VULN_LIVE_FETCH",
                                        "RAG", kiss24_uuid, "SUCCESS")
            except Exception as e:
                pass

    context_text = context_text + live_ks24_context if context_text or live_ks24_context else "No relevant context found."

    gemini_history = [item for q, a in history_rows for item in
                      (types.Content(role="user", parts=[types.Part.from_text(text=q)]),
                       types.Content(role="model", parts=[types.Part.from_text(text=a)]))]

    sys_instr = """Your name is Luigi. Answer strictly based on Context Documents and history. If missing, say you don't know. Priority: 1. [LIVE KEEP SECURE 24 STATUS], 2. [LLM_ANALYSIS], 3. [FULL_TEST_REPORT]. Always cite using Markdown: '... fact [[1]](#cite-docID).'"""
    config = types.GenerateContentConfig(system_instruction=sys_instr)

    def event_generator():
        try:
            response_stream = client.chats.create(model='gemini-3.5-flash', history=gemini_history,
                                                  config=config).send_message_stream(
                f"Context:\n{context_text}\n\nQuestion: {req.query}")
            full_answer = ""
            for chunk in response_stream:
                if chunk.text:
                    full_answer += chunk.text
                    yield json.dumps({"text": chunk.text}) + "\n"

            confirmed_citations = [citations_map[cid] for cid in set(re.findall(r'#cite-([a-f0-9\-]{36})', full_answer))
                                   if cid in citations_map]
            new_log_id = str(uuid.uuid4())
            yield json.dumps({"citations": confirmed_citations, "log_id": new_log_id}) + "\n"

            with db_cursor_context() as stream_cursor:
                stream_cursor.execute(
                    "INSERT INTO rag_chat_logs (id, session_id, user_id, test_id, asset_id, question, answer, timestamp, citations) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)",
                    (new_log_id, str(req.session_id), str(current_user["id"]),
                     str(req.test_id) if req.test_id else None, str(req.asset_id) if req.asset_id else None, req.query,
                     full_answer, json.dumps(confirmed_citations)))
                stream_cursor.connection.commit()
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


def check_all_chunks(cursor):
    cursor.execute(
        "SELECT dc.id, td.file_name, t.name, dc.chunk_index, dc.text_content, dc.embedding::text, dc.created_at FROM document_chunks dc LEFT JOIN test_documents td ON dc.document_id = td.id LEFT JOIN tests t ON td.test_id = t.id")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_all_rag_logs(cursor):
    cursor.execute("SELECT * FROM rag_chat_logs")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_chat_sessions(cursor, current_user: dict):
    cursor.execute(
        "SELECT session_id, MAX(timestamp) as last_updated, (ARRAY_AGG(question ORDER BY timestamp ASC))[1] as title FROM rag_chat_logs WHERE user_id = %s AND is_session_active = TRUE GROUP BY session_id ORDER BY last_updated DESC LIMIT 50",
        (str(current_user["id"]),))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_session_messages(cursor, session_id: str, current_user: dict):
    cursor.execute(
        "SELECT id, question, answer, timestamp, user_feedback, citations FROM rag_chat_logs WHERE session_id = %s AND user_id = %s AND is_session_active = TRUE ORDER BY timestamp ASC",
        (session_id, str(current_user["id"])))
    messages = []
    for log_id, q, a, t, feedback, citations in cursor.fetchall():
        time_str = t.strftime("%I:%M %p") if t else ""
        messages.extend([{"role": "user", "content": q, "timestamp": time_str},
                         {"role": "assistant", "content": a, "citations": citations if citations else [],
                          "timestamp": time_str, "log_id": str(log_id), "feedback": feedback}])
    return messages


def get_shared_session_messages(cursor, session_id: str):
    cursor.execute(
        "SELECT id, question, answer, timestamp, user_feedback, citations FROM rag_chat_logs WHERE session_id = %s AND is_session_active = TRUE ORDER BY timestamp ASC",
        (session_id,))
    rows = cursor.fetchall()
    if not rows: raise HTTPException(status_code=404, detail="Shared session not found.")
    messages = []
    for log_id, q, a, t, feedback, citations in rows:
        time_str = t.strftime("%I:%M %p") if t else ""
        messages.extend([{"role": "user", "content": q, "timestamp": time_str},
                         {"role": "assistant", "content": a, "citations": citations if citations else [],
                          "timestamp": time_str, "log_id": str(log_id), "feedback": feedback}])
    return messages


def submit_rag_feedback(cursor, log_id: str, request, current_user: dict):
    cursor.execute("UPDATE rag_chat_logs SET user_feedback = %s WHERE id = %s AND user_id = %s",
                   (request.is_good, log_id, str(current_user["id"])))
    cursor.connection.commit()
    return {"status": "success"}


def delete_chat_session(cursor, session_id: str, current_user: dict):
    if session_id == "all":
        cursor.execute("UPDATE rag_chat_logs SET is_session_active = FALSE WHERE user_id = %s",
                       (str(current_user["id"]),))
    else:
        cursor.execute("UPDATE rag_chat_logs SET is_session_active = FALSE WHERE session_id = %s AND user_id = %s",
                       (session_id, str(current_user["id"])))
    cursor.connection.commit()
    return {"status": "success"}


def bulk_delete_chat_sessions(cursor, request, current_user: dict):
    if not request.session_ids: return {"status": "success"}
    if "all" in request.session_ids:
        cursor.execute("UPDATE rag_chat_logs SET is_session_active = FALSE WHERE user_id = %s",
                       (str(current_user["id"]),))
    else:
        cursor.execute(
            f"UPDATE rag_chat_logs SET is_session_active = FALSE WHERE session_id IN ({','.join(['%s'] * len(request.session_ids))}) AND user_id = %s",
            tuple(request.session_ids + [str(current_user["id"])]))
    cursor.connection.commit()
    return {"status": "success"}