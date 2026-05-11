import secrets
import string
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

# Cache for cipher instance to avoid recreating on every call
_cipher_cache = None
_cached_secret_key = None


def generate_temp_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_cipher():
    """Get Fernet cipher instance using app's SECRET_KEY. Cached for performance."""
    global _cipher_cache, _cached_secret_key
    
    key = current_app.config.get('SECRET_KEY')
    if not key:
        raise ValueError("SECRET_KEY not configured")
    
    # Only recreate cipher if SECRET_KEY changed
    if _cached_secret_key != key or _cipher_cache is None:
        # Derive a 32-byte key from SECRET_KEY using SHA256
        # This ensures consistent encryption/decryption
        key_bytes = hashlib.sha256(key.encode()).digest()
        # Base64 encode for Fernet (produces valid URL-safe base64)
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        _cipher_cache = Fernet(key_b64)
        _cached_secret_key = key
    
    return _cipher_cache


def encrypt_message(plaintext):
    """Encrypt message content. Returns base64 string of encrypted token."""
    try:
        if not plaintext:
            return plaintext
        
        cipher = get_cipher()
        # Fernet.encrypt() returns bytes that are already base64-encoded
        encrypted_token = cipher.encrypt(plaintext.encode())
        # Decode to string for storage in database
        return encrypted_token.decode('utf-8')
    except Exception as e:
        print(f"Encryption error: {e}")
        return plaintext


def decrypt_message(ciphertext):
    """Decrypt message content. Expects base64 string of encrypted token."""
    try:
        if not ciphertext:
            return ciphertext
        
        # Check if it looks like an encrypted token (starts with gAAAAA for Fernet)
        # If not, return as-is (backwards compatibility with unencrypted messages)
        if not isinstance(ciphertext, str) or not ciphertext.startswith('gAAAAA'):
            return ciphertext
        
        cipher = get_cipher()
        # Encode string back to bytes for decryption
        decrypted = cipher.decrypt(ciphertext.encode('utf-8'))
        return decrypted.decode('utf-8')
    except (InvalidToken, Exception) as e:
        print(f"Decryption error: {type(e).__name__}: {e}")
        # Return original if decryption fails (for backwards compatibility)
        return ciphertext
