from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.geography import Geography, GeoLevel
from app.utils.security import create_access_token, hash_password

client = TestClient(fastapi_app)

def test_restricted_module_access():
    print("\n--- TESTING EXPENSES, TIMESHEETS & MATERIAL REQUEST ACCESS RESTRICTION ---")
    db = SessionLocal()
    try:
        # 1. Setup Geographies
        zone_geo = db.query(Geography).filter(Geography.level == GeoLevel.zone).first()
        if not zone_geo:
            zone_geo = Geography(name="North Zone", code="NZ", level=GeoLevel.zone)
            db.add(zone_geo)
            db.commit()
            db.refresh(zone_geo)

        region_geo = db.query(Geography).filter(Geography.level == GeoLevel.region).first()
        if not region_geo:
            region_geo = Geography(name="South Region", code="SR", level=GeoLevel.region, parent_id=zone_geo.id)
            db.add(region_geo)
            db.commit()
            db.refresh(region_geo)

        territory_geo = db.query(Geography).filter(Geography.level == GeoLevel.territory).first()
        if not territory_geo:
            territory_geo = Geography(name="Local Territory", code="LT", level=GeoLevel.territory, parent_id=region_geo.id)
            db.add(territory_geo)
            db.commit()
            db.refresh(territory_geo)

        # 2. Test Admin Access
        admin_user = db.query(User).filter(User.role == UserRole.admin).first()
        if not admin_user:
            admin_user = User(
                username="admin",
                full_name="System Admin",
                email="admin@safar.com",
                hashed_password=hash_password("adminpass"),
                role=UserRole.admin,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        assert admin_user.can_access_restricted_modules == True
        print("✓ Admin user has full access to restricted modules.")

        # 3. Test TM with Region Geography
        tm_region = db.query(User).filter(User.username == "tm_region_test").first()
        if not tm_region:
            tm_region = User(
                username="tm_region_test",
                full_name="Region Manager",
                email="tm_region@safar.com",
                hashed_password=hash_password("tmpassword"),
                role=UserRole.territory_manager,
                geography_id=region_geo.id,
                is_active=True
            )
            db.add(tm_region)
            db.commit()
            db.refresh(tm_region)
        assert tm_region.can_access_restricted_modules == True
        print(f"✓ Territory Manager assigned to Region ('{region_geo.name}') HAS access.")

        # 4. Test TM with Territory Geography
        tm_territory = db.query(User).filter(User.username == "tm_territory_test").first()
        if not tm_territory:
            tm_territory = User(
                username="tm_territory_test",
                full_name="Territory Manager Low",
                email="tm_territory@safar.com",
                hashed_password=hash_password("tmpassword"),
                role=UserRole.territory_manager,
                geography_id=territory_geo.id,
                is_active=True
            )
            db.add(tm_territory)
            db.commit()
            db.refresh(tm_territory)
        assert tm_territory.can_access_restricted_modules == False
        print(f"✓ Territory Manager assigned to Territory ('{territory_geo.name}') IS BLOCKED.")

        # 5. Test Field Rep Access
        rep = db.query(User).filter(User.role == UserRole.field_rep).first()
        if not rep:
            rep = User(
                username="rep1",
                full_name="Field Rep 1",
                email="rep1@safar.com",
                hashed_password=hash_password("reppassword"),
                role=UserRole.field_rep,
                is_active=True
            )
            db.add(rep)
            db.commit()
            db.refresh(rep)
        assert rep.can_access_restricted_modules == False
        print("✓ Field Rep IS BLOCKED from restricted modules.")

        # 6. Test API endpoints enforcement for Field Rep
        rep_token = create_access_token({"sub": str(rep.id), "role": rep.role.value})
        headers = {"Authorization": f"Bearer {rep_token}"}

        res_exp = client.get("/api/v1/expenses/my", headers=headers)
        assert res_exp.status_code == 403
        print("✓ Field Rep GET /api/v1/expenses/my -> 403 Forbidden")

        res_mr = client.get("/api/v1/material-requests/my", headers=headers)
        assert res_mr.status_code == 403
        print("✓ Field Rep GET /api/v1/material-requests/my -> 403 Forbidden")

        res_exp_post = client.post("/api/v1/expenses?category=travel&amount=500", headers=headers)
        assert res_exp_post.status_code == 403
        print("✓ Field Rep POST /api/v1/expenses -> 403 Forbidden")

        # 7. Test API endpoints enforcement for Region TM
        tm_token = create_access_token({"sub": str(tm_region.id), "role": tm_region.role.value})
        headers_tm = {"Authorization": f"Bearer {tm_token}"}
        res_exp_tm = client.get("/api/v1/expenses/my", headers=headers_tm)
        assert res_exp_tm.status_code == 200
        print("✓ Region TM GET /api/v1/expenses/my -> 200 OK")

        print("\n🎉 ALL RESTRICTED MODULE ACCESS RULES VERIFIED SUCCESSFULLY!")

    finally:
        db.close()

if __name__ == "__main__":
    test_restricted_module_access()
