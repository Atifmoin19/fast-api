from fastapi import FastAPI, HTTPException, Depends
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

    # Create the book
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

@app.get("/authors/", response_model=list[schemas.AuthorResponse])
def list_authors(db: Session = Depends(get_db)):
    authors = db.query(models.Author).all()
    return [schemas.AuthorResponse(id=a.id, author_name=a.author_name) for a in authors]
