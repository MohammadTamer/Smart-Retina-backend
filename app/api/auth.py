from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.db import models, database
from app.core import security
from app.schemas import user as user_schemas
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
from app.api import deps
from dotenv import load_dotenv
import requests
load_dotenv()

router = APIRouter()

@router.get("/me", response_model=user_schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(deps.get_current_user)):
    return current_user
@router.post("/signup", response_model=user_schemas.UserResponse)
def create_user(user: user_schemas.UserCreate, db: Session = Depends(database.get_db)):
    # validate if email already exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = security.get_password_hash(user.password)
    print(hashed_password)
    new_user = models.User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        provider=models.AuthProvider.LOCAL
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=user_schemas.Token)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create Tokens
    access_token = security.create_access_token(data={"sub": user.email, "role": user.role})
    refresh_token = security.create_refresh_token(data={"sub": user.email})

    # Save Refresh Token to DB
    db_refresh_token = models.RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=datetime.now() + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(db_refresh_token)
    db.commit()

    # set HttpOnly Cookie to avoid Xss
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,  # JavaScript cannot read this
        secure=False,  # Set to True in Production (HTTPS)
        samesite="lax",  # CSRF protection
        max_age=security.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "user_role": user.role,
    }


@router.post("/google", response_model=user_schemas.Token)
def google_login(login_data: user_schemas.GoogleLoginRequest, response: Response,
                 db: Session = Depends(database.get_db)):
    try:
        google_res = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {login_data.token}"}
        )

        if google_res.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google Token")

        user_info = google_res.json()

    except Exception:
        raise HTTPException(status_code=401, detail="Failed to connect to Google")

    email = user_info.get("email")
    name = user_info.get("name")
    picture = user_info.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        user = models.User(
            email=email,
            full_name=name,
            provider=models.AuthProvider.GOOGLE,
            role=models.UserRole.PATIENT,
            avatar_url=picture,
            hashed_password=None,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if user.avatar_url != picture:
            user.avatar_url = picture
            db.commit()
    access_token = security.create_access_token(data={"sub": user.email, "role": user.role})
    refresh_token = security.create_refresh_token(data={"sub": user.email})

    db_refresh_token = models.RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=datetime.now() + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(db_refresh_token)
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=security.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "user_role": user.role,
    }


@router.post("/logout")
def logout(response: Response, refresh_token: str = Cookie(None), db: Session = Depends(database.get_db)):
    if not refresh_token:
        return {"message": "Already logged out"}

    # Find token in DB
    stored_token = db.query(models.RefreshToken).filter(models.RefreshToken.token == refresh_token).first()

    if stored_token:
        stored_token.revoked = True
        db.commit()

    # Delete the cookie
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=user_schemas.Token)
def refresh_token(response: Response, refresh_token: str = Cookie(None), db: Session = Depends(database.get_db)):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    try:
        payload = jwt.decode(refresh_token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token signature")

    stored_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == refresh_token,
        models.RefreshToken.revoked == False
    ).first()

    if not stored_token:
        raise HTTPException(status_code=401, detail="Token revoked or not found")

    if stored_token.expires_at < datetime.now():
        stored_token.revoked = True
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.query(models.User).filter(models.User.id == stored_token.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    stored_token.revoked = True

    new_access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role}
    )
    new_refresh_token = security.create_refresh_token(
        data={"sub": user.email}
    )

    new_db_token = models.RefreshToken(
        token=new_refresh_token,
        user_id=user.id,
        expires_at=datetime.now() + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_db_token)

    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=False,  # Set True in production (HTTPS)
        samesite="lax",
        max_age=security.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "refresh_token": new_refresh_token
    }
