from sqlalchemy import BigInteger, Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

# if you update any fields in the model you have to run command : ALTER TABLE

class Author(Base):
    __tablename__ = "author"

    id = Column[int](Integer, primary_key=True, index=True)
    author_name = Column(String, unique=True, index=True, nullable=False)

    books = relationship("Book", back_populates="author")

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    author_id = Column[int](Integer, ForeignKey("author.id"))
    published_year = Column[int](Integer)   # new column
    genre = Column(String)             # new column
    author = relationship("Author", back_populates="books")


class UserList(Base):
    __tablename__ ='userlist'

    id = Column(Integer, primary_key=True, index=True)
    username= Column(String, index=True, nullable=False)
    user_id = Column(BigInteger, index=True)
    user_role = Column(String, index=True, nullable=False)
    # user_token=Column(String, index=True,default='',nullable=True)
    # is_active=Column(Boolean,index=True,default=False)




