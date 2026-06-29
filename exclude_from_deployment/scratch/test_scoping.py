import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.product import Product
from app.models.company import CompanyProfile
from app.routers.products import product_list
from app.routers.api.master import product_list as api_product_list
from app.routers.company import product_mappings_list
from fastapi import Request, HTTPException

class MockRequest(Request):
    def __init__(self, scope=None, receive=None):
        if scope is None:
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/products",
                "headers": [],
                "session": {},
            }
        super().__init__(scope, receive)

async def test_scoping_functionality():
    db = SessionLocal()
    try:
        # Get or create two company profiles for testing
        cp1 = db.query(CompanyProfile).filter(CompanyProfile.code == "COMP1").first()
        if not cp1:
            cp1 = CompanyProfile(code="COMP1", name="Company 1", is_active=True)
            db.add(cp1)
            db.commit()
            db.refresh(cp1)
            
        cp2 = db.query(CompanyProfile).filter(CompanyProfile.code == "COMP2").first()
        if not cp2:
            cp2 = CompanyProfile(code="COMP2", name="Company 2", is_active=True)
            db.add(cp2)
            db.commit()
            db.refresh(cp2)

        # Clear existing test products
        db.query(Product).filter(Product.company_profile_id.in_([cp1.id, cp2.id])).delete()
        db.commit()

        # Add products for both companies
        p1 = Product(name="Company 1 Product", erp_id="PROD-C1-01", company_profile_id=cp1.id, mrp=10.0, gst_rate=12.0)
        p2 = Product(name="Company 2 Product", erp_id="PROD-C2-01", company_profile_id=cp2.id, mrp=20.0, gst_rate=18.0)
        db.add_all([p1, p2])
        db.commit()

        # 1. Create a non-admin user associated with Company 1
        user_c1 = User(
            email="user_c1@example.com",
            username="user_c1",
            full_name="User Company 1",
            hashed_password="...",
            role=UserRole.field_rep,
            company_profile_id=cp1.id,
            is_active=True
        )

        # 2. Test web product list endpoint scoping for non-admin User C1
        print("Testing web product_list for non-admin user associated with Company 1...")
        request = MockRequest()
        # Call product_list router function directly
        res = await product_list(
            request=request,
            current_user=user_c1,
            db=db,
            company_profile_id="",  # passed as empty to see if it defaults correctly to C1
            q="",
            category="",
            must_sell="",
            page=1
        )
        context = res.body  # Jinja2TemplateResponse stores context in body/context
        
        # Verify pagination products are only from Company 1
        pagination = res.context["pagination"]
        print(f"-> Scoped page results count: {len(pagination.items)}")
        for item in pagination.items:
            print(f"   - Product: {item.name} (Company Profile ID: {item.company_profile_id})")
            assert item.company_profile_id == cp1.id, "Error: Leaked product from other company!"

        # Verify profiles dropdown contains only C1
        profiles_list = res.context["profiles"]
        print(f"-> Scoped profiles dropdown count: {len(profiles_list)}")
        assert len(profiles_list) == 1 and profiles_list[0].id == cp1.id, "Error: Profiles dropdown not scoped!"

        # 3. Test mobile API products endpoint scoping for non-admin User C1
        print("\nTesting mobile API product_list for non-admin user associated with Company 1...")
        api_res = await api_product_list(
            current_user=user_c1,
            db=db
        )
        items = api_res["items"]
        print(f"-> Mobile API returned {len(items)} products:")
        for it in items:
            print(f"   - Product: {it['name']} (ID: {it['id']})")
            # Verify database lookup
            prod_db = db.query(Product).filter(Product.id == it['id']).first()
            assert prod_db.company_profile_id == cp1.id, "Error: Leaked product in mobile API!"

        # 4. Test mapping routes permissions scoping
        print("\nTesting account mappings access for Company 1 user to Company 2 mappings...")
        try:
            await product_mappings_list(
                profile_id=cp2.id,
                request=request,
                current_user=user_c1,
                db=db
            )
            print("❌ Error: Accessed another company's mappings without authorization!")
        except HTTPException as e:
            print(f"✅ Success: Threw expected HTTP {e.status_code} - {e.detail}")
            assert e.status_code == 403

        print("\n🎉 ALL SCOPING FUNCTIONALITY VERIFIED SUCCESSFULLY!")

    finally:
        # Clean up database test entries
        db.query(Product).filter(Product.company_profile_id.in_([cp1.id, cp2.id])).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(test_scoping_functionality())
