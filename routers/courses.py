# routers/courses.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database.db_connect import db_connect
from models.schemas import User, Course, RoleEnum, Session as CourseSessionModel
from utils.security import get_current_user
from datetime import date, time

router = APIRouter(tags=["Courses Management"])
# Khởi tạo db_instance
db_instance = db_connect()
templates = Jinja2Templates(directory="templates")

# --- SCHEMAS ---
class CourseCreate(BaseModel):
    name: str
    total_sessions: int = 15
    absence_limit: int = 3

class StudentEnroll(BaseModel):
    student_code: str

class CourseSessionCreate(BaseModel):
    date: date
    start_time: time
    late_threshold_time: time

# --- API ENDPOINTS ---

@router.post("/api/courses")
async def create_course(request: Request, course_data: CourseCreate, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in [RoleEnum.ADMIN, RoleEnum.TEACHER]:
        raise HTTPException(status_code=403, detail="Bạn không có quyền tạo lớp học")

    # Đã thêm các trường số buổi vào lúc khởi tạo lớp
    new_course = Course(
        name=course_data.name, 
        teacher_id=user.id,
        total_sessions=course_data.total_sessions,
        absence_limit=course_data.absence_limit
    )
    db.add(new_course)
    db.commit()
    return {"message": "Tạo lớp học thành công", "course_id": new_course.id}

@router.post("/api/courses/{course_id}/enroll")
async def enroll_student(course_id: int, enroll_data: StudentEnroll, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in [RoleEnum.ADMIN, RoleEnum.TEACHER]:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")

    student = db.query(User).filter(User.student_code == enroll_data.student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên với mã này")

    if student in course.students:
        return {"message": "Sinh viên đã có tên trong lớp này"}
    
    course.students.append(student)
    db.commit()
    return {"message": f"Đã thêm sinh viên {student.full_name} vào lớp"}

@router.get("/courses/{course_id}/students")
async def get_course_students(course_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")

    return templates.TemplateResponse("course_students.html", {
        "request": request,
        "user": user,
        "course": course,
        "students": course.students
    })

@router.get("/courses")
async def list_courses(request: Request, db: Session = Depends(db_instance.get_session)): # Đã sửa db.get_session -> db_instance.get_session
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        return RedirectResponse(url="/login", status_code=302)

    # Logic phân quyền:
    if user.role == 'admin':
        courses = db.query(Course).all()
    else:
        courses = db.query(Course).filter(Course.teacher_id == user.id).all()

    return templates.TemplateResponse("courses.html", {
        "request": request,
        "user": user,
        "courses": courses
    })

@router.get("/courses/{course_id}")
async def course_detail(course_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not course:
        return RedirectResponse(url="/courses")
    
    if user.role != 'admin' and course.teacher_id != user.id:
        return RedirectResponse(url="/courses")

    return templates.TemplateResponse("course_detail.html", {
        "request": request,
        "user": user,
        "course": course,
        "students": course.students,
        "sessions": course.sessions
    })

@router.get("/api/users/search")
async def search_students(q: str, request: Request, db: Session = Depends(db_instance.get_session)):
    """API Gợi ý tìm kiếm sinh viên (Tối đa 50 kết quả)"""
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Tìm kiếm theo MSSV hoặc Tên (sử dụng ilike để không phân biệt hoa thường)
    students = db.query(User).filter(
        (User.role == 'student') &
        ((User.student_code.ilike(f"%{q}%")) | (User.full_name.ilike(f"%{q}%")))
    ).limit(50).all()

    # Chỉ trả về dữ liệu cần thiết cho thẻ dropdown
    return [{"student_code": s.student_code, "full_name": s.full_name} for s in students]


@router.delete("/api/courses/{course_id}/students/{student_code}")
async def remove_student(course_id: int, student_code: str, request: Request, db: Session = Depends(db_instance.get_session)):
    """API Xóa sinh viên khỏi lớp học"""
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Forbidden")

    course = db.query(Course).filter(Course.id == course_id).first()
    student = db.query(User).filter(User.student_code == student_code).first()
    
    if not course or not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu")

    # Xóa mối quan hệ Nhiều-Nhiều
    if student in course.students:
        course.students.remove(student)
        db.commit()
        return {"message": "Đã xóa sinh viên khỏi lớp"}
        
    return {"message": "Sinh viên không có trong lớp này"}

@router.post("/api/courses/{course_id}/sessions")
async def create_session(course_id: int, session_data: CourseSessionCreate, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Kiểm tra lớp học
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")

    # Lưu vào database
    new_session = CourseSessionModel(
        course_id=course_id,
        date=session_data.date, 
        start_time=session_data.start_time,
        late_threshold_time=session_data.late_threshold_time
    )
    db.add(new_session)
    db.commit()
    return {"message": "Tạo buổi học thành công!", "session_id": new_session.id}

