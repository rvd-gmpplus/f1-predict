from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()

if settings.google_client_id:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.github_client_id:
    oauth.register(
        name="github",
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.email == body.email) | (User.username == body.username)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email or username already taken")

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/google")
async def google_login(request: Request):
    redirect_uri = f"{settings.frontend_url}/auth/callback/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo", {})
    user = db.query(User).filter(User.oauth_provider == "google", User.oauth_id == user_info["sub"]).first()
    if not user:
        user = db.query(User).filter(User.email == user_info["email"]).first()
        if user:
            user.oauth_provider = "google"
            user.oauth_id = user_info["sub"]
        else:
            user = User(
                email=user_info["email"],
                username=user_info.get("name", user_info["email"].split("@")[0]),
                oauth_provider="google", oauth_id=user_info["sub"],
                avatar_url=user_info.get("picture"),
            )
            db.add(user)
        db.commit()
        db.refresh(user)
    jwt_token = create_access_token(user_id=user.id)
    return RedirectResponse(f"{settings.frontend_url}/auth/success?token={jwt_token}")


@router.get("/github")
async def github_login(request: Request):
    redirect_uri = f"{settings.frontend_url}/auth/callback/github"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get("user", token=token)
    user_info = resp.json()
    email_resp = await oauth.github.get("user/emails", token=token)
    emails = email_resp.json()
    primary_email = next((e["email"] for e in emails if e["primary"]), user_info.get("email"))
    user = db.query(User).filter(User.oauth_provider == "github", User.oauth_id == str(user_info["id"])).first()
    if not user:
        user = db.query(User).filter(User.email == primary_email).first()
        if user:
            user.oauth_provider = "github"
            user.oauth_id = str(user_info["id"])
        else:
            user = User(
                email=primary_email,
                username=user_info.get("login", primary_email.split("@")[0]),
                oauth_provider="github", oauth_id=str(user_info["id"]),
                avatar_url=user_info.get("avatar_url"),
            )
            db.add(user)
        db.commit()
        db.refresh(user)
    jwt_token = create_access_token(user_id=user.id)
    return RedirectResponse(f"{settings.frontend_url}/auth/success?token={jwt_token}")
