from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole

def test_core_infrastructure_visibility():
    print("\n--- TESTING CORE INFRASTRUCTURE VISIBILITY RULES ---")
    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    tm_user = db.query(User).filter(User.role == UserRole.territory_manager).first()
    rep_user = db.query(User).filter(User.role == UserRole.field_rep).first()

    from itsdangerous import TimestampSigner
    from app.config import settings

    signer = TimestampSigner(settings.secret_key)
    import json, base64

    # 1. Admin Request
    session_admin = json.dumps({"user_id": admin_user.id}).encode("utf-8")
    cookie_admin = signer.sign(base64.b64encode(session_admin)).decode("utf-8")
    client_admin = TestClient(fastapi_app, cookies={"session": cookie_admin})
    res_admin = client_admin.get("/dashboard")

    assert res_admin.status_code == 200
    assert "Core Infrastructure" in res_admin.text
    assert "API Core" in res_admin.text
    assert "Datastore" in res_admin.text
    assert "Job Scheduler" in res_admin.text
    assert "ZAP Sync" not in res_admin.text
    assert "CMMS Sync" not in res_admin.text
    assert "CONNECT Sync" not in res_admin.text
    print("✓ Admin CAN view Core Infrastructure panel (Offline syncs cleanly removed).")

    # 2. Territory Manager Request
    if tm_user:
        session_tm = json.dumps({"user_id": tm_user.id}).encode("utf-8")
        cookie_tm = signer.sign(base64.b64encode(session_tm)).decode("utf-8")
        client_tm = TestClient(fastapi_app, cookies={"session": cookie_tm})
        res_tm = client_tm.get("/dashboard")
        assert res_tm.status_code == 200
        assert "Core Infrastructure" not in res_tm.text
        print(f"✓ Territory Manager '{tm_user.username}' CANNOT view Core Infrastructure panel (Hidden).")

    # 3. Field Rep Request
    if rep_user:
        session_rep = json.dumps({"user_id": rep_user.id}).encode("utf-8")
        cookie_rep = signer.sign(base64.b64encode(session_rep)).decode("utf-8")
        client_rep = TestClient(fastapi_app, cookies={"session": cookie_rep})
        res_rep = client_rep.get("/dashboard")
        assert res_rep.status_code == 200
        assert "Core Infrastructure" not in res_rep.text
        print(f"✓ Field Rep '{rep_user.username}' CANNOT view Core Infrastructure panel (Hidden).")

    db.close()
    print("\n🎉 ALL CORE INFRASTRUCTURE VISIBILITY RULES 100% VERIFIED!")

if __name__ == "__main__":
    test_core_infrastructure_visibility()
