from datetime import timedelta

import asyncpg
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from api.errors import StructuredHTTPException
from core.schemas import Token, UserCreate, UserResponse
from core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    verify_password,
)
from db.database import get_db_connection

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> dict:
    credentials_exception = StructuredHTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        error="Unauthorized",
        detail="Could not validate credentials",
        code="INVALID_CREDENTIALS",
        source="auth",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        raise StructuredHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="Unauthorized",
            detail="JWT token is expired or invalid",
            code="INVALID_TOKEN",
            source="auth",
        ) from e

    user = await conn.fetchrow("SELECT id, email FROM users WHERE email = $1", email)
    if user is None:
        raise credentials_exception
    return dict(user)


@router.post("/register", response_model=UserResponse)
async def register(
    user: UserCreate, conn: asyncpg.Connection = Depends(get_db_connection)
) -> dict:
    existing = await conn.fetchval(
        "SELECT id FROM users WHERE email = $1", user.email
    )
    if existing:
        raise StructuredHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Bad Request",
            detail="Email already registered",
            code="USER_ALREADY_EXISTS",
            source="auth",
        )
    hashed = get_password_hash(user.password)
    user_id = await conn.fetchval(
        "INSERT INTO users (email, hashed_password) VALUES ($1, $2) RETURNING id",
        user.email,
        hashed,
    )
    return {"id": user_id, "email": user.email}


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> dict:
    user = await conn.fetchrow(
        "SELECT id, email, hashed_password FROM users WHERE email = $1",
        form_data.username,
    )
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise StructuredHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="Unauthorized",
            detail="Incorrect email or password",
            code="INCORRECT_CREDENTIALS",
            source="auth",
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
