from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Author(Base):
    __tablename__ = "author"

    id = Column(Integer, primary_key=True, index=True)
    author_name = Column(String, unique=True, index=True, nullable=False)

    books = relationship("Book", back_populates="author")

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    author_id = Column(Integer, ForeignKey("author.id"))
    published_year = Column(Integer)   # new column
    genre = Column(String)             # new column
    author = relationship("Author", back_populates="books")
