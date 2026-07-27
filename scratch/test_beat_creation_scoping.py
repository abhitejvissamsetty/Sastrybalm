from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.geography import Geography, GeoLevel
from itsdangerous import TimestampSigner
from app.config import settings
import json, base64

def test_beat_creation_scoping():
    print("\n--- TESTING BEAT CREATION SCOPING & PERMISSION RULES ---")
    db = SessionLocal()
    signer = TimestampSigner(settings.secret_key)

    # 1. Admin
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    assert admin_user is not None
    session_admin = json.dumps({"user_id": admin_user.id}).encode("utf-8")
    cookie_admin = signer.sign(base64.b64encode(session_admin)).decode("utf-8")
    client_admin = TestClient(fastapi_app, cookies={"session": cookie_admin})

    res_admin_new = client_admin.get("/master-data/beats/new")
    assert res_admin_new.status_code == 200
    print("✓ Admin CAN access /master-data/beats/new page.")

    # 2. Regional TM (Region or Zone)
    regional_geo = db.query(Geography).filter(Geography.level == GeoLevel.region).first()
    assert regional_geo is not None
    tm_regional = db.query(User).filter(User.role == UserRole.territory_manager, User.geography_id == regional_geo.id).first()
    if not tm_regional:
        tm_regional = db.query(User).filter(User.role == UserRole.territory_manager).first()
        tm_regional.geography_id = regional_geo.id
        db.commit()

    session_tm = json.dumps({"user_id": tm_regional.id}).encode("utf-8")
    cookie_tm = signer.sign(base64.b64encode(session_tm)).decode("utf-8")
    client_tm = TestClient(fastapi_app, cookies={"session": cookie_tm})

    res_tm_new = client_tm.get("/master-data/beats/new")
    assert res_tm_new.status_code == 200
    print(f"✓ Territory Manager '{tm_regional.username}' (Geography = Region) CAN access /master-data/beats/new page.")

    # 3. Sub-Regional TM (Territory level below Region)
    territory_geo = db.query(Geography).filter(Geography.level == GeoLevel.territory).first()
    assert territory_geo is not None
    tm_sub = db.query(User).filter(User.role == UserRole.territory_manager, User.username == "tm_sub_test").first()
    if not tm_sub:
        tm_sub = User(
            username="tm_sub_test",
            email="tm_sub_test@safar.com",
            full_name="Sub Regional TM",
            hashed_password="test_hash",
            role=UserRole.territory_manager,
            geography_id=territory_geo.id,
            is_active=True
        )
        db.add(tm_sub)
        db.commit()
    else:
        tm_sub.geography_id = territory_geo.id
        db.commit()

    session_tm_sub = json.dumps({"user_id": tm_sub.id}).encode("utf-8")
    cookie_tm_sub = signer.sign(base64.b64encode(session_tm_sub)).decode("utf-8")
    client_tm_sub = TestClient(fastapi_app, cookies={"session": cookie_tm_sub})

    res_tm_sub = client_tm_sub.get("/master-data/beats/new")
    assert res_tm_sub.status_code == 403
    print(f"✓ Territory Manager '{tm_sub.username}' (Geography = Territory < Region) BLOCKED with HTTP 403 Access Denied.")

    # 4. Field Rep
    field_rep = db.query(User).filter(User.role == UserRole.field_rep).first()
    assert field_rep is not None
    session_rep = json.dumps({"user_id": field_rep.id}).encode("utf-8")
    cookie_rep = signer.sign(base64.b64encode(session_rep)).decode("utf-8")
    client_rep = TestClient(fastapi_app, cookies={"session": cookie_rep})

    res_rep_new = client_rep.get("/master-data/beats/new")
    assert res_rep_new.status_code == 403
    print(f"✓ Field Rep '{field_rep.username}' BLOCKED with HTTP 403 Access Denied.")

    db.close()
    print("\n🎉 BEAT CREATION SCOPING RULES 100% VERIFIED WORKING PERFECTLY!")

if __name__ == "__main__":
    test_beat_creation_scoping()
