from typing import Optional
from fastapi import  FastAPI, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
import models, database, schemas

# Create all tables (if they don't exist)
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Dependency to get DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/books/", response_model=schemas.BookResponse)
def create_book(book: schemas.BookCreate, db: Session = Depends(get_db)):
    # Check if author exists
    author = db.query(models.Author).filter_by(author_name=book.author_name).first()
    if not author:
        author = models.Author(author_name=book.author_name)
        db.add(author)
        db.commit()
        db.refresh(author)

    existing_book = db.query(models.Book).filter(models.Book.title == book.title).first()
    print(existing_book,'------------------------------')
    if existing_book:
       raise HTTPException(status_code=400, detail="Book already exists.")
    new_book = models.Book(title=book.title, author_id=author.id,   published_year=book.published_year,
        genre=book.genre                      )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    # Return response including author_name
    return schemas.BookResponse(
        id=new_book.id,
        title=new_book.title,
        author_name=author.author_name,
        published_year=new_book.published_year,
        genre=new_book.genre
    )

@app.get("/books/", response_model=list[schemas.BookResponse])
def list_books(db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    response = []
    for book in books:
        author = db.query(models.Author).filter_by(id=book.author_id).first()
        response.append(schemas.BookResponse(
            id=book.id,
            title=book.title,
            author_name=author.author_name if author else "Unknown",
            published_year=book.published_year or 0,
            genre=book.genre or "Unknown"
        ))
    return response

@app.delete("/delete-books")
def delete_book(book:schemas.BookResponse,db: Session = Depends(get_db)):
    new_book = db.query(models.Book).filter(models.Book.id == book.id).first()
    if not new_book:
        return {"error":"No record found for this book"}
    db.delete(new_book)
    db.commit()
    return {"message":'Deleted Record',"data":new_book}

@app.delete("/delete-all")
def delete_book(db: Session = Depends(get_db)):
    db.query(models.Book).delete()
    seq_name = db.execute(text("SELECT pg_get_serial_sequence('books', 'id')")).scalar()
    db.execute(text(f"ALTER SEQUENCE {seq_name} RESTART WITH 1"))
    db.commit()
    return {"message":'Deleted Record'}


@app.get("/authors/", response_model=list[schemas.AuthorResponse])
def list_authors(db: Session = Depends(get_db)):
    authors = db.query(models.Author).all()
    return [schemas.AuthorResponse(id=a.id, author_name=a.author_name) for a in authors]

@app.get('/user-list',response_model=list[schemas.AddUserResponse])
def get_user_list(db: Session = Depends(get_db)):
    userlist = db.query(models.UserList).all()
    return [schemas.AddUserResponse(id=a.id,user_id=a.user_id,user_role=a.user_role,username=a.username) for a in userlist]

@app.post("/create-user")
def create_user(user:schemas.AddUserRequest, db: Session = Depends(get_db)):
    existing_user=  db.query(models.UserList).filter(models.UserList.user_id == user.user_id).first()
    if existing_user:
       raise HTTPException(status_code=400, detail="User already exists.")
    new_user = models.UserList(username=user.username,user_id=user.user_id,user_role=user.user_role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"data":new_user,"message":"user created successfully"}

@app.delete("/delete-all-user")
def delete_user(user:Optional[schemas.AddUserRequest] = None, db: Session = Depends(get_db)):
    if not user:
        deleted_count = db.query(models.UserList).delete()
        sql = text(f"""
            SELECT setval(
            pg_get_serial_sequence('userList', 'id'),
            COALESCE((SELECT MAX(id) FROM userList), 0) + 1,
            false
        );
        """)
        db.execute(sql)
        db.commit()
        return {"message": f"Deleted all users ({deleted_count} records)."}
    existing_user = (
        db.query(models.UserList)
        .filter(models.UserList.user_id == user.user_id)
        .first()
    )
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(existing_user)
    sql = text(f"""
            SELECT setval(
            pg_get_serial_sequence('userList', 'id'),
            COALESCE((SELECT MAX(id) FROM userList), 0) + 1,
            false
    );
    """)
    db.execute(sql)
    db.commit()
    return {"message":'Deleted Record'}


    

    

    