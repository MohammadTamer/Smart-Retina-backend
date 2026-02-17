from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()
db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "smart_retina_db")

encoded_password = quote_plus(db_password)
print(encoded_password)
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:3306/{db_name}"
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the .env file")

# pool_pre_ping=True is important for MySQL to handle "server has gone away" errors
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,pool_pre_ping=True)

# each request will create a new session instance from this class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# create the Base class to make the domain entities inherit from it
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()