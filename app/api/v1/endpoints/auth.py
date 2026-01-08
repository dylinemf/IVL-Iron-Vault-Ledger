from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.db.session import get_session
from app.core.security import verify_password, hash_password
from app.core.auth import create_access_token
from app.core.config import settings
from app.models import User

auth_router = APIRouter()

@auth_router.post("/token", response_model=dict)
def login_for_access_token(
    session: Session = Depends(get_session), form_data: OAuth2PasswordRequestForm = Depends()
):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/register", response_model=dict)
def register_user(
    username: str = Body(...), 
    password: str = Body(...), 
    fullname: str = Body(default=None), 
    session: Session = Depends(get_session)
):
    existing_user = session.exec(select(User).where(User.username == username)).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already registered")
    
    hashed_password = hash_password(password)
    new_user = User(username=username, hashed_password=hashed_password, full_name=fullname)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    return {
        "status": "success",
        "message": "User registered successfully",
        "data": {
            "username": new_user.username
        }
    }
