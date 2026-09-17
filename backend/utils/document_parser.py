import io
import zipfile
import tempfile
import os
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
from pptx import Presentation
from googleapiclient.discovery import build
import google.auth
from googleapiclient.http import MediaIoBaseDownload
from audit_logger import log_audit_event


# --- MIME TYPE MAPPINGS ---
GOOGLE_MIME_TYPES = {
    'doc': 'application/vnd.google-apps.document',
    'sheet': 'application/vnd.google-apps.spreadsheet',
    'slide': 'application/vnd.google-apps.presentation'
}

EXPORT_MIME_TYPES = {
    'doc': 'text/plain',
    'sheet': 'text/csv',
    'slide': 'text/plain'
}


def get_drive_service():
    # Use your existing GCP service account credentials setup here
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build('drive', 'v3', credentials=credentials)


def extract_text_from_drive_file(drive_file_id: str, mime_type: str) -> str:
    """
    Downloads or exports a file from Google Drive and extracts all text.
    Includes a strict memory cap to prevent OOM panics from oversized blobs.
    """
    service = get_drive_service()

    # --- 1. HANDLE LARGE VIDEO FILES (STREAM DIRECTLY TO DISK) ---
    if mime_type.startswith('video/'):
        from system_services.rag_service import analyze_video_from_disk
        ext = ".mp4" if "mp4" in mime_type else ".webm"
        tmp_path = ""
        try:
            # Stream chunk by chunk into a local temp file on disk
            request = service.files().get_media(fileId=drive_file_id, supportsAllDrives=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_path = tmp_file.name
                downloader = MediaIoBaseDownload(tmp_file, request, chunksize=1024 * 1024 * 8)  # 8MB chunks
                done = False
                while not done:
                    status, done = downloader.next_chunk()

            # Pass the disk file directly to Gemini's File API
            return analyze_video_from_disk(tmp_path, mime_type)
        except Exception as e:
            return f"[Video Processing Error: {str(e)}]"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Enforce 25MB File Size Limit
    try:
        file_metadata = service.files().get(fileId=drive_file_id, fields="size", supportsAllDrives=True).execute()
        # Native Google Docs/Sheets don't return a 'size' field, so we default to 0
        file_size_bytes = int(file_metadata.get('size', 0))

        MAX_FILE_SIZE_MB = 25
        if file_size_bytes > (MAX_FILE_SIZE_MB * 1024 * 1024):
            log_audit_event(
                user_id="SYSTEM",
                role="SYSTEM",
                action="DOCUMENT_PARSING_EXTRACT_TEXT_ERROR",
                resource_type="DOCUMENT_PARSING",
                resource_id="DOCUMENT_PARSING",
                details=f"File exceeds maximum allowed ingestion size of {MAX_FILE_SIZE_MB}MB. (Detected: {file_size_bytes / (1024 * 1024):.1f}MB). Parsing aborted to prevent memory exhaustion"
            )
            raise ValueError(
                f"File exceeds maximum allowed ingestion size of {MAX_FILE_SIZE_MB}MB "
                f"(Detected: {file_size_bytes / (1024 * 1024):.1f}MB). "
                f"Parsing aborted to prevent memory exhaustion."
            )
    except ValueError as ve:
        log_audit_event(
            user_id="SYSTEM",
            role="SYSTEM",
            action="DOCUMENT_PARSING_EXTRACT_VALUE_ERROR",
            resource_type="DOCUMENT_PARSING",
            resource_id="DOCUMENT_PARSING",
            details=f"Document Parsing: Value error: {ve}"
        )
        raise ve  # Rethrow our explicit size limit error
    except Exception as ex:
        log_audit_event(
            user_id="SYSTEM",
            role="SYSTEM",
            action="DOCUMENT_PARSING_EXTRACT_EXCEPTION",
            resource_type="DOCUMENT_PARSING",
            resource_id="DOCUMENT_PARSING",
            details=f"Ignore standard API fetch errors and proceed to download attempt: {ex}"
        )
        # Ignore standard API fetch errors and proceed to download attempt
        pass

    # 1. HANDLE NATIVE GOOGLE WORKSPACE FILES (EXPORT)
    if mime_type == GOOGLE_MIME_TYPES['doc']:
        request = service.files().export_media(fileId=drive_file_id, mimeType=EXPORT_MIME_TYPES['doc'])
        return request.execute().decode('utf-8')

    elif mime_type == GOOGLE_MIME_TYPES['sheet']:
        request = service.files().export_media(fileId=drive_file_id, mimeType=EXPORT_MIME_TYPES['sheet'])
        return request.execute().decode('utf-8')

    elif mime_type == GOOGLE_MIME_TYPES['slide']:
        request = service.files().export_media(fileId=drive_file_id, mimeType=EXPORT_MIME_TYPES['slide'])
        return request.execute().decode('utf-8')

    # 2. HANDLE STANDARD BLOB FILES (DOWNLOAD)
    request = service.files().get_media(fileId=drive_file_id, supportsAllDrives=True)
    file_bytes = request.execute()
    file_stream = io.BytesIO(file_bytes)

    # 3. PARSE BLOB FILES BASED ON MIME TYPE
    #Handle Images and Videos

    if mime_type.startswith('image/'):
        from system_services.rag_service import analyze_multimodal_content
        return analyze_multimodal_content(file_bytes, mime_type)

    elif mime_type == 'application/pdf':
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join([page.get_text() for page in doc])
        return text

    elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':  # .docx
        doc = Document(file_stream)
        return "\n".join([para.text for para in doc.paragraphs])

    elif mime_type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':  # .pptx
        prs = Presentation(file_stream)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if paragraph.text.strip():
                            text_runs.append(paragraph.text.strip())
        return "\n".join(text_runs)

    elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':  # .xlsx
        df = pd.read_excel(file_stream)
        return df.to_csv(index=False)  # Convert Excel to CSV string for LLM readability

    elif mime_type == 'application/zip':
        return parse_zip_file(file_stream)

    elif mime_type.startswith('text/') or mime_type in [
        'application/json',
        'application/javascript',
        'application/csv',
        'text/csv',
        'text/markdown',
        'text/x-markdown'
    ]:
        # Catches .txt, .md, .csv, .json, .py, .js etc.
        return file_bytes.decode('utf-8', errors='ignore')

    else:
        return ""


def parse_zip_file(zip_stream: io.BytesIO) -> str:
    """Extracts text from all readable code/text files inside a ZIP archive."""
    text_content = []
    ignore_dirs = ['node_modules/', '.git/', '__pycache__/']
    valid_extensions = ('.py', '.js', '.ts', '.java', '.json', '.txt', '.md', '.html', '.css', '.go', '.rs')

    with zipfile.ZipFile(zip_stream) as z:
        for filename in z.namelist():
            if filename.endswith('/') or any(ign in filename for ign in ignore_dirs):
                continue
            if filename.endswith(valid_extensions):
                try:
                    with z.open(filename) as f:
                        file_text = f.read().decode('utf-8', errors='ignore')
                        text_content.append(f"--- FILE: {filename} ---\n{file_text}\n")
                except Exception as ex:
                    log_audit_event(
                        user_id="SYSTEM",
                        role="SYSTEM",
                        action="DOCUMENT_PARSING_ZIP_FILE_EXCEPTION",
                        resource_type="DOCUMENT_PARSING",
                        resource_id="PARSING_ZIP",
                        details=f"Exception parsing zip file: {ex}. Continue"
                    )
                    continue

    return "\n".join(text_content)