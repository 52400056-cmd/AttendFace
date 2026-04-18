# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from database.db_connect import db_connect
from models.schemas import User, RoleEnum
from utils.security import get_password_hash, verify_password, create_access_token, get_current_user
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
import os
import base64

router = APIRouter(tags=["Authentication"])
db_instance = db_connect()

templates = Jinja2Templates(directory="templates")

# Schema dùng để nhận dữ liệu đăng ký (Pydantic)
class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str
    role: RoleEnum

@router.post("/api/register")
def register(user_data: UserRegister, db: Session = Depends(db_instance.get_session)):
    """API Đăng ký người dùng mới (Mã hóa mật khẩu)"""
    # Kiểm tra xem email đã tồn tại chưa
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký!")

    # Tạo User mới với mật khẩu đã băm
    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role
    )
    
    db.add(new_user)
    db.commit()
    return {"message": "Đăng ký thành công!", "email": new_user.email}

@router.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(db_instance.get_session)):
    """API Đăng nhập và trả về JWT Token"""
    # OAuth2PasswordRequestForm mặc định dùng trường 'username', ta sẽ coi nó như email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    # Kiểm tra user có tồn tại và mật khẩu có khớp không
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Tạo Token chứa thông tin định danh
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id}
    )
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # Vẫn phải set cookie để trình duyệt ghi nhớ trạng thái đăng nhập
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True 
    )
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token") # Xóa token khỏi trình duyệt
    return response

@router.get("/profile")
async def profile(request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "role": user.role
    })

@router.post("/api/save-face")
async def save_face(
    request: Request,
    data: dict = Body(...), 
    db: Session = Depends(db_instance.get_session),
):
    user = get_current_user(request, db)
    
    if not user:
        return {"error": "Chưa đăng nhập"}

    image_data = data.get("image").split(",")[1]
    
    # Tạo thư mục lưu trữ nếu chưa có
    upload_dir = "static/uploads/avatar"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Lưu file theo mã sinh viên của Nhân hoặc ID
    file_name = f"{user.student_code or user.id}.jpg"
    file_path = os.path.join(upload_dir, file_name)
    
    with open(file_path, "wb") as f:
        f.write(base64.b64decode(image_data))
    
    # Cập nhật DB
    user.url_pic = file_path
    db.commit()
    
    return {"message": "Đã lưu ảnh đại diện thành công!", "path": file_path}