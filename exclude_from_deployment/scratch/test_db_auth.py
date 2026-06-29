import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from app.database import SessionLocal
from app.services.auth import authenticate_user

db = SessionLocal()
try:
    user = authenticate_user(db, "john_rep", "John@123")
    print(f"Result for 'john_rep' and 'John@123': {user}")
    if user:
        print(f"User details: id={user.id}, username={user.username}, is_active={user.is_active}, role={user.role}")
    else:
        # Let's inspect the user record directly
        from app.models.user import User
        u = db.query(User).filter(User.username == "john_rep").first()
        if u:
            print(f"Direct DB query: username={u.username}, is_active={u.is_active}, role={u.role}")
            from app.utils.security import verify_password
            print(f"Password verify result: {verify_password('John@123', u.hashed_password)}")
        else:
            print("User 'john_rep' not found in database!")
finally:
    db.close()
