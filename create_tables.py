# create_tables.py
from database import engine, Base
from models import Book, Author,UserList

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")