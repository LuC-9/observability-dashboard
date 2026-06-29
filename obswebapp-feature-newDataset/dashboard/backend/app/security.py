import datetime
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from . import config

_bearer = HTTPBearer(auto_error=False)


def make_token(username: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"sub": username, "iat": now,
               "exp": now + datetime.timedelta(hours=config.JWT_TTL_HOURS)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def login(username: str, password: str) -> str:
    if username == config.ADMIN_USER and password == config.ADMIN_PASS:
        return make_token(username)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")


def login_google(credential: str) -> tuple[str, str]:
    """Verify a Google Identity credential (ID token); allow only the configured domain."""
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "SSO not configured")
    from google.oauth2 import id_token
    from google.auth.transport import requests as grequests
    try:
        info = id_token.verify_oauth2_token(credential, grequests.Request(), config.GOOGLE_CLIENT_ID)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid Google token")
    email = (info.get("email") or "").lower()
    hd = info.get("hd")
    if config.ALLOWED_DOMAIN and not (email.endswith("@" + config.ALLOWED_DOMAIN) or hd == config.ALLOWED_DOMAIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"only {config.ALLOWED_DOMAIN} accounts allowed")
    return make_token(email), email


def require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    try:
        payload = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid/expired token")
