# routers/courses.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from models.schemas import AttendanceRecord

from database.db_connect import db_connect
from models.schemas import User, Course, RoleEnum, Session as CourseSessionModel
from utils.security import get_current_user
from datetime import date, time, datetime

router = APIRouter(tags=["Courses Management"])
# Khởi tạo db_instance
db_instance = db_connect()
templates = Jinja2Templates(directory="templates")

# --- SCHEMAS ---
class CourseCreate(BaseModel):
    name: str
    total_sessions: int = 15
    absence_limit: int = 3

class StudentAttendanceUpdate(BaseModel):
    student_id: int
    status: str

class SessionUpdateDetails(BaseModel):
    date: date
    start_time: time
    late_threshold_time: time
    attendance: list[StudentAttendanceUpdate]

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
    
    now = datetime.now()
    for s in course.sessions:
        # --- BỘ LỌC AN TOÀN TRÁNH LỖI STRING CỦA SQLITE ---
        # 1. Xử lý Ngày
        if isinstance(s.date, str):
            s_date = datetime.strptime(s.date.split("T")[0], "%Y-%m-%d").date()
        else:
            s_date = s.date.date() if hasattr(s.date, 'date') else s.date
            
        # 2. Xử lý Giờ bắt đầu
        if isinstance(s.start_time, str):
            s_time = datetime.strptime(s.start_time, "%H:%M:%S").time()
        else:
            s_time = s.start_time
            
        # 3. Xử lý Giờ chốt trễ
        if isinstance(s.late_threshold_time, str):
            s_late = datetime.strptime(s.late_threshold_time, "%H:%M:%S").time()
        else:
            s_late = s.late_threshold_time

        # Tính toán mốc bắt đầu
        start_dt = datetime.combine(s_date, s_time)

        # ĐỊNH DẠNG SẴN NGÀY GIỜ ĐỂ ĐƯA RA HTML AN TOÀN
        s.display_date = s_date.strftime('%d/%m/%Y')
        s.display_start = s_time.strftime('%H:%M')
        s.display_late = s_late.strftime('%H:%M')
        
        # LOGIC HIỂN THỊ UI
        if s.is_closed:
            s.ui_status = "Đã chốt"
            s.ui_color = "bg-secondary"
        elif now >= start_dt:
            s.ui_status = "Đã đến giờ"
            s.ui_color = "bg-success"
        else:
            s.ui_status = "Chưa đến giờ"
            s.ui_color = "bg-info text-dark"

        s.can_checkin = True

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
@router.get("/api/sessions/{session_id}/details")
async def get_session_details(session_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Không tìm thấy buổi học")

    course = session_obj.course
    records = db.query(AttendanceRecord).filter(AttendanceRecord.session_id == session_id).all()
    record_map = {r.student_id: r.status for r in records}

    student_data = []
    for st in course.students:
        student_data.append({
            "id": st.id,
            "student_code": st.student_code,
            "full_name": st.full_name,
            "status": record_map.get(st.id, "Vắng")
        })
    s_date = session_obj.date
    s_date_str = s_date.split("T")[0] if isinstance(s_date, str) else s_date.strftime("%Y-%m-%d")

    s_start = session_obj.start_time
    s_start_str = s_start[:5] if isinstance(s_start, str) else s_start.strftime("%H:%M")

    s_late = session_obj.late_threshold_time
    s_late_str = s_late[:5] if isinstance(s_late, str) else s_late.strftime("%H:%M")

    return {
        "date": s_date_str,
        "start_time": s_start_str,
        "late_threshold_time": s_late_str,
        "students": student_data
    }
@router.put("/api/sessions/{session_id}")
async def update_session_details(session_id: int, data: SessionUpdateDetails, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Không có quyền")

    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    
    # 1. Cập nhật thời gian
    session_obj.date = data.date
    session_obj.start_time = data.start_time
    session_obj.late_threshold_time = data.late_threshold_time

    # 2. Cập nhật trạng thái điểm danh thủ công
    for att in data.attendance:
        record = db.query(AttendanceRecord).filter_by(session_id=session_id, student_id=att.student_id).first()
        if record:
            record.status = att.status
        else:
            new_record = AttendanceRecord(session_id=session_id, student_id=att.student_id, status=att.status)
            db.add(new_record)

    db.commit()
    return {"message": "Đã lưu thay đổi thành công!"}
@router.post("/api/sessions/{session_id}/toggle-status")
async def toggle_session_status(session_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Không có quyền")

    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Không tìm thấy")

    session_obj.is_closed = not session_obj.is_closed 
    db.commit()
    
    msg = "Đã khóa buổi học" if session_obj.is_closed else "Đã mở lại buổi học"
    return {"message": msg}
# --- THÊM ROUTE HIỂN THỊ TRANG TẠO LỚP HỌC ---
@router.get("/add-course")
async def add_course_page(request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    
    # Bảo mật: Chỉ admin và giảng viên mới được vào trang này
    if not user or user.role not in ['admin', 'teacher']:
        return RedirectResponse(url="/login", status_code=302)
        
    return templates.TemplateResponse("add_course.html", {
        "request": request, 
        "user": user
    })