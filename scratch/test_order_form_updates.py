from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.order import Order, OrderType
from app.models.outlet import Outlet, OutletStatus
from app.models.local_distribution import LocalChannelPartner
from app.models.product import Product, ProductCategory
from itsdangerous import TimestampSigner
from app.config import settings
import json, base64

def test_order_form_updates():
    print("\n--- TESTING NEW ORDER FORM & ORDER TYPE UPDATES ---")
    db = SessionLocal()
    signer = TimestampSigner(settings.secret_key)

    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    assert admin_user is not None

    session_admin = json.dumps({"user_id": admin_user.id}).encode("utf-8")
    cookie_admin = signer.sign(base64.b64encode(session_admin)).decode("utf-8")
    client_admin = TestClient(fastapi_app, cookies={"session": cookie_admin})

    # 1. Test GET /operations/orders/new rendering
    res = client_admin.get("/operations/orders/new")
    assert res.status_code == 200
    assert "Order Type" in res.text
    assert "Flow Type" not in res.text
    assert "Sales Scope Confined" in res.text
    print("✓ GET /operations/orders/new renders with Order Type and without Flow Type.")

    # 2. Test Sales Product Scope Filtering
    sales_products = db.query(Product).filter(Product.is_active == True, Product.category_type == ProductCategory.sales).all()
    non_sales_products = db.query(Product).filter(Product.is_active == True, Product.category_type != ProductCategory.sales).all()
    
    for sp in sales_products:
        assert f'>{sp.name}</option>' in res.text
    for nsp in non_sales_products:
        assert f'>{nsp.name}</option>' not in res.text
    print(f"✓ Confined products dropdown to Sales Category ({len(sales_products)} sales products included, {len(non_sales_products)} non-sales excluded).")

    # 3. Test POST /operations/orders/new creation with OrderType
    outlet = db.query(Outlet).first()
    cp = db.query(LocalChannelPartner).first()
    print(f"DEBUG: outlet={outlet}, cp={cp}, sales_products_len={len(sales_products)}")
    
    if not cp:
        cp = LocalChannelPartner(name="Test Partner", partner_type="distributor", code="CP_TEST_99", is_active=True)
        db.add(cp)
        db.commit()
    if not outlet:
        outlet = Outlet(name="Test Outlet", code="OUT_TEST_99", status=OutletStatus.active, is_active=True)
        db.add(outlet)
        db.commit()

    post_data = {
        "outlet_id": str(outlet.id),
        "channel_partner_id": str(cp.id),
        "order_type": "Primary",
        "notes": "Test Primary Order Creation",
        "product_id[]": [str(sales_products[0].id)],
        "quantity[]": ["5"],
        "unit_price[]": ["100.00"],
        "gst_rate[]": ["18.00"],
        "discount_pct[]": ["5.00"],
    }

    res_post = client_admin.post("/operations/orders/new", data=post_data, follow_redirects=True)
    assert res_post.status_code == 200

    created_order = db.query(Order).order_by(Order.id.desc()).first()
    assert created_order is not None
    assert created_order.order_type == OrderType.primary
    print(f"✓ Created order {created_order.order_number} verified with OrderType = Primary.")

    db.close()
    print("\n🎉 ORDER FORM UPDATES VERIFIED 100% WORKING PERFECTLY!")

if __name__ == "__main__":
    test_order_form_updates()
