from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole

def test_403_rendering():
    db = SessionLocal()
    rep = db.query(User).filter(User.role == UserRole.field_rep).first()
    db.close()

    # Create signed session cookie for rep
    from itsdangerous import TimestampSigner
    from app.config import settings

    signer = TimestampSigner(settings.secret_key)
    import json, base64
    session_data = json.dumps({"user_id": rep.id}).encode("utf-8")
    b64_data = base64.b64encode(session_data)
    cookie_val = signer.sign(b64_data).decode("utf-8")

    client = TestClient(fastapi_app, cookies={"session": cookie_val})
    res = client.get("/operations/expenses")
    print("Status Code:", res.status_code)
    assert res.status_code == 403
    assert "403 Restricted" in res.text
    assert "Access Denied" in res.text
    print("✓ 403 Access Denied template rendered flawlessly!")

if __name__ == "__main__":
    test_403_rendering()
