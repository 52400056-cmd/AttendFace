from fastapi import FastAPI, Request, Depends
from contextlib import asynccontextmanager
from database.db_connect import db_connect
from routers import auth
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from utils.security import get_current_user
# Khởi tạo instance kết nối
db = db_connect()

# Định nghĩa vòng đời (lifespan) của ứng dụng
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Hệ thống đang khởi động...")
    db.create_tables()
    
    yield 

    print("Hệ thống đang tắt...")

app = FastAPI(
    title="Hệ thống Điểm danh Khuôn mặt",
    lifespan=lifespan
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.include_router(auth.router)
@app.get("/")
async def index(request: Request, db: Session = Depends(db.get_session)):
    # 1. Dùng hàm get_current_user để giải mã Token và lấy thông tin từ DB
    user = get_current_user(request, db)
    
    if not user:
        # Nếu không có token, hoặc token hết hạn/sai lệch, đuổi về trang login
        return RedirectResponse(url="/login", status_code=302)
    
    # 2. Truyền biến 'user' sang cho Jinja2
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user  
    })

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Mở file main.py và sửa lại hàm get_attendance_list

@app.get("/attendance-list")
async def get_attendance_list(request: Request, db: Session = Depends(db.get_session)):
    # 1. Giải mã token để lấy thông tin user
    user = get_current_user(request, db)
    
    # 2. Bắt buộc phải đăng nhập mới được xem danh sách
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Dữ liệu giả định
    sample_students = [
        {"id": "52400056", "name": "Chu Đức Thành Nhân", "status": "Có mặt"},
        {"id": "52400057", "name": "Nguyễn Văn A", "status": "Vắng"}
    ]
    
    # 3. Truyền thêm biến 'user' vào TemplateResponse
    return templates.TemplateResponse(
        "students.html", 
        {
            "request": request, 
            "user": user,          # <--- ĐÂY LÀ DÒNG CHÌA KHÓA ĐỂ FIX LỖI
            "students": sample_students, 
            "title": "Danh sách điểm danh"
        }
    )

@app.get("/profile")
async def profile_page(request: Request, db: Session = Depends(db.get_session)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@app.get("/register-face")
async def register_face_page(request: Request, db: Session = Depends(db.get_session)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Trả về template register_face.html
    return templates.TemplateResponse("register_face.html", {
        "request": request, 
        "user": user
    })

