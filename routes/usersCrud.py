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

@router.get("/user-list", response_model=list[schemas.AddUserResponse])
def get_user_list(db: Session = Depends(get_db)):
    userlist = db.query(models.UserList).all()
    return [
        schemas.AddUserResponse(
            id=a.id, user_id=a.user_id, user_role=a.user_role, username=a.username
        )
        for a in userlist
    ]

@router.post("/create-user")
def create_user(user: schemas.AddUserRequest, db: Session = Depends(get_db)):
    existing_user = db.query(models.UserList).filter(models.UserList.user_id == user.user_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    new_user = models.UserList(username=user.username, user_id=user.user_id, user_role=user.user_role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"data": new_user, "message": "User created successfully"}

@router.delete("/delete-all-user")
def delete_all_users(db: Session = Depends(get_db)):
    deleted_count = db.query(models.UserList).delete()
    db.execute(text("""
        SELECT setval(
            pg_get_serial_sequence('userList', 'id'),
            COALESCE((SELECT MAX(id) FROM userList), 0) + 1,
            false
        );
    """))
    db.commit()
    return {"message": f"Deleted all users ({deleted_count} records)."}
