from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import models, schemas, database

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/books/", response_model=schemas.BookResponse)
def create_book(book: schemas.BookCreate, db: Session = Depends(get_db)):
    author = db.query(models.Author).filter_by(author_name=book.author_name).first()
    if not author:
        author = models.Author(author_name=book.author_name)
        db.add(author)
        db.commit()
        db.refresh(author)

    existing_book = db.query(models.Book).filter(models.Book.title == book.title).first()
    if existing_book:
        raise HTTPException(status_code=400, detail="Book already exists.")

    new_book = models.Book(
        title=book.title,
        author_id=author.id,
        published_year=book.published_year,
        genre=book.genre,
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    return schemas.BookResponse(
        id=new_book.id,
        title=new_book.title,
        author_name=author.author_name,
        published_year=new_book.published_year,
        genre=new_book.genre,
    )

@router.get("/books/", response_model=list[schemas.BookResponse])
def list_books(db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    return [
        schemas.BookResponse(
            id=b.id,
            title=b.title,
            author_name=db.query(models.Author).get(b.author_id).author_name
            if db.query(models.Author).get(b.author_id)
            else "Unknown",
            published_year=b.published_year or 0,
            genre=b.genre or "Unknown",
        )
        for b in books
    ]

@router.delete("/delete-all")
def delete_all_books(db: Session = Depends(get_db)):
    db.query(models.Book).delete()
    seq_name = db.execute(text("SELECT pg_get_serial_sequence('books', 'id')")).scalar()
    db.execute(text(f"ALTER SEQUENCE {seq_name} RESTART WITH 1"))
    db.commit()
    return {"message": "Deleted all records"}
