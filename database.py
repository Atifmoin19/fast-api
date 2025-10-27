import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()
# Database URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") 
print(SQLALCHEMY_DATABASE_URL,'======================>==================')

# SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()
