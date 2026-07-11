import os
from dotenv import load_dotenv
from psycopg2 import pool
from fastapi import HTTPException
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

# Read from environment variables, fallback to local Docker defaults
DB_USER = os.environ.get("POSTGRES_USER")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT",)
DB_NAME = os.environ.get("POSTGRES_DB")

# Sqlalchemy orm setup for all the models
# ---------------------------------------
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# raw psycopg2 setup for the routes
# ---------------------------------
try:
    connection_pool = pool.ThreadedConnectionPool(
        minconn=1, maxconn=20,
        user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT, database=DB_NAME
    )
    print("✅ Successfully connected to PostgreSQL Pool")
except Exception as e:
    print(f"🚨 Failed to initialize database pool: {e}")
    connection_pool = None


def get_db_connection():
    if not connection_pool:
        return None
    try:
        return connection_pool.getconn()
    except Exception as e:
        print(f"🚨 Failed to get connection from pool: {e}")
        return None

def release_db_connection(conn):
    if connection_pool and conn:
        connection_pool.putconn(conn)

def get_db_cursor():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        release_db_connection(conn)

@contextmanager
def db_cursor_context():
    conn = get_db_connection()
    if not conn:
        yield None
        return
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        release_db_connection(conn)