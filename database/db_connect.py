from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models.schemas import Base

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

    def get_session(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()