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
import json
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input
import numpy as np
import cv2

mobilenet_model = MobileNetV2(weights='imagenet', include_top=False, pooling='avg')

router = APIRouter(tags=["Authentication"])
db_instance = db_connect()

templates = Jinja2Templates(directory="templates")

# Schema dùng để nhận dữ liệu đăng ký (Pydantic)
class UserRegister(BaseModel):
    full_name: str
    student_code: str  # Thêm trường MSSV
    email: str
    password: str
    confirm_password: str # Thêm trường xác nhận mật khẩu

# 2. Cập nhật API Đăng ký
@router.post("/api/register")
def register(user_data: UserRegister, db: Session = Depends(db_instance.get_session)):
    """API Đăng ký sinh viên mới"""
    # Kiểm tra mật khẩu xác nhận
    if user_data.password != user_data.confirm_password:
        raise HTTPException(status_code=400, detail="Mật khẩu xác nhận không khớp!")

    # Kiểm tra xem MSSV hoặc Email đã tồn tại chưa
    if db.query(User).filter(User.student_code == user_data.student_code).first():
        raise HTTPException(status_code=400, detail="Mã sinh viên này đã được đăng ký!")
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký!")

    # Tạo User mới, mặc định gán quyền là STUDENT
    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        student_code=user_data.student_code,
        hashed_password=get_password_hash(user_data.password),
        role=RoleEnum.STUDENT 
    )
    
    db.add(new_user)
    db.commit()
    return {"message": "Đăng ký thành công!", "student_code": new_user.student_code}

@router.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(db_instance.get_session)):
    """API Đăng nhập: Chấp nhận cả MSSV hoặc Email"""
    
    # Tìm user dựa trên Email HOẶC Mã sinh viên
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.student_code == form_data.username)
    ).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thông tin đăng nhập không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(
        data={"sub": user.student_code or user.email, "role": user.role, "user_id": user.id}
    )
    
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
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

def get_face_embedding(image_path: str):
    img = cv2.imread(image_path)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    

    img_resized = cv2.resize(img, (224, 224))
    

    img_array = np.expand_dims(img_resized, axis=0)
    img_array = preprocess_input(img_array)
    
    # 4. Dự đoán (Trích xuất Vector)
    embedding = mobilenet_model.predict(img_array)
    
    # Trả về list Python thông thường thay vì Numpy Array để dễ dàng lưu vào PostgreSQL
    return embedding[0].tolist()
@router.post("/api/save-face")
async def save_face(
    request: Request,
    data: dict = Body(...), 
    db: Session = Depends(db_instance.get_session)
):
    user = get_current_user(request, db)
    if not user:
        return {"error": "Chưa đăng nhập"}

    image_data = data.get("image").split(",")[1]
    
    upload_dir = "static/uploads/avatar"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_name = f"{user.student_code or user.id}.jpg"
    file_path = os.path.join(upload_dir, file_name)
    
    with open(file_path, "wb") as f:
        f.write(base64.b64decode(image_data))
    
    # --- PHẦN MỚI: TẠO VÀ LƯU VECTOR ---
    try:
        # Gọi hàm tạo vector
        vector_data = get_face_embedding(file_path)
        
        # Cập nhật vào DB (pgvector yêu cầu truyền vào list hoặc string JSON)
        user.face_embedding = vector_data
        
    except Exception as e:
        print(f"Lỗi khi tạo embedding: {e}")
    # -----------------------------------
    
    user.url_pic = file_path
    db.commit()
    
    return {"message": "Đã lưu ảnh đại diện và tạo Vector thành công!", "path": file_path}

@router.get("/api/users/staff")
def get_staff(db: Session = Depends(db_instance.get_session)):
    return db.query(User).filter(User.role.in_(['admin', 'teacher'])).all()

# 2. Lấy danh sách toàn bộ sinh viên
@router.get("/api/users/students")
def get_students(db: Session = Depends(db_instance.get_session)):
    return db.query(User).filter(User.role == 'student').all()