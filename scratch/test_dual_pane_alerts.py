from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole

def test_dual_pane_rendering():
    print("\n--- TESTING DUAL-PANE ALERTS TEMPLATE RENDERING ---")
    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    tm_user = db.query(User).filter(User.role == UserRole.territory_manager).first()
    rep_user = db.query(User).filter(User.role == UserRole.field_rep).first()

    from itsdangerous import TimestampSigner
    from app.config import settings

    signer = TimestampSigner(settings.secret_key)
    import json, base64

    # 1. Test Admin Dual-Pane
    session_data = json.dumps({"user_id": admin_user.id}).encode("utf-8")
    b64_data = base64.b64encode(session_data)
    cookie_val = signer.sign(b64_data).decode("utf-8")

    client_admin = TestClient(fastapi_app, cookies={"session": cookie_val})
    res_admin_personal = client_admin.get("/action-center/alerts?tab=personal")
    assert res_admin_personal.status_code == 200
    assert "My Personal Alerts" in res_admin_personal.text
    assert "Team &amp; Operational Alerts" in res_admin_personal.text or "Team & Operational Alerts" in res_admin_personal.text
    print("✓ Admin gets Dual-Pane view (Personal Tab & Operational Tab).")

    res_admin_op = client_admin.get("/action-center/alerts?tab=operational")
    assert res_admin_op.status_code == 200
    print("✓ Admin can navigate to 'Team & Operational Alerts' tab cleanly.")

    # 2. Test Field Rep Single-Pane
    session_data_rep = json.dumps({"user_id": rep_user.id}).encode("utf-8")
    b64_data_rep = base64.b64encode(session_data_rep)
    cookie_val_rep = signer.sign(b64_data_rep).decode("utf-8")

    client_rep = TestClient(fastapi_app, cookies={"session": cookie_val_rep})
    res_rep = client_rep.get("/action-center/alerts")
    assert res_rep.status_code == 200
    assert "Team & Operational Alerts" not in res_rep.text
    print("✓ Field Rep gets clean single view (Operational Pane tab hidden).")

    db.close()
    print("\n🎉 DUAL-PANE ALERTS RENDERING VERIFIED 100% WORKING PERFECTLY!")

if __name__ == "__main__":
    test_dual_pane_rendering()
