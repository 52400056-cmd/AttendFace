from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Khóa bí mật dùng để ký JWT (Trong thực tế nên lưu ở file .env)
SECRET_KEY = "XanhPHP_52400056_52400247_TDTU_2026" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Token hết hạn sau 60 phút

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        # Loại bỏ tiền tố 'Bearer '
        token = token.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        # Tìm user trong DB (sử dụng db_connect)
        from models.schemas import User
        return db.query(User).filter(User.id == user_id).first()
    except:
        return None