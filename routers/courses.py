from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import text
from database.db_connect import db_connect
from models.schemas import User, Course, RoleEnum, Session as CourseSessionModel, AttendanceRecord, AttendanceStatus
from utils.security import get_current_user
from datetime import date, time, datetime

router = APIRouter(tags=["Courses Management"])
db_instance = db_connect()
templates = Jinja2Templates(directory="templates")

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

@router.post("/api/courses")
async def create_course(request: Request, course_data: CourseCreate, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in [RoleEnum.ADMIN, RoleEnum.TEACHER]:
        raise HTTPException(status_code=403, detail="Bạn không có quyền tạo lớp học")

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
    student = db.query(User).filter(User.student_code == enroll_data.student_code).first()
    
    if not course or not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy")

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
    return templates.TemplateResponse("course_students.html", {"request": request, "user": user, "course": course, "students": course.students})

@router.get("/courses/{course_id}")
async def course_detail(course_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/login", status_code=302)
        
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not course:
        return RedirectResponse(url="/")

    if user.role == 'student':
        if course not in user.courses_enrolled:
            return RedirectResponse(url="/")

        history = []
        absent_count = 0

        for s in course.sessions:
            s_date = datetime.strptime(s.date.split("T")[0], "%Y-%m-%d").date() if isinstance(s.date, str) else (s.date.date() if hasattr(s.date, 'date') else s.date)
            record = db.query(AttendanceRecord).filter_by(session_id=s.id, student_id=user.id).first()
            
            ui_status = "Chưa điểm danh"
            ui_color = "bg-secondary opacity-75"
            
            if record:
                status_str = record.status.value if hasattr(record.status, 'value') else str(record.status).split('.')[-1]
                status_str = status_str.lower()
                
                if status_str in ["present", "có mặt"]:
                    ui_status, ui_color = "Có mặt", "bg-success"
                elif status_str in ["late", "đi trễ"]:
                    ui_status, ui_color = "Đi trễ", "bg-warning text-dark"
                else:
                    ui_status, ui_color = "Vắng", "bg-danger"
                    absent_count += 1
            elif s.is_closed:
                ui_status, ui_color = "Vắng", "bg-danger"
                absent_count += 1

            history.append({
                "date": s_date.strftime('%d/%m/%Y'),
                "start_time": s.start_time[:5] if isinstance(s.start_time, str) else s.start_time.strftime("%H:%M"),
                "status": ui_status,
                "color": ui_color
            })

        return templates.TemplateResponse("student_course_detail.html", {
            "request": request, 
            "user": user, 
            "course": course,
            "history": history,
            "absent_count": absent_count
        })

    if user.role != 'admin' and course.teacher_id != user.id:
        return RedirectResponse(url="/")
    
    now = datetime.now()
    for s in course.sessions:
        s_date = datetime.strptime(s.date.split("T")[0], "%Y-%m-%d").date() if isinstance(s.date, str) else (s.date.date() if hasattr(s.date, 'date') else s.date)
        s_time = datetime.strptime(s.start_time, "%H:%M:%S").time() if isinstance(s.start_time, str) else s.start_time
        s_late = datetime.strptime(s.late_threshold_time, "%H:%M:%S").time() if isinstance(s.late_threshold_time, str) else s.late_threshold_time

        s.display_date = s_date.strftime('%d/%m/%Y')
        s.display_start = s_time.strftime('%H:%M')
        s.display_late = s_late.strftime('%H:%M')
        
        start_dt = datetime.combine(s_date, s_time)
        if s.is_closed:
            s.ui_status, s.ui_color = "Đã chốt", "bg-secondary"
        elif now >= start_dt:
            s.ui_status, s.ui_color = "Đã đến giờ", "bg-success"
        else:
            s.ui_status, s.ui_color = "Chưa đến giờ", "bg-info text-dark"

    enroll_data = db.execute(
        text("SELECT student_id, is_banned FROM enrollments WHERE course_id = :cid"),
        {"cid": course.id}
    ).fetchall()
    ban_map = {r[0]: r[1] for r in enroll_data}

    for st in course.students:
        absent_count = db.query(AttendanceRecord).join(CourseSessionModel).filter(
            CourseSessionModel.course_id == course.id,
            AttendanceRecord.student_id == st.id,
            AttendanceRecord.status == AttendanceStatus.ABSENT
        ).count()
        
        st.absent_count = absent_count 
        st.is_banned = ban_map.get(st.id, False)

    return templates.TemplateResponse("course_detail.html", {
        "request": request, "user": user, "course": course, 
        "students": course.students, "sessions": course.sessions
    })

@router.get("/api/users/search")
async def search_students(q: str, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Forbidden")

    students = db.query(User).filter((User.role == 'student') & ((User.student_code.ilike(f"%{q}%")) | (User.full_name.ilike(f"%{q}%")))).limit(50).all()
    return [{"student_code": s.student_code, "full_name": s.full_name} for s in students]

@router.delete("/api/courses/{course_id}/students/{student_code}")
async def remove_student(course_id: int, student_code: str, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Forbidden")

    course = db.query(Course).filter(Course.id == course_id).first()
    student = db.query(User).filter(User.student_code == student_code).first()
    
    if student in course.students:
        course.students.remove(student)
        db.commit()
        return {"message": "Đã xóa"}
    return {"message": "Không tìm thấy"}

@router.post("/api/courses/{course_id}/sessions")
async def create_session(course_id: int, session_data: CourseSessionCreate, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Forbidden")

    new_session = CourseSessionModel(
        course_id=course_id,
        date=session_data.date, 
        start_time=session_data.start_time,
        late_threshold_time=session_data.late_threshold_time
    )
    db.add(new_session)
    db.commit()
    return {"message": "Thành công!", "session_id": new_session.id}

@router.get("/api/sessions/{session_id}/details")
async def get_session_details(session_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user: raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    records = db.query(AttendanceRecord).filter(AttendanceRecord.session_id == session_id).all()
    record_map = {r.student_id: r.status for r in records}

    DB_TO_UI_STATUS = {"PRESENT": "Có mặt", "LATE": "Đi trễ", "ABSENT": "Vắng", "present": "Có mặt", "late": "Đi trễ", "absent": "Vắng"}

    student_data = []
    for st in session_obj.course.students:
        raw_status = record_map.get(st.id)
        status_str = raw_status.value if hasattr(raw_status, 'value') else str(raw_status).split('.')[-1] if raw_status else "absent"
        student_data.append({"id": st.id, "student_code": st.student_code, "full_name": st.full_name, "status": DB_TO_UI_STATUS.get(status_str, "Vắng")})

    return {
        "date": session_obj.date.split("T")[0] if isinstance(session_obj.date, str) else session_obj.date.strftime("%Y-%m-%d"),
        "start_time": session_obj.start_time[:5] if isinstance(session_obj.start_time, str) else session_obj.start_time.strftime("%H:%M"),
        "late_threshold_time": session_obj.late_threshold_time[:5] if isinstance(session_obj.late_threshold_time, str) else session_obj.late_threshold_time.strftime("%H:%M"),
        "students": student_data
    }

@router.put("/api/sessions/{session_id}")
async def update_session_details(session_id: int, data: SessionUpdateDetails, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Không có quyền")

    UI_TO_ENUM = {
        "Có mặt": AttendanceStatus.PRESENT,
        "Đi trễ": AttendanceStatus.LATE,
        "Vắng": AttendanceStatus.ABSENT
    }

    try:
        session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
        session_obj.date = data.date
        session_obj.start_time = data.start_time
        session_obj.late_threshold_time = data.late_threshold_time

        for att in data.attendance:
            db_enum_status = UI_TO_ENUM.get(att.status, AttendanceStatus.ABSENT)
            record = db.query(AttendanceRecord).filter_by(session_id=session_id, student_id=att.student_id).first()
            if record:
                record.status = db_enum_status
            else:
                db.add(AttendanceRecord(session_id=session_id, student_id=att.student_id, status=db_enum_status))

        db.commit()

        for att in data.attendance:
            absent_count = db.query(AttendanceRecord).join(CourseSessionModel).filter(
                CourseSessionModel.course_id == session_obj.course_id,
                AttendanceRecord.student_id == att.student_id,
                AttendanceRecord.status == AttendanceStatus.ABSENT
            ).count()

            if absent_count >= session_obj.course.absence_limit:
                db.execute(
                    text("UPDATE enrollments SET is_banned = true WHERE course_id = :cid AND student_id = :sid"),
                    {"cid": session_obj.course_id, "sid": att.student_id}
                )
            else:
                db.execute(
                    text("UPDATE enrollments SET is_banned = false WHERE course_id = :cid AND student_id = :sid"),
                    {"cid": session_obj.course_id, "sid": att.student_id}
                )
        
        db.commit()
        return {"message": "Thành công!"}
    except Exception as e:
        db.rollback() 
        raise HTTPException(status_code=400, detail=f"Lỗi DB: {str(e)}")

@router.post("/api/sessions/{session_id}/toggle-status")
async def toggle_session_status(session_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    session_obj.is_closed = not session_obj.is_closed 
    db.commit()
    return {"message": "Thành công"}

@router.get("/add-course")
async def add_course_page(request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("add_course.html", {"request": request, "user": user})
@router.post("/api/courses/{course_id}/students/{student_id}/toggle-ban")
async def toggle_student_ban(course_id: int, student_id: int, payload: dict, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Không có quyền")
    
    db.execute(
        text("UPDATE enrollments SET is_banned = :banned WHERE course_id = :cid AND student_id = :sid"),
        {"banned": payload.get("is_banned", False), "cid": course_id, "sid": student_id}
    )
    db.commit()
    return {"message": "Cập nhật thành công"}