import os
import base64
import hashlib
from cryptography.fernet import Fernet
from utils.secret_manager import get_secret


# --- SECURITY: ENCRYPTION CIPHER ---
def get_cipher():
    secret = str(get_secret(os.environ.get("SECURE_NOTE_SECRET_NAME")))
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)