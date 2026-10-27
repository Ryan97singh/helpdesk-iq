import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.security import CurrentUser, DbSession, create_token, decode_token, hash_password, verify_password
from app.models import User
from app.schemas import LoginIn, RefreshIn, RegisterIn, TokenPair, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _tokens(user: User) -> TokenPair:
    return TokenPair(access_token=create_token(user, "access"), refresh_token=create_token(user, "refresh"),
                     user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbSession):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=email, name=body.name, hashed_password=hash_password(body.password))
    db.add(user)
    db.commit()
    return _tokens(user)


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: DbSession):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.hashed_password):
        # Same message for unknown email and wrong password: no account enumeration.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: DbSession):
    payload = decode_token(body.refresh_token, expected_kind="refresh")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return _tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.get("/providers")
def providers():
    s = get_settings()
    return {"google": bool(s.google_client_id), "demo_mode": s.demo_mode, "daily_budget_usd": s.llm_daily_budget_usd}


# --- Google OAuth 2.0 / OIDC (authorization-code flow) -------------------------------------------

@router.get("/google/login")
def google_login():
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google SSO is not configured")
    state = secrets.token_urlsafe(24)
    get_cache().set(f"oauth_state:{state}", "1", ttl=600)  # CSRF protection for the callback
    params = {"client_id": s.google_client_id, "redirect_uri": s.google_redirect_uri, "response_type": "code",
              "scope": "openid email profile", "state": state, "prompt": "select_account"}
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
def google_callback(request: Request, db: DbSession, code: str, state: str):
    s = get_settings()
    if not get_cache().get(f"oauth_state:{state}"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state")
    with httpx.Client(timeout=10) as client:
        token = client.post(GOOGLE_TOKEN_URL, data={
            "code": code, "client_id": s.google_client_id, "client_secret": s.google_client_secret,
            "redirect_uri": s.google_redirect_uri, "grant_type": "authorization_code"})
        if token.status_code != 200:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth code exchange failed")
        info = client.get(GOOGLE_USERINFO_URL,
                          headers={"Authorization": f"Bearer {token.json()['access_token']}"}).json()
    if not info.get("email_verified"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Google account email is not verified")
    email = info["email"].lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=info.get("name") or email, auth_provider="google")
        db.add(user)
        db.commit()
    pair = _tokens(user)
    # Tokens go in the URL fragment: never sent to servers or logged by proxies.
    fragment = urlencode({"access_token": pair.access_token, "refresh_token": pair.refresh_token})
    return RedirectResponse(f"{s.frontend_url}/auth/callback#{fragment}")
