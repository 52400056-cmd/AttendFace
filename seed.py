import random
from datetime import date
from database.db_connect import db_connect
from models.schemas import User, RoleEnum
from utils.security import get_password_hash
from sqlalchemy.orm import Session

def seed_data():
    # 1. Khởi tạo kết nối
    db_instance = db_connect()
    db: Session = next(db_instance.get_session())
    
    # 2. Danh sách 10 tên sinh viên khác nhau
    full_names = [
        "Nguyễn Văn An", "Lê Thị Bình", "Trần Minh Cường", "Phạm Hoàng Dung",
        "Hoàng Anh Tuấn", "Đặng Thu Thảo", "Bùi Tiến Dũng", "Ngô Thanh Vân",
        "Đỗ Hùng Dũng", "Võ Minh Thuận"
    ]
    
    # 3. Mật khẩu mặc định băm bằng bcrypt
    hashed_pw = get_password_hash("123456")
    
    print("Đang tạo dữ liệu sinh viên...")
    
    for i in range(10):
        # Tạo mã sinh viên ngẫu nhiên 5240xxxx
        random_suffix = random.randint(1000, 9999)
        st_code = f"5240{random_suffix}"
        
        # Kiểm tra trùng MSSV trước khi thêm (đảm bảo tính Unique của DB)
        if db.query(User).filter(User.student_code == st_code).first():
            continue

        new_student = User(
            full_name=full_names[i],
            email=f"{st_code}@student.tdtu.edu.vn",
            student_code=st_code, #
            hashed_password=hashed_pw,
            role="student", #
            date_of_birth=date(2006, random.randint(1, 12), random.randint(1, 28)), #
            url_pic=None #
        )
        
        db.add(new_student)
    
    try:
        db.commit()
        print("✅ Đã tạo thành công 10 sinh viên mẫu!")
    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi khi chèn dữ liệu: {e}")
    finally:
        db.close()
def seed_staff():
    db_instance = db_connect()
    db: Session = next(db_instance.get_session())
    

    
    staff_data = [
        User(
            full_name="Quản Trị Viên",
            email="admin@tdtu.edu.vn",
            student_code="admin", # Dùng làm tài khoản đăng nhập
            hashed_password=get_password_hash("admin"),
            role="admin"
        ),
        User(
            full_name="Giảng viên Khoa CNTT",
            email="teacher@tdtu.edu.vn",
            student_code="GV001", # Dùng làm tài khoản đăng nhập
            hashed_password=get_password_hash("GV001"),
            role="teacher"
        )
    ]
    
    try:
        # Kiểm tra xem tài khoản đã tồn tại chưa để tránh lỗi trùng lặp
        if not db.query(User).filter(User.student_code == "admin").first():
            db.add_all(staff_data)
            db.commit()
            print("✅ Đã tạo tài khoản Admin và Teacher thành công!")
        else:
            print("⚠️ Tài khoản đã tồn tại trong Database.")
    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi: {e}")
    finally:
        db.close()
        
if __name__ == "__main__":
    seed_data()
    seed_staff()