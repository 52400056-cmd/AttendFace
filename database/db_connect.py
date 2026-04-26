from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models.schemas import Base, User  # Đã thêm User vào đây
import os

class db_connect:
    def __init__(self):
        self.DATABASE_URL = "postgresql://postgres:123456@db:5432/faceattend_db"
        
        self.engine = create_engine(self.DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            
        Base.metadata.create_all(bind=self.engine)
        print("Đã khởi tạo Database PostgreSQL và kích hoạt pgvector thành công!")
        self.seed_data_if_empty()

    def seed_data_if_empty(self):
        with self.SessionLocal() as session:
            if session.query(User).first() is None:
                try:
                    sql_file_path = os.path.join(os.path.dirname(__file__), "..", "db_init", "khoitao.sql")
                    if os.path.exists(sql_file_path):
                        with open(sql_file_path, "r", encoding="utf-8") as file:
                            sql_script = file.read()
                        
                        connection = self.engine.raw_connection()
                        try:
                            cursor = connection.cursor()
                            cursor.execute(sql_script)
                            connection.commit()
                            print("Nạp dữ liệu thành công!")
                        except Exception as e:
                            print(f"Lỗi khi chạy file SQL: {e}")
                        finally:
                            connection.close()
                    else:
                        print("Không tìm thấy file db_init/khoitao.sql!")
                except Exception as e:
                    print(f" Lỗi hệ thống khi nạp dữ liệu: {e}")

    def get_session(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()