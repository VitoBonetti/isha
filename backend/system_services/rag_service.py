import os
import json
import re
import uuid
import time
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_
from google import genai
from google.genai import types
from models.tests import TestDocuments, Tests, TestAnalysis, TestAssets, DocumentChunk, RagChatLogs
from models.assets import Assets
from models.raw_assets import RawAssets
from database import SessionLocal
from utils.document_parser import extract_text_from_drive_file
from utils.secret_manager import get_secret
from utils.drive_manager import DriveManager
from utils.kiss24_app_service import get_test_vulns_info
from audit_logger import log_audit_event
from utils.timeaware import aware_utcnow

# Initialize the Gemini Client
client = genai.Client(api_key=get_secret(os.environ.get("LUIGI_KEY_NAME")))


def _parse_citations(raw_citations):
    """Bulletproof parser to ensure citations are ALWAYS a clean list for the frontend."""
    if not raw_citations:
        return []
    if isinstance(raw_citations, str):
        try:
            return json.loads(raw_citations)
        except Exception:
            return []
    if isinstance(raw_citations, list):
        return raw_citations
    return []


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
    db = SessionLocal()
    try:
        if test_id and test_id != "None":
            all_documents = db.query(TestDocuments).filter(TestDocuments.test_id == test_id).all()
        else:
            all_documents = db.query(TestDocuments).filter(TestDocuments.test_id.is_(None),
                                                           TestDocuments.doc_type == 'KNOWLEDGE_BASE').all()

        if not all_documents:
            log_audit_event(str(user_id), str(user_role), "RAG_NO_DOC_FOUND", "RAG",
                            str(test_id) if test_id else "KNOWLEDGE_BASE", "No documents found to index.")
            return

        docs_to_process = []
        for doc in all_documents:
            last_chunked = db.query(func.max(DocumentChunk.created_at)).filter(
                DocumentChunk.document_id == str(doc.id)).scalar()

            if last_chunked and doc.last_modified and doc.last_modified <= last_chunked:
                continue
            docs_to_process.append(doc)

        if not docs_to_process:
            log_audit_event(str(user_id), str(user_role), "RAG_NO_UPDATE", "RAG", "Documents",
                            f"[{aware_utcnow()}] Skipping RAG sync: All up to date.")
            return

        for doc in docs_to_process:
            db.query(DocumentChunk).filter(DocumentChunk.document_id == str(doc.id)).delete()

        for doc in docs_to_process:
            chunks = []

            if doc.is_virtual:
                analysis = db.query(TestAnalysis).filter(TestAnalysis.test_id == test_id).first()
                raw_text = analysis.analysis_text if analysis and analysis.analysis_text else ""
                if not raw_text.strip(): continue
                raw_text = f"# [LLM QUALITY ANALYSIS]\n{raw_text}"
                chunks = structure_aware_chunking(raw_text)
            else:
                try:
                    raw_text = extract_text_from_drive_file(doc.drive_file_id, doc.mime_type)
                except Exception as e:
                    log_audit_event(str(user_id), str(user_role), "EXTRACT_TEXT_FAILED", "RAG", str(doc.id),
                                    f"Failed to parse {doc.file_name}: {e}")
                    continue
                if not raw_text or not raw_text.strip(): continue
                chunks = structure_aware_chunking(raw_text)

            if not chunks: continue

            taxonomy_string = f"SOURCE TYPE: [{doc.doc_type}] | FILENAME: {doc.file_name}"
            if doc.folder_path: taxonomy_string += f" | FOLDER PATH: {doc.folder_path}"
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
                        vector_str = f"[{','.join(map(str, response.embeddings[0].values))}]"

                        # Change :vec::vector to CAST(:vec AS vector)
                        db.execute(text("""
                            INSERT INTO document_chunks (id, document_id, test_id, chunk_index, text_content, embedding, created_at) 
                            VALUES (gen_random_uuid(), :doc_id, :test_id, :index, :content, CAST(:vec AS vector), CURRENT_TIMESTAMP)
                        """), {"doc_id": str(doc.id), "test_id": test_id, "index": index, "content": contextualized_chunk, "vec": vector_str})

                        break
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            if attempt < max_retries - 1:
                                time.sleep(base_delay * (2 ** attempt))
                                continue
                            else:
                                log_audit_event(str(user_id), str(user_role), "RAG_EMBEDDING_FAILED_429", "RAG",
                                                str(doc.id), f"Max retries for chunk {index}.")
                                break
                        else:
                            log_audit_event(str(user_id), str(user_role), "RAG_EMBEDDING_FAILED", "RAG", str(doc.id),
                                            f"Failed chunk {index}: {error_str}")
                            break

        db.commit()
        log_audit_event(str(user_id), str(user_role), "CHUNK_TEXT_EMBEDDED", "RAG",
                        str(test_id) if test_id else "KNOWLEDGE_BASE", "Embeddings successful.")
    except Exception as e:
        db.rollback()
        log_audit_event(str(user_id), str(user_role), "RAG_SYNC_FAILED", "RAG",
                        str(test_id) if test_id else "KNOWLEDGE_BASE", f"Sync failed: {str(e)}")
    finally:
        db.close()


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

    db = SessionLocal()
    test_rows = db.query(Tests.id).filter(Tests.drive_folder_id.isnot(None)).all()
    db.close()

    for (t_id,) in test_rows:
        try:
            process_test_documents_background(str(t_id), user_id, user_role)
        except Exception as e:
            log_audit_event(user_id, user_role, "SYNC_ALL_TEST_TO_RAG_FAILED", "RAG", str(t_id),
                            f"Nightly sync failed: {e}")
    log_audit_event(user_id, user_role, "SYNC_ALL_TEST_TO_RAG_COMPLETED", "RAG", "ALL TESTS", "Nightly sync complete.")


def get_rag_filters(db: Session):
    filters = [
        {"type": "doc_type", "id": "KNOWLEDGE_BASE", "name": "Knowledge-Base", "trigger": "/"},
        {"type": "doc_type", "id": "FULL_TEST_REPORT", "name": "Full-Test-Report", "trigger": "/"},
        {"type": "doc_type", "id": "LLM_ANALYSIS", "name": "LLM-Quality-Analysis", "trigger": "/"},
        {"type": "doc_type", "id": "VULN_REPORT", "name": "Vulnerability-Report", "trigger": "/"},
        {"type": "doc_type", "id": "PRESENTATION", "name": "Presentation", "trigger": "/"},
        {"type": "doc_type", "id": "MANUAL_UPLOAD", "name": "Manual-Upload", "trigger": "/"},
    ]

    assets = (db.query(RawAssets.id, RawAssets.name)
              .distinct()
              .join(Assets, RawAssets.id == Assets.raw_asset_id)
              .join(TestAssets, Assets.id == TestAssets.asset_id)
              .join(Tests, TestAssets.test_id == Tests.id)
              .filter(Tests.drive_folder_id.isnot(None))
              .order_by(RawAssets.name.asc()).all())

    for r_id, r_name in assets:
        filters.append({"type": "asset", "id": str(r_id), "name": r_name.replace(" ", "-"), "trigger": "@"})

    tests = db.query(Tests.id, Tests.name).filter(Tests.drive_folder_id.isnot(None)).order_by(Tests.name.asc()).all()
    for t_id, t_name in tests:
        filters.append({"type": "test", "id": str(t_id), "name": t_name.replace(" ", "-"), "trigger": "$"})

    return filters


def get_rag_stats(db: Session):
    total = db.query(func.count(func.distinct(DocumentChunk.document_id))).scalar()
    return {"total_sources": total or 0}


def chat_with_documents(db: Session, req, current_user: dict):
    try:
        query_vector = json.dumps(client.models.embed_content(model='gemini-embedding-2', contents=req.query,
                                                              config=types.EmbedContentConfig(
                                                                  output_dimensionality=768)).embeddings[0].values)
        query_vector = f"[{query_vector[1:-1]}]"  # Format for pgvector
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to embed query: {str(e)}")

    # Use Raw SQL for the pgvector `<=>` operation for performance and accuracy
    query_sql = """
        SELECT dc.id, dc.text_content, td.id as doc_id, td.file_name, td.file_url, td.doc_type, 1 - (dc.embedding <=> CAST(:vec AS vector)) as similarity, dc.test_id 
        FROM document_chunks dc JOIN test_documents td ON dc.document_id = td.id
    """
    where_clauses, params = [], {"vec": query_vector}

    if req.doc_type == 'KNOWLEDGE_BASE':
        where_clauses.extend(["dc.test_id IS NULL", "td.doc_type = 'KNOWLEDGE_BASE'"])
    else:
        where_clauses.append("dc.test_id IS NOT NULL")
        if req.asset_id:
            query_sql += " JOIN test_assets ta ON dc.test_id = ta.test_id"
            where_clauses.append("ta.asset_id = :asset_id")
            params["asset_id"] = str(req.asset_id)
        elif req.test_id:
            where_clauses.append("dc.test_id = :test_id")
            params["test_id"] = str(req.test_id)
        if req.doc_type:
            where_clauses.append("td.doc_type = :doc_type")
            params["doc_type"] = req.doc_type

    if where_clauses: query_sql += " WHERE " + " AND ".join(where_clauses)
    query_sql += " ORDER BY dc.embedding <=> CAST(:vec AS vector) LIMIT 30"

    raw_results = db.execute(text(query_sql), params).fetchall()

    history_rows = (db.query(RagChatLogs.question, RagChatLogs.answer)
                    .filter(RagChatLogs.session_id == str(req.session_id), RagChatLogs.user_id == str(current_user["id"]))
                    .order_by(RagChatLogs.timestamp.desc()).limit(3).all())
    history_rows = list(reversed(history_rows))

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
        test = db.query(Tests).filter(Tests.id == str(req.test_id)).first()
        if test and test.kiss24:
            try:
                if raw_data := get_test_vulns_info(test.kiss24):
                    if raw_data.get("items"):
                        summary = [
                            f"- [{i.get('severity', 'Unrated')}] {i.get('description', 'Unknown')} (ID: {i.get('id', 'N/A')}, Current State: {i.get('state', 'Open')})"
                            for i in raw_data["items"]]
                        live_ks24_context = "\n\n--- LIVE KEEP SECURE 24 STATUS ---\n" + "\n".join(summary) + "\n"
                        log_audit_event(str(current_user["id"]), str(current_user["role"]), "CHAT_VULN_LIVE_FETCH",
                                        "RAG", test.kiss24, "SUCCESS")
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

            db_stream = SessionLocal()
            try:
                db_stream.execute(text("""
                    INSERT INTO rag_chat_logs (id, session_id, user_id, test_id, asset_id, question, answer, timestamp, citations) 
                    VALUES (:id, :session_id, :user_id, :test_id, :asset_id, :question, :answer, CURRENT_TIMESTAMP, :citations)
                """), {
                    "id": new_log_id,
                    "session_id": str(req.session_id),
                    "user_id": str(current_user["id"]),
                    "test_id": str(req.test_id) if req.test_id else None,
                    "asset_id": str(req.asset_id) if req.asset_id else None,
                    "question": req.query,
                    "answer": full_answer,
                    "citations": json.dumps(confirmed_citations)
                })
                db_stream.commit()
            finally:
                db_stream.close()

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


def get_chat_sessions(db: Session, current_user: dict):
    query = (db.query(
        RagChatLogs.session_id,
        func.max(RagChatLogs.timestamp).label("last_updated"),
        func.array_agg(RagChatLogs.question.op('ORDER BY')(RagChatLogs.timestamp.asc()))[1].label("title"))
             .filter(RagChatLogs.user_id == str(current_user["id"]), RagChatLogs.is_session_active == True)
             .group_by(RagChatLogs.session_id)
             .order_by(func.max(RagChatLogs.timestamp).desc()).limit(50))

    return [{"session_id": str(r.session_id), "last_updated": r.last_updated, "title": r.title} for r in query.all()]


def get_session_messages(db: Session, session_id: str, current_user: dict):
    messages_db = (db.query(RagChatLogs)
                   .filter(RagChatLogs.session_id == session_id, RagChatLogs.user_id == str(current_user["id"]), RagChatLogs.is_session_active == True)
                   .order_by(RagChatLogs.timestamp.asc()).all())

    messages = []
    for log in messages_db:
        time_str = log.timestamp.strftime("%I:%M %p") if log.timestamp else ""

        # USE THE FAILSAFE HERE
        clean_citations = _parse_citations(log.citations)

        messages.extend([
            {"role": "user", "content": log.question, "timestamp": time_str},
            {"role": "assistant", "content": log.answer, "citations": clean_citations, "timestamp": time_str,
             "log_id": str(log.id), "feedback": log.user_feedback}
        ])
    return messages


def get_shared_session_messages(db: Session, session_id: str):
    messages_db = (db.query(RagChatLogs)
                   .filter(RagChatLogs.session_id == session_id, RagChatLogs.is_session_active == True)
                   .order_by(RagChatLogs.timestamp.asc()).all())

    if not messages_db: raise HTTPException(status_code=404, detail="Shared session not found.")

    messages = []
    for log in messages_db:
        time_str = log.timestamp.strftime("%I:%M %p") if log.timestamp else ""

        # USE THE FAILSAFE HERE TOO
        clean_citations = _parse_citations(log.citations)

        messages.extend([
            {"role": "user", "content": log.question, "timestamp": time_str},
            {"role": "assistant", "content": log.answer, "citations": clean_citations, "timestamp": time_str,
             "log_id": str(log.id), "feedback": log.user_feedback}
        ])
    return messages


def submit_rag_feedback(db: Session, log_id: str, request, current_user: dict):
    log = db.query(RagChatLogs).filter(RagChatLogs.id == log_id, RagChatLogs.user_id == str(current_user["id"])).first()
    if log:
        log.user_feedback = request.is_good
        db.commit()
    return {"status": "success"}


def delete_chat_session(db: Session, session_id: str, current_user: dict):
    query = db.query(RagChatLogs).filter(RagChatLogs.user_id == str(current_user["id"]))
    if session_id != "all":
        query = query.filter(RagChatLogs.session_id == session_id)

    query.update({"is_session_active": False}, synchronize_session=False)
    db.commit()
    return {"status": "success"}


def bulk_delete_chat_sessions(db: Session, request, current_user: dict):
    if not request.session_ids: return {"status": "success"}

    query = db.query(RagChatLogs).filter(RagChatLogs.user_id == str(current_user["id"]))
    if "all" not in request.session_ids:
        query = query.filter(RagChatLogs.session_id.in_(request.session_ids))

    query.update({"is_session_active": False}, synchronize_session=False)
    db.commit()
    return {"status": "success"}