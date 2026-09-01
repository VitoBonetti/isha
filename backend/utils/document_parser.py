import io
import zipfile
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
from pptx import Presentation
from googleapiclient.discovery import build
import google.auth

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

    # Enforce 25MB File Size Limit
    try:
        file_metadata = service.files().get(fileId=drive_file_id, fields="size").execute()
        # Native Google Docs/Sheets don't return a 'size' field, so we default to 0
        file_size_bytes = int(file_metadata.get('size', 0))

        MAX_FILE_SIZE_MB = 25
        if file_size_bytes > (MAX_FILE_SIZE_MB * 1024 * 1024):
            raise ValueError(
                f"File exceeds maximum allowed ingestion size of {MAX_FILE_SIZE_MB}MB "
                f"(Detected: {file_size_bytes / (1024 * 1024):.1f}MB). "
                f"Parsing aborted to prevent memory exhaustion."
            )
    except ValueError as ve:
        raise ve  # Rethrow our explicit size limit error
    except Exception:
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
    request = service.files().get_media(fileId=drive_file_id)
    file_bytes = request.execute()
    file_stream = io.BytesIO(file_bytes)

    # 3. PARSE BLOB FILES BASED ON MIME TYPE
    if mime_type == 'application/pdf':
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
                except Exception:
                    continue

    return "\n".join(text_content)