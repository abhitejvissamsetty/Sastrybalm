from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.geography import Geography, GeoLevel
from app.routers.analytics import filter_alerts_for_user

def test_login_alerts_isolation():
    print("\n--- TESTING STRICT LOGIN & OTP ALERT PRIVACY ISOLATION ---")
    db = SessionLocal()
    try:
        # 1. Fetch Users
        admin_user = db.query(User).filter(User.role == UserRole.admin).first()
        tm_region = db.query(User).filter(User.role == UserRole.territory_manager, User.geography.has(level=GeoLevel.region)).first()
        rep_user = db.query(User).filter(User.role == UserRole.field_rep).first()

        # 2. Add a test OTP alert for rep_user
        test_login_alert = Alert(
            severity=AlertSeverity.info,
            alert_type=AlertType.custom,
            title=f"Login OTP for {rep_user.full_name}",
            message=f"OTP verification code for {rep_user.username}: 999999",
            user_id=rep_user.id
        )
        db.add(test_login_alert)
        db.commit()
        db.refresh(test_login_alert)

        # 3. Test Admin Access (Must see all)
        admin_alerts = filter_alerts_for_user(db.query(Alert), admin_user, db).all()
        admin_alert_ids = [a.id for a in admin_alerts]
        assert test_login_alert.id in admin_alert_ids
        print(f"✓ Admin CAN view Login/OTP alert #{test_login_alert.id}.")

        # 4. Test Rep's Own Access (Must see own)
        rep_alerts = filter_alerts_for_user(db.query(Alert), rep_user, db).all()
        rep_alert_ids = [a.id for a in rep_alerts]
        assert test_login_alert.id in rep_alert_ids
        print(f"✓ Field Rep '{rep_user.username}' CAN view their OWN Login/OTP alert.")

        # 5. Test Region TM Access (MUST NOT see foreign login/OTP alert)
        if tm_region:
            tm_alerts = filter_alerts_for_user(db.query(Alert), tm_region, db).all()
            tm_alert_ids = [a.id for a in tm_alerts]
            assert test_login_alert.id not in tm_alert_ids
            print(f"✓ Region TM '{tm_region.username}' CANNOT view foreign Login/OTP alert of '{rep_user.username}'.")

        # Cleanup test alert
        db.delete(test_login_alert)
        db.commit()

        print("\n🎉 LOGIN & OTP ALERT PRIVACY ISOLATION 100% VERIFIED!")

    finally:
        db.close()

if __name__ == "__main__":
    test_login_alerts_isolation()
