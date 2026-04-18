from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, JSON, Time, Table, Date
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
import enum
from datetime import datetime

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

class AttendanceStatus(enum.Enum):
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"

enrollments = Table(
    "enrollments",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("course_id", Integer, ForeignKey("courses.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20)) # 'admin', 'teacher', 'student'
    date_of_birth = Column(Date, nullable=True) # Ngày sinh
    student_code = Column(String(20), unique=True, nullable=True) # Ví dụ: 52400056
    face_embedding = Column(JSON, nullable=True)
    url_pic = Column(String(255), nullable=True)
    # Mối quan hệ
    courses_enrolled = relationship("Course", secondary=enrollments, back_populates="students")
    attendance_records = relationship("AttendanceRecord", back_populates="student")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    teacher_id = Column(Integer, ForeignKey("users.id"))
    
    # CÁC TRƯỜNG MỚI THÊM
    total_sessions = Column(Integer, default=15) # Tổng số buổi (VD: 15 buổi)
    absence_limit = Column(Integer, default=3)   # Số buổi tối đa được nghỉ (VD: 3)
    
    teacher = relationship("User", back_populates="managed_courses")
    students = relationship("User", secondary=enrollments, back_populates="courses_enrolled")
    sessions = relationship("Session", back_populates="course")

User.managed_courses = relationship("Course", back_populates="teacher")

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    date = Column(DateTime, nullable=False) 
    start_time = Column(Time, nullable=False) 
    late_threshold_time = Column(Time, nullable=False) 
    
    course = relationship("Course", back_populates="sessions")
    records = relationship("AttendanceRecord", back_populates="session")

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    student_id = Column(Integer, ForeignKey("users.id"))
    check_in_time = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(AttendanceStatus), nullable=False)
    
    session = relationship("Session", back_populates="records")
    student = relationship("User", back_populates="attendance_records")