from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

import os
from dotenv import load_dotenv

# from .env import DATABASE_USERNAME, POSTGRES_PASSWORD, DATABASE_HOST, DATABASE_PORT, DATABASE_NAME
load_dotenv()

DATABASE_USERNAME = os.getenv("DATABASE_USERNAME")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_PORT = os.getenv("DATABASE_PORT")
DATABASE_NAME = os.getenv("DATABASE_NAME")


if not DATABASE_USERNAME:
    user = os.getenv("DATABASE_USER", "postgres")
if not POSTGRES_PASSWORD:
    pwd = os.getenv("POSTGRES_PASSWORD", "postgres")  # quid des secrets ?
if not DATABASE_HOST:
    host = os.getenv("DATABASE_HOST", "localhost")
if not DATABASE_PORT:
    port = os.getenv("DATABASE_PORT", "5432")
if not DATABASE_NAME:
    name = os.getenv("DATABASE_NAME", "forecast_database")


SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{DATABASE_USERNAME}:{POSTGRES_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
# SQLALCHEMY_DATABASE_URL = 'postgresql://postgres:Bright#1270@localhost/forecast_database'

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
