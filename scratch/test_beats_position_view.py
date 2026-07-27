from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.beat import Beat
from app.config import settings
from itsdangerous import TimestampSigner
import json, base64

def test_beats_position_column():
    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    assert admin_user is not None

    signer = TimestampSigner(settings.secret_key)
    session_data = json.dumps({"user_id": admin_user.id}).encode("utf-8")
    cookie_val = signer.sign(base64.b64encode(session_data)).decode("utf-8")

    client = TestClient(app, cookies={"session": cookie_val})
    response = client.get("/master-data/beats")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    html = response.text

    assert "Position" in html, "Position column header missing"
    assert "Unassigned" in html, "Unassigned badge missing for beat with no position"
    assert "EAST BHUBANESWAR" in html, "Position name missing for assigned beat"

    print("✓ Beats List View Position column test PASSED!")

if __name__ == "__main__":
    test_beats_position_column()
