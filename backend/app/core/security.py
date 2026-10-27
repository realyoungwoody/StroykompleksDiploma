import re
import time
from collections import defaultdict, deque
from secrets import token_urlsafe
from urllib.parse import urlparse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from argon2 import PasswordHasher
from fastapi import HTTPException, Request
from .config import get_settings

hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except Exception:
        return False


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11 or not digits.startswith("7"):
        raise ValueError("Введите корректный российский номер телефона")
    return "+" + digits


serializer = URLSafeTimedSerializer(get_settings().session_secret, salt="admin-session")


def make_session(admin_id: int) -> str:
    return serializer.dumps({"admin_id": admin_id, "nonce": token_urlsafe(8)})


def get_admin_id(request: Request) -> int:
    token = request.cookies.get("admin_session")
    if not token:
        raise HTTPException(401, "Требуется вход администратора")
    try:
        return int(serializer.loads(token, max_age=60 * 60 * 12)["admin_id"])
    except (BadSignature, KeyError, ValueError):
        raise HTTPException(401, "Сессия недействительна")


def verify_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    origin_host = urlparse(origin).hostname
    allowed_dev_origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    }
    if origin_host != request.url.hostname and origin not in allowed_dev_origins:
        raise HTTPException(403, "Недопустимый источник запроса")


class RateLimiter:
    def __init__(self):
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, seconds: int) -> None:
        now = time.monotonic()
        bucket = self.events[key]
        while bucket and bucket[0] < now - seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, "Слишком много запросов. Повторите позже")
        bucket.append(now)


rate_limiter = RateLimiter()
