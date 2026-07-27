from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.order import Order, OrderType, PaymentSettlementStatus
from app.models.outlet import Outlet, OutletStatus
from app.models.local_distribution import LocalChannelPartner
from app.models.product import Product, ProductCategory
from app.models.timesheet import VisitRecord
from app.utils.timezone import ist_now
from itsdangerous import TimestampSigner
from app.config import settings
import json, base64

def test_order_flows():
    print("\n--- TESTING SECONDARY & PRIMARY ORDER FLOWS ---")
    db = SessionLocal()
    signer = TimestampSigner(settings.secret_key)

    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    field_rep = db.query(User).filter(User.role == UserRole.field_rep).first()
    tm_user = db.query(User).filter(User.role == UserRole.territory_manager).first()
    outlet = db.query(Outlet).first()
    
    import uuid
    rnd = uuid.uuid4().hex[:8].upper()
    no_visit_outlet = Outlet(name=f"No Visit Outlet Test {rnd}", code=f"OUT_NO_VISIT_{rnd}", status=OutletStatus.active)
    db.add(no_visit_outlet)
    db.commit()
    db.refresh(no_visit_outlet)

    cp = db.query(LocalChannelPartner).first()
    sales_products = db.query(Product).filter(Product.is_active == True, Product.category_type == ProductCategory.sales).all()

    assert admin_user and field_rep and tm_user and outlet and cp and sales_products

    session_admin = json.dumps({"user_id": admin_user.id}).encode("utf-8")
    cookie_admin = signer.sign(base64.b64encode(session_admin)).decode("utf-8")
    client_admin = TestClient(fastapi_app, cookies={"session": cookie_admin})

    session_rep = json.dumps({"user_id": field_rep.id}).encode("utf-8")
    cookie_rep = signer.sign(base64.b64encode(session_rep)).decode("utf-8")
    client_rep = TestClient(fastapi_app, cookies={"session": cookie_rep})

    session_tm = json.dumps({"user_id": tm_user.id}).encode("utf-8")
    cookie_tm = signer.sign(base64.b64encode(session_tm)).decode("utf-8")
    client_tm = TestClient(fastapi_app, cookies={"session": cookie_tm})

    # 1. Test Secondary Order without Visit Record -> Should fail
    post_sec_no_visit = {
        "order_type": "Secondary",
        "outlet_id": str(no_visit_outlet.id),
        "channel_partner_id": str(cp.id),
        "product_id[]": [str(sales_products[0].id)],
        "quantity[]": ["2"],
        "unit_price[]": ["100.00"],
    }
    res_no_visit = client_admin.post("/operations/orders/new", data=post_sec_no_visit)
    assert res_no_visit.status_code == 200
    assert "mandatory Visit record" in res_no_visit.text
    print("✓ Secondary Order WITHOUT Visit Record correctly rejected.")

    # Log a Visit Record for Admin against outlet
    visit_admin = VisitRecord(
        user_id=admin_user.id,
        outlet_id=outlet.id,
        visit_time=ist_now()
    )
    db.add(visit_admin)
    db.commit()
    db.refresh(visit_admin)

    # 2. Test Secondary Order with Regional Company & Payment Flow
    post_sec_regional = {
        "order_type": "Secondary",
        "outlet_id": str(outlet.id),
        "visit_id": str(visit_admin.id),
        "channel_partner_id": "regional_company",
        "amount_collected": "100.00",
        "payment_method": "upi",
        "transaction_ref": "UPI_REF_9999",
        "product_id[]": [str(sales_products[0].id)],
        "quantity[]": ["2"],
        "unit_price[]": ["100.00"],
    }
    res_sec_reg = client_admin.post("/operations/orders/new", data=post_sec_regional, follow_redirects=True)
    assert res_sec_reg.status_code == 200

    created_sec = db.query(Order).filter(Order.is_regional_company == True, Order.user_id == admin_user.id).order_by(Order.id.desc()).first()
    assert created_sec is not None
    assert created_sec.visit_id is not None
    assert created_sec.is_regional_company == True
    assert created_sec.payment_settlement in [PaymentSettlementStatus.partial, PaymentSettlementStatus.paid]
    print(f"✓ Secondary Order {created_sec.order_number} created with Visit #{created_sec.visit_id}, Regional Company fulfillment, and UPI payment collection.")

    # 3. Test Primary Order by L1 Field Rep -> Should be blocked
    post_pri_rep = {
        "order_type": "Primary",
        "channel_partner_id": str(cp.id),
        "product_id[]": [str(sales_products[0].id)],
        "quantity[]": ["10"],
        "unit_price[]": ["200.00"],
    }
    res_pri_rep = client_rep.post("/operations/orders/new", data=post_pri_rep)
    assert res_pri_rep.status_code == 200
    assert "restricted to Territory Managers" in res_pri_rep.text
    print("✓ Primary Order by L1 Field Rep correctly BLOCKED.")

    # 4. Test Primary Order by L2 Territory Manager -> Should succeed (No Visit, No Outlet, No Payment)
    post_pri_tm = {
        "order_type": "Primary",
        "channel_partner_id": str(cp.id),
        "product_id[]": [str(sales_products[0].id)],
        "quantity[]": ["10"],
        "unit_price[]": ["200.00"],
    }
    res_pri_tm = client_tm.post("/operations/orders/new", data=post_pri_tm, follow_redirects=True)
    assert res_pri_tm.status_code == 200

    created_pri = db.query(Order).filter(Order.order_type == OrderType.primary, Order.user_id == tm_user.id).order_by(Order.id.desc()).first()
    assert created_pri is not None
    assert created_pri.outlet_id is None
    assert created_pri.visit_id is None
    assert created_pri.channel_partner_id == cp.id
    print(f"✓ Primary Order {created_pri.order_number} created by TM against Channel Partner {cp.name} without Visit or Outlet requirement.")

    db.close()
    print("\n🎉 SECONDARY & PRIMARY ORDER FLOWS 100% VERIFIED WORKING PERFECTLY!")

if __name__ == "__main__":
    test_order_flows()
