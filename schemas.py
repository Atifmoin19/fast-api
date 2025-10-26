from pydantic import BaseModel

# ---------------------------
# Author Schemas
# ---------------------------
class AuthorCreate(BaseModel):
    author_name: str

class AuthorResponse(BaseModel):
    id: int
    author_name: str

    class Config:
        from_attributes = True  # For Pydantic v2, replaces orm_mode


# ---------------------------
# Book Schemas
# ---------------------------
class BookCreate(BaseModel):
    title: str
    author_name: str  # Name of the author
    published_year: int   # new field
    genre: str            # new field

class BookResponse(BaseModel):
    id: int
    title: str
    author_name: str
    published_year: int
    genre: str

    class Config:
        from_attributes = True
