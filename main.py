from fastapi import FastAPI, Request, Depends
from contextlib import asynccontextmanager
from database.db_connect import db_connect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from utils.security import get_current_user
from routers import auth, courses, attendance   
from models.schemas import Course, User as UserModel, Session as CourseSessionModel
db = db_connect()

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
app.include_router(attendance.router)

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/")
async def index(request: Request, db: Session = Depends(db.get_session)):
    user = get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    if user.role == 'admin':
        courses = db.query(Course).all()
        total_students = db.query(UserModel).filter(UserModel.role == 'student').count()
        total_sessions = db.query(CourseSessionModel).count()
    elif user.role == 'teacher':
        courses = db.query(Course).filter(Course.teacher_id == user.id).all()
        total_students = sum([len(c.students) for c in courses]) 
        total_sessions = sum([len(c.sessions) for c in courses])
    else:
        courses = user.courses_enrolled
        total_students = 0
        total_sessions = 0

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,  
        "courses": courses,
        "total_courses": len(courses),
        "total_students": total_students,
        "total_sessions": total_sessions
    })

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register-face")
async def register_face_page(request: Request, db: Session = Depends(db.get_session)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("register_face.html", {
        "request": request, 
        "user": user
    })

