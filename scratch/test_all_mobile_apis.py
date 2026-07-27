import os
import sys
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Setup in-memory SQLite DB
from app.models.base import Base
import app.models  # load all models
from app.database import SessionLocal
from app.dependencies import get_db
from app.main import app
from app.utils.security import hash_password
from app.models.user import User, UserRole
from app.models.beat import Beat, BeatType
from app.models.outlet import Outlet, OutletStatus
from app.models.product import Product
from app.models.company import SystemConfiguration, PaymentMode

# In-memory SQLite engine for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def setup_test_data():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test user
    user = User(
        username="testrep",
        hashed_password=hash_password("password123"),
        full_name="Test Field Rep",
        email="rep@example.com",
        role=UserRole.field_rep,
        is_active=True,
    )
    db.add(user)
    
    # Create SystemConfiguration
    sys_config = SystemConfiguration(
        id=1,
        payment_mode=PaymentMode.cash_and_online,
        denomination_mandatory=False,
        gps_threshold_metres=100,
        sync_interval_seconds=300,
    )
    db.add(sys_config)

    # Create Beat
    beat = Beat(
        name="Central Beat",
        code="BEAT01",
        beat_type=BeatType.GT,
        is_active=True,
    )
    db.add(beat)
    db.flush()

    # Create Outlet
    outlet = Outlet(
        name="Raj Medicals",
        code="OUT0001",
        beat_id=beat.id,
        status=OutletStatus.active,
        mobile="9876543210",
        gps_lat=12.9716,
        gps_lng=77.5946,
    )
    db.add(outlet)

    # Create Product
    product = Product(
        name="Safar 50g",
        sku="SB50G",
        mrp=100.0,
        gst_rate=12.0,
        is_active=True,
    )
    db.add(product)
    
    db.commit()
    db.close()

def run_tests():
    print("Setting up test database...")
    setup_test_data()
    
    results = []

    def test(name, func):
        try:
            func()
            print(f"  ✓ {name}")
            results.append((name, True, None))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"  ✗ {name}: {e}\n{tb}")
            results.append((name, False, str(e)))

    print("\nRunning Mobile API Tests:")
    token = None
    headers = {}

    # 1. Login
    def t1():
        nonlocal token, headers
        res = client.post("/api/v1/auth/token", json={"username": "testrep", "password": "password123"})
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        data = res.json()
        assert "access_token" in data
        assert data["username"] == "testrep"
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
    test("1. POST /auth/token (Login)", t1)

    # 2. Get me
    def t2():
        res = client.get("/api/v1/auth/me", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["username"] == "testrep"
    test("2. GET /auth/me", t2)

    # 3. System Config
    def t3():
        res = client.get("/api/v1/config", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert "payment_mode" in res.json()
    test("3. GET /config", t3)

    # 4. Geography Tree
    def t4():
        res = client.get("/api/v1/geography/tree", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert "tree" in res.json()
    test("4. GET /geography/tree", t4)

    # 5. List Beats
    def t5():
        res = client.get("/api/v1/beats", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert len(res.json()["items"]) >= 1
    test("5. GET /beats", t5)

    # 6. Beat Daily Plan
    def t6():
        res = client.get("/api/v1/beats/daily-plan?beat_id=1", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert len(res.json()["outlets"]) >= 1
    test("6. GET /beats/daily-plan", t6)

    # 7. List Outlets
    def t7():
        res = client.get("/api/v1/outlets", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert len(res.json()["items"]) >= 1
    test("7. GET /outlets", t7)

    # 8. Create Outlet
    def t8():
        payload = {
            "name": "New Shop",
            "beat_id": 1,
            "mobile": "9999988888",
            "channel": "GT"
        }
        res = client.post("/api/v1/outlets", json=payload, headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["name"] == "New Shop"
    test("8. POST /outlets", t8)

    # 9. List Products
    def t9():
        res = client.get("/api/v1/products", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert len(res.json()["items"]) >= 1
    test("9. GET /products", t9)

    # 10. Attendance Today (Not checked in yet)
    def t10():
        res = client.get("/api/v1/attendance/today", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["checked_in"] == False
    test("10. GET /attendance/today (Before Checkin)", t10)

    # 11. Attendance Checkin
    def t11():
        res = client.post("/api/v1/attendance/checkin?gps_lat=12.9716&gps_lng=77.5946&address=Bangalore", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["status"] == "open"
    test("11. POST /attendance/checkin", t11)

    # 12. Log Visit
    visit_id = None
    def t12():
        nonlocal visit_id
        res = client.post("/api/v1/visits?outlet_id=1&gps_lat=12.9716&gps_lng=77.5946&purpose=sales", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        visit_id = res.json()["id"]
    test("12. POST /visits", t12)

    # 13. Visit Checkout
    def t13():
        res = client.post(f"/api/v1/visits/{visit_id}/checkout", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
    test("13. POST /visits/{id}/checkout", t13)

    # 14. Create Order
    order_id = None
    def t14():
        nonlocal order_id
        items = [{
            "product_id": 1,
            "quantity": 2,
            "unit_price": 100.0,
            "gst_rate": 12.0,
            "discount_pct": 0.0
        }]
        res = client.post("/api/v1/orders?outlet_id=1&beat_id=1&notes=urgent", json=items, headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        data = res.json()
        assert data["status"] == "draft"
        order_id = data["id"]
    test("14. POST /orders", t14)

    # 15. Submit Order
    def t15():
        res = client.patch(f"/api/v1/orders/{order_id}/submit", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["status"] in ("submitted", "confirmed")
    test("15. PATCH /orders/{id}/submit", t15)

    # 16. Get My Orders
    def t16():
        res = client.get("/api/v1/orders/my", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert len(res.json()["items"]) >= 1
    test("16. GET /orders/my", t16)

    # 17. Get Order Detail
    def t17():
        res = client.get(f"/api/v1/orders/{order_id}", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["id"] == order_id
    test("17. GET /orders/{id}", t17)

    # 18. Collect Payment
    payment_id = None
    def t18():
        nonlocal payment_id
        res = client.post(f"/api/v1/payments?outlet_id=1&amount=200.0&method=cash&order_id={order_id}&denom_100=2", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        payment_id = res.json()["id"]
    test("18. POST /payments", t18)

    # 19. Payment Submission
    def t19():
        payload = {
            "payment_ids": [payment_id],
            "notes": "EOD submission"
        }
        res = client.post("/api/v1/payment-submissions", json=payload, headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["payment_count"] == 1
    test("19. POST /payment-submissions", t19)

    # 20. Log Expense
    def t20():
        res = client.post("/api/v1/expenses?category=travel&amount=150.0&description=Bus+fare", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["status"] == "submitted"
    test("20. POST /expenses", t20)

    # 21. Material Request
    def t21():
        res = client.post("/api/v1/material-requests?outlet_id=1&description=Posters+needed&category=marketing", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["status"] in ("submitted", "approved")
    test("21. POST /material-requests", t21)

    # 22. Asset Capitalization
    def t22():
        res = client.post("/api/v1/asset-capitalizations?outlet_id=1&item_name=Cooler&quantity=1&deployed_by=rep", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["status"] in ("pending", "deployed")
    test("22. POST /asset-capitalizations", t22)

    # 23. Attendance Checkout
    def t23():
        res = client.post("/api/v1/attendance/checkout?gps_lat=12.9716&gps_lng=77.5946&notes=Done", headers=headers)
        assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
        assert res.json()["status"] == "closed"
    test("23. POST /attendance/checkout", t23)

    print("\n" + "="*50)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"SUMMARY: {passed} PASSED, {failed} FAILED out of {len(results)} tests.")
    print("="*50)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
