"""Bounded, expiring in-memory upload references; never written to disk."""
import secrets
import time
import threading

_uploads = {}
_lock = threading.Lock()
MAX_BYTES = 60 * 1024 * 1024
TTL = 30 * 60

def store(data):
    if len(data) > 20 * 1024 * 1024:
        raise ValueError('Upload a PDF smaller than 20 MB.')
    with _lock:
        now = time.monotonic()
        for key, (saved, _) in list(_uploads.items()):
            if now-saved > TTL:
                del _uploads[key]
        while _uploads and sum(len(v[1]) for v in _uploads.values()) + len(data) > MAX_BYTES:
            del _uploads[next(iter(_uploads))]
        token = secrets.token_urlsafe(32)
        _uploads[token] = (now, data)
        return token

def resolve(token):
    with _lock:
        entry = _uploads.get(token) if isinstance(token, str) else None
        if not entry or time.monotonic()-entry[0] > TTL:
            raise ValueError('Uploaded document expired. Select the file again to continue.')
        _uploads[token] = (time.monotonic(), entry[1])
        return entry[1]
