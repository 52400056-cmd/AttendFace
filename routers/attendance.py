from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import base64
from typing import Dict, List
from utils.ai import get_face_embedding
from sqlalchemy import text
from database.db_connect import db_connect
from models.schemas import Session as CourseSessionModel, AttendanceRecord, AttendanceStatus, Course
from utils.security import get_current_user
from datetime import timedelta

router = APIRouter(tags=["Attendance"])
db_instance = db_connect()
templates = Jinja2Templates(directory="templates")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: int):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: int):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)

    async def broadcast(self, message: dict, session_id: int):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()

@router.get("/sessions/{session_id}/attendance")
async def attendance_page(session_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        return RedirectResponse(url="/courses")
    
    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    if not session_obj:
        return RedirectResponse(url="/courses")
        
    if isinstance(session_obj.date, str):
        session_obj.display_date = session_obj.date.split("T")[0]
    else:
        session_obj.display_date = session_obj.date.strftime("%d/%m/%Y")

    try:
        records = db.query(AttendanceRecord).filter(AttendanceRecord.session_id == session_id).all()
        record_map = {r.student_id: r.status for r in records}
    except Exception as e:
        print("Bỏ qua lỗi dữ liệu DB cũ:", e)
        record_map = {}

    students_data = []
    for st in session_obj.course.students:
        raw_status = record_map.get(st.id)
        if raw_status:
            status_str = raw_status.value if hasattr(raw_status, 'value') else str(raw_status).split('.')[-1]
            if status_str.lower() in ["present", "có mặt"]:
                ui_status = "Có mặt"
            elif status_str.lower() in ["late", "đi trễ"]:
                ui_status = "Đi trễ"
            else:
                ui_status = "Vắng"
        else:
            ui_status = "Chưa điểm danh"

        students_data.append({
            "student_code": st.student_code,
            "full_name": st.full_name,
            "status": ui_status
        })

    return templates.TemplateResponse("attendance.html", {
        "request": request,
        "user": user,
        "session": session_obj,
        "students": students_data 
    })

@router.get("/sessions/{session_id}/camera")
async def camera_page(session_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    return templates.TemplateResponse("camera.html", {
        "request": request,
        "session": session_obj
    })

@router.websocket("/ws/attendance/{session_id}")
async def websocket_attendance(websocket: WebSocket, session_id: int, db: Session = Depends(db_instance.get_session)):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping": continue

            frame_data = data.split(",")[1]
            img_bytes = base64.b64decode(frame_data)
            face_vector = get_face_embedding(img_bytes)
            
            if face_vector is None:
                await websocket.send_json({"status": "unknown"})
                continue

            vector_str = str(face_vector)
            sql_query = text("""
                SELECT id, student_code, full_name, (face_embedding <=> CAST(:vec AS vector)) AS distance 
                FROM users 
                WHERE role = 'student' AND face_embedding IS NOT NULL
                ORDER BY distance ASC LIMIT 1
            """)
            
            result = db.execute(sql_query, {"vec": vector_str}).fetchone()
            MATCH_THRESHOLD = 0.55 
            
            if result and result.distance < MATCH_THRESHOLD:
                student_id = result.id
                
                existing_record = db.query(AttendanceRecord).filter_by(session_id=session_id, student_id=student_id).first()
                if existing_record:
                    existing_record.status = AttendanceStatus.PRESENT
                else:
                    new_record = AttendanceRecord(session_id=session_id, student_id=student_id, status=AttendanceStatus.PRESENT)
                    db.add(new_record)
                db.commit()

                await manager.broadcast({
                    "status": "success",
                    "student_code": result.student_code,
                    "student_name": result.full_name,
                    "distance": round(result.distance, 2) 
                }, session_id)
            else:
                await websocket.send_json({"status": "unknown"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        print(f"Lỗi hệ thống WebSocket AI: {e}")
        try: manager.disconnect(websocket, session_id)
        except: pass

@router.get("/api/courses/{course_id}/attendance-audit")
async def audit_attendance(course_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Không có quyền")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")

    banned_alerts = []
    
    for st in course.students:
        absent_count = db.query(AttendanceRecord).join(CourseSessionModel).filter(
            CourseSessionModel.course_id == course_id,
            AttendanceRecord.student_id == st.id,
            AttendanceRecord.status == AttendanceStatus.ABSENT
        ).count()
        if absent_count >= course.absence_limit:
            banned_alerts.append({
                "name": st.full_name,
                "code": st.student_code,
                "absent_count": absent_count
            })

    return {"banned_alerts": banned_alerts}

@router.post("/api/sessions/{session_id}/finalize")
async def finalize_attendance(session_id: int, request: Request, db: Session = Depends(db_instance.get_session)):
    user = get_current_user(request, db)
    if not user or user.role not in ['admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Không có quyền")

    session_obj = db.query(CourseSessionModel).filter(CourseSessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Không tìm thấy buổi học")

    course = session_obj.course
    students = course.students
    existing_records = db.query(AttendanceRecord).filter_by(session_id=session_id).all()
    record_map = {r.student_id: r for r in existing_records}

    for st in students:
        if st.id in record_map:
            record = record_map[st.id]
            if record.status == AttendanceStatus.PRESENT and record.check_in_time:
                local_check_in = record.check_in_time + timedelta(hours=7)
                if local_check_in.time() > session_obj.late_threshold_time:
                    record.status = AttendanceStatus.LATE
        else:
            new_record = AttendanceRecord(session_id=session_id, student_id=st.id, status=AttendanceStatus.ABSENT)
            db.add(new_record)

    db.flush()

    all_students_status = []

    for st in students:
        absent_count = db.query(AttendanceRecord).join(CourseSessionModel).filter(
            CourseSessionModel.course_id == course.id,
            AttendanceRecord.student_id == st.id,
            AttendanceRecord.status == AttendanceStatus.ABSENT
        ).count()

        is_banned = False
        if absent_count >= course.absence_limit:
            db.execute(
                text("UPDATE enrollments SET is_banned = true WHERE course_id = :cid AND student_id = :sid"),
                {"cid": course.id, "sid": st.id}
            )
            is_banned = True
        else:
            enroll_record = db.execute(
                text("SELECT is_banned FROM enrollments WHERE course_id = :cid AND student_id = :sid"),
                {"cid": course.id, "sid": st.id}
            ).fetchone()
            is_banned = enroll_record[0] if enroll_record else False

        all_students_status.append({
            "id": st.id,
            "name": st.full_name,
            "code": st.student_code,
            "absent_count": absent_count,
            "is_banned": is_banned
        })

    session_obj.is_closed = True
    db.commit()

    return {
        "message": "Đã chốt danh sách!",
        "course_name": course.name,
        "absence_limit": course.absence_limit,
        "students": all_students_status
    }
