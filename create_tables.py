# create_tables.py
from database import engine, Base
from models import Book, Author

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")