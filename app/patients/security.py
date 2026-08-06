import base64
import hashlib
import re
from flask import current_app
from cryptography.fernet import Fernet

def get_fernet_key():
    """Derive a 32-byte URL-safe base64 key from current_app.config['SECRET_KEY']"""
    secret = current_app.config.get('SECRET_KEY', 'default-ipcms-secret-key')
    key_bytes = hashlib.sha256(secret.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_aadhaar(aadhaar_raw: str) -> str:
    """Encrypt 12-digit Aadhaar number for secure storage at rest."""
    if not aadhaar_raw:
        return ""
    clean_num = re.sub(r'\D', '', str(aadhaar_raw))
    if not clean_num:
        return ""
    f = Fernet(get_fernet_key())
    encrypted = f.encrypt(clean_num.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_aadhaar(aadhaar_encrypted: str) -> str:
    """Decrypt Aadhaar number for authorized roles."""
    if not aadhaar_encrypted:
        return ""
    try:
        f = Fernet(get_fernet_key())
        decrypted = f.decrypt(aadhaar_encrypted.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception:
        return ""


def mask_aadhaar(aadhaar_raw: str) -> str:
    """Returns masked Aadhaar format e.g. XXXX-XXXX-5678."""
    if not aadhaar_raw:
        return "N/A"
    clean_num = re.sub(r'\D', '', str(aadhaar_raw))
    if len(clean_num) >= 4:
        last4 = clean_num[-4:]
        return f"XXXX-XXXX-{last4}"
    return "XXXX-XXXX-XXXX"
