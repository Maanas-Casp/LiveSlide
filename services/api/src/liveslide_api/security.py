from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .config import API_JWT_EXPIRES_SECONDS, API_JWT_SECRET


def hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        import os
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return "scrypt$" + _b64(salt) + "$" + _b64(digest)


def check_password(password: str, stored_hash: str) -> bool:
    try:
        if stored_hash.startswith("scrypt$"):
            _, salt, digest = stored_hash.split("$", 2)
            actual = hashlib.scrypt(password.encode(),
                                    salt=base64.urlsafe_b64decode(salt + "=" * (-len(salt) % 4)),
                                    n=2**14, r=8, p=1)
            return hmac.compare_digest(_b64(actual), digest)
        import bcrypt
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except (ImportError, ValueError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_token(subject: str, role: str) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": subject, "role": role,
                              "exp": int(time.time()) + API_JWT_EXPIRES_SECONDS},
                             separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _b64(hmac.new(API_JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = _b64(hmac.new(API_JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid token signature")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(claims["exp"]) <= int(time.time()):
            raise ValueError("Token expired")
        return claims
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired token") from exc
