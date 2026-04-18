from fastapi import FastAPI, Request, Depends
from contextlib import asynccontextmanager
from database.db_connect import db_connect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from utils.security import get_current_user
from routers import auth, courses
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
app.include_router(courses.router) 

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

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

@app.get("/courses")
async def list_courses(request: Request, db: Session = Depends(db.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        return RedirectResponse(url="/login", status_code=302)

    # Logic phân quyền:
    if user.role == 'admin':
        # Admin thấy toàn bộ lớp học trong hệ thống
        courses = db.query(Course).all()
    else:
        # Giảng viên chỉ thấy lớp do mình phụ trách
        courses = db.query(Course).filter(Course.teacher_id == user.id).all()

    return templates.TemplateResponse("courses.html", {
        "request": request,
        "user": user,
        "courses": courses
    })

@app.get("/courses/{course_id}")
async def course_detail(course_id: int, request: Request, db: Session = Depends(db.get_session)):
    user = get_current_user(request, db)
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not course:
        return RedirectResponse(url="/courses")
    
    # Kiểm tra quyền truy cập chi tiết lớp
    if user.role != 'admin' and course.teacher_id != user.id:
        return RedirectResponse(url="/courses")

    return templates.TemplateResponse("course_detail.html", {
        "request": request,
        "user": user,
        "course": course,
        "students": course.students # Lấy danh sách SV đã tham gia lớp
    })

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

@app.get("/add-course")
async def add_course_page(request: Request, db: Session = Depends(db.get_session)):
    user = get_current_user(request, db)
    # Bảo mật: Chỉ cho phép admin hoặc giáo viên vào trang này
    if not user or user.role not in ['admin', 'teacher']:
        return RedirectResponse(url="/login", status_code=302)
        
    return templates.TemplateResponse("add_course.html", {
        "request": request, 
        "user": user
    })

