import os
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from database import db_cursor_context
import uuid
from datetime import datetime
import asyncio
from websockets_manager import manager
from audit_logger import log_audit_event


class DriveManager:
    def __init__(self):
        # Exact same native auth pattern as importer.py
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds, project = google.auth.default(scopes=scopes)
        self.drive_service = build('drive', 'v3', credentials=creds)
        self.source_folder_id = os.getenv('SOURCE_FOLDER_ID')

    def find_folder(self, name: str, parent_id: str):
        """Searches for a specific folder inside a parent."""
        query = f"name='{name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.drive_service.files().list(
            q=query, fields="files(id, name, webViewLink)", supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute()
        items = results.get('files', [])
        return items[0] if items else None

    def create_folder(self, name: str, parent_id: str):
        """Creates a new folder inside a parent."""
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        return self.drive_service.files().create(
            body=file_metadata, fields='id, webViewLink', supportsAllDrives=True
        ).execute()

    def get_or_create_folder(self, name: str, parent_id: str):
        folder = self.find_folder(name, parent_id)
        return folder if folder else self.create_folder(name, parent_id)

    def scan_folder_recursive(self, folder_id: str, current_path: str = "") -> list:
        """Recursively scans a folder and all subfolders, passing down the relative path."""
        found_files = []
        try:
            query = f"'{folder_id}' in parents and trashed=false"

            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType, webViewLink, modifiedTime)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            for item in results.get('files', []):
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    # It found a subfolder! Append its name to the path and dive deeper.
                    new_path = f"{current_path}/{item['name']}" if current_path else item['name']
                    found_files.extend(self.scan_folder_recursive(item['id'], current_path=new_path))
                else:
                    # It found a file! Attach the current path before keeping it.
                    item['folder_path'] = current_path
                    found_files.append(item)

            return found_files
        except Exception as e:
            print(f"Error recursively scanning folder {folder_id}: {e}")
            return []

    def sync_global_knowledge_base(self, user_id: str = "SYSTEM", user_role: str = "SYSTEM"):
        """Indexes files from the global knowledge base folder and removes deleted orphans."""
        kb_folder_id = os.getenv('KNOWLEDGE_BASE_FOLDER_ID')

        if not kb_folder_id:
            raise ValueError("KNOWLEDGE_BASE_FOLDER_ID is not set in the environment variables.")

        files = self.scan_folder_recursive(kb_folder_id)

        with db_cursor_context() as cursor:
            # SCENARIO A: Folder is 100% empty (Wipe everything)
            if not files:
                print(f"Drive scanner found 0 files in folder {kb_folder_id}. Wiping Knowledge Base.")
                log_audit_event(
                    user_id=user_id, role=user_role, action="SYNC_KB_EMPTY_DRIVE",
                    resource_type="RAG", resource_id="KNOWLEDGE_BASE",
                    details="0 files found in Google Drive. Proceeding to wipe all Knowledge Base documents from the database."
                )

                # Delete all chunks linked to KB docs
                cursor.execute("""
                    DELETE FROM document_chunks 
                    WHERE document_id IN (
                        SELECT id FROM test_documents WHERE test_id IS NULL AND doc_type = 'KNOWLEDGE_BASE'
                    )
                """)

                # Delete all KB docs
                cursor.execute("DELETE FROM test_documents WHERE test_id IS NULL AND doc_type = 'KNOWLEDGE_BASE'")
                deleted_docs = cursor.rowcount

                if deleted_docs > 0:
                    log_audit_event(
                        user_id=user_id, role=user_role, action="SYNC_KB_ORPHAN_CLEANUP",
                        resource_type="RAG", resource_id="KNOWLEDGE_BASE",
                        details=f"Wiped {deleted_docs} orphaned documents from the Knowledge Base."
                    )

            # SCENARIO B: Folder has files (Upsert and Selective Cleanup)
            else:
                # 1. Upsert files that currently exist in Drive
                for f in files:
                    mod_time = datetime.strptime(f['modifiedTime'],
                                                 "%Y-%m-%dT%H:%M:%S.%fZ") if 'modifiedTime' in f else datetime.now()
                    # Upsert with test_id = NULL, doc_type = 'KNOWLEDGE_BASE', and the captured folder_path
                    cursor.execute('''
                        INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, doc_type, folder_path, last_modified, synced_at)
                        VALUES (%s, NULL, %s, %s, %s, %s, 'KNOWLEDGE_BASE', %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (drive_file_id) DO UPDATE SET 
                            file_name = EXCLUDED.file_name, 
                            file_url = EXCLUDED.file_url, 
                            folder_path = EXCLUDED.folder_path,
                            last_modified = EXCLUDED.last_modified, 
                            synced_at = CURRENT_TIMESTAMP
                    ''', (str(uuid.uuid4()), f['id'], f['name'], f.get('mimeType', 'unknown'), f.get('webViewLink', ''),
                          f.get('folder_path', ''), mod_time))

                # 2. Cleanup Step: Delete documents (and their AI chunks) that are no longer in Drive
                current_drive_ids = [f['id'] for f in files]
                format_strings = ','.join(['%s'] * len(current_drive_ids))

                # Safely delete the AI chunks for any orphaned documents
                cursor.execute(f"""
                    DELETE FROM document_chunks 
                    WHERE document_id IN (
                        SELECT id FROM test_documents 
                        WHERE test_id IS NULL 
                          AND doc_type = 'KNOWLEDGE_BASE' 
                          AND drive_file_id NOT IN ({format_strings})
                    )
                """, tuple(current_drive_ids))

                # Delete the orphaned documents themselves
                cursor.execute(f"""
                    DELETE FROM test_documents 
                    WHERE test_id IS NULL 
                      AND doc_type = 'KNOWLEDGE_BASE' 
                      AND drive_file_id NOT IN ({format_strings})
                """, tuple(current_drive_ids))

                deleted_docs = cursor.rowcount
                if deleted_docs > 0:
                    log_audit_event(
                        user_id=user_id, role=user_role, action="SYNC_KB_ORPHAN_CLEANUP",
                        resource_type="RAG", resource_id="KNOWLEDGE_BASE",
                        details=f"Removed {deleted_docs} orphaned documents that were deleted from Google Drive."
                    )

            cursor.connection.commit()

    def provision_test_workspace(self, test_id: str, year: int, service_name: str, market: str, test_name: str):
        try:
            # 1. Find "Reports" folder inside SOURCE_FOLDER_ID
            reports_folder = self.get_or_create_folder("02. Reports", self.source_folder_id)

            # 2. Year folder
            year_folder = self.get_or_create_folder(str(year), reports_folder['id'])

            # 3. Map the Service Name to the specific Drive Folder string
            clean_service = service_name if service_name else "Uncategorized"
            service_folder = self.get_or_create_folder(clean_service, year_folder['id'])

            # 4. Market folder (fallback to 'General' if no market is assigned)
            safe_market = market if market else "General"
            market_folder = self.get_or_create_folder(safe_market, service_folder['id'])

            # 5. Create the actual Test folder
            test_folder = self.get_or_create_folder(test_name, market_folder['id'])

            # 6. Save back to the database
            with db_cursor_context() as cursor:
                cursor.execute(
                    "UPDATE tests SET drive_folder_id = %s, drive_folder_url = %s WHERE id = %s",
                    (test_folder['id'], test_folder['webViewLink'], test_id)
                )
            print(f"Successfully provisioned Drive folder for test: {test_name}")

        except Exception as e:
            print(f"Failed to provision Drive workspace: {e}")

    def archive_test_workspace(self, folder_id: str, test_name: str):
        try:
            self.drive_service.files().delete(
                fileId=folder_id, supportsAllDrives=True
            ).execute()
            print(f"Trashed Drive folder {folder_id}")
        except Exception as e:
            print(f"Failed to trash Drive workspace: {e}")

    def scan_folder_for_files(self, folder_id: str):
        """Fetches all files (ignoring sub-folders) inside a specific Drive folder."""
        # Query: Inside this folder, NOT trashed, and NOT a folder itself
        query = f"'{folder_id}' in parents and trashed=false and mimeType != 'application/vnd.google-apps.folder'"
        try:
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType, webViewLink, modifiedTime)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            return results.get('files', [])
        except Exception as e:
            print(f"Error scanning folder {folder_id}: {e}")
            return []

    def run_daily_document_sync(self):
        """Finds all provisioned test folders and indexes their files into the database."""
        print("Starting Daily Drive Document Sync...")

        with db_cursor_context() as cursor:
            # 1. Get all tests that have a Google Drive folder
            cursor.execute("SELECT id, drive_folder_id FROM tests WHERE drive_folder_id IS NOT NULL")
            tests_with_folders = cursor.fetchall()

            success_count = 0

            for test_id, folder_id in tests_with_folders:
                files = self.scan_folder_for_files(folder_id)

                for f in files:
                    # Convert Google's ISO time string to standard timestamp
                    mod_time = datetime.strptime(f['modifiedTime'],
                                                 "%Y-%m-%dT%H:%M:%S.%fZ") if 'modifiedTime' in f else datetime.now()

                    # 2. UPSERT into the database
                    cursor.execute('''
                        INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, last_modified, synced_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (drive_file_id) 
                        DO UPDATE SET 
                            file_name = EXCLUDED.file_name,
                            file_url = EXCLUDED.file_url,
                            last_modified = EXCLUDED.last_modified,
                            synced_at = CURRENT_TIMESTAMP
                    ''', (
                        str(uuid.uuid4()), test_id, f['id'], f['name'],
                        f.get('mimeType', 'unknown'), f.get('webViewLink', ''), mod_time
                    ))
                    success_count += 1

            # Optional: Delete records in the DB if they were removed from Google Drive
            # (By deleting rows where synced_at is older than the start of this sync job)

            print(f"✅ Document Sync Complete. Indexed/Updated {success_count} files.")

    def relocate_test_workspace(self, folder_id: str, new_year: int, new_service_name: str, new_market: str,
                                new_test_name: str):
        """Moves an existing folder to a new path and updates its name if necessary."""
        try:
            # 1. Resolve what the NEW target parent folder should be
            reports_folder = self.get_or_create_folder("02. Reports", self.source_folder_id)
            year_folder = self.get_or_create_folder(str(new_year), reports_folder['id'])

            # Use the dynamic Service Name directly!
            clean_service = new_service_name if new_service_name else "Uncategorized"
            service_folder = self.get_or_create_folder(clean_service, year_folder['id'])

            safe_market = new_market if new_market else "General"
            market_folder = self.get_or_create_folder(safe_market, service_folder['id'])

            target_parent_id = market_folder['id']

            # 2. Get the current folder's actual state from Google Drive
            file = self.drive_service.files().get(
                fileId=folder_id, fields='parents, name', supportsAllDrives=True
            ).execute()

            current_parents = file.get('parents', [])
            current_name = file.get('name')

            # 3. Check what needs to change
            body = {}
            if current_name != new_test_name:
                body['name'] = new_test_name  # Update name if the test was renamed!

            needs_move = target_parent_id not in current_parents

            # 4. Execute the Drive API Update
            if needs_move:
                previous_parents = ",".join(current_parents)
                self.drive_service.files().update(
                    fileId=folder_id,
                    addParents=target_parent_id,
                    removeParents=previous_parents,
                    body=body if body else None,
                    supportsAllDrives=True
                ).execute()
                print(f"Moved and/or renamed workspace to: {clean_service} > {safe_market} > {new_test_name}")
            elif body:
                self.drive_service.files().update(
                    fileId=folder_id,
                    body=body,
                    supportsAllDrives=True
                ).execute()
                print(f"Renamed workspace to: {new_test_name}")

        except Exception as e:
            print(f"Failed to relocate Drive workspace: {e}")

    def upload_file(self, folder_id: str, filename: str, file_bytes: bytes, mimetype: str):
        """Uploads a file byte-stream to a specific Google Drive folder."""
        try:
            file_metadata = {'name': filename, 'parents': [folder_id]}
            media = MediaIoBaseUpload(
                io.BytesIO(file_bytes),
                mimetype=mimetype,
                resumable=True
            )
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()

            print(f"Uploaded {filename} to Drive successfully.")
            return {
                "id": file.get('id'),
                "link": file.get('webViewLink')
            }
        except Exception as e:
            print(f"Failed to upload file {filename}: {e}")
            raise e


# Add this to the bottom with your other async helpers:
async def background_relocate_workspace(folder_id, year, service_name, market, test_name):
    import asyncio
    await asyncio.to_thread(DriveManager().relocate_test_workspace, folder_id, year, service_name, market, test_name)


# Helper functions for FastAPI BackgroundTasks
async def background_provision_workspace(test_id, year, service_name, market, test_name):
    await asyncio.to_thread(DriveManager().provision_test_workspace, test_id, year, service_name, market, test_name)

    await manager.broadcast('{"action": "REFRESH_BOARD"}')


async def background_archive_workspace(folder_id, test_name):
    await asyncio.to_thread(DriveManager().archive_test_workspace, folder_id, test_name)
    await manager.broadcast('{"action": "REFRESH_BOARD"}')