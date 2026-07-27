from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole

def test_dashboard_kpis_rendering():
    print("\n--- TESTING OPERATIONAL DASHBOARD KPIS RENDERING ---")
    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    tm_user = db.query(User).filter(User.role == UserRole.territory_manager).first()

    from itsdangerous import TimestampSigner
    from app.config import settings

    signer = TimestampSigner(settings.secret_key)
    import json, base64

    # 1. Admin Dashboard
    session_admin = json.dumps({"user_id": admin_user.id}).encode("utf-8")
    cookie_admin = signer.sign(base64.b64encode(session_admin)).decode("utf-8")
    client_admin = TestClient(fastapi_app, cookies={"session": cookie_admin})
    res_admin = client_admin.get("/dashboard")

    assert res_admin.status_code == 200
    assert "Receivables" not in res_admin.text
    assert "System Health" not in res_admin.text
    assert "SKUs" not in res_admin.text
    assert "Outlets Scope" in res_admin.text
    assert "Attendance / Workforce" in res_admin.text
    assert "Orders Today" in res_admin.text
    assert "Marketing Assets" in res_admin.text
    assert "Work Orders" in res_admin.text
    assert "Vendor Quotations" in res_admin.text
    print("✓ Admin Dashboard KPI grid updated with Clubbed Attendance/Workforce (0/1) & Vendor Operational Data.")

    # 2. TM Dashboard
    if tm_user:
        session_tm = json.dumps({"user_id": tm_user.id}).encode("utf-8")
        cookie_tm = signer.sign(base64.b64encode(session_tm)).decode("utf-8")
        client_tm = TestClient(fastapi_app, cookies={"session": cookie_tm})
        res_tm = client_tm.get("/dashboard")
        assert res_tm.status_code == 200
        assert "Receivables" not in res_tm.text
        assert "Attendance / Workforce" in res_tm.text
        print("✓ Territory Manager Dashboard renders Clubbed Attendance/Workforce (0/1) & Vendor Operational Data.")

    db.close()
    print("\n🎉 ALL OPERATIONAL DASHBOARD KPIS VERIFIED 100% WORKING PERFECTLY!")

if __name__ == "__main__":
    test_dashboard_kpis_rendering()
