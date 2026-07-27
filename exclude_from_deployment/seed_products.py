from decimal import Decimal
from app.database import SessionLocal
from app.models.product import Product

def seed_products():
    db = SessionLocal()
    try:
        existing_count = db.query(Product).count()
        if existing_count > 0:
            print(f"[skip] Database already contains {existing_count} products.")
            return

        products = [
            Product(
                name="Safar Regular",
                erp_id="PROD-BALM-REG",
                sku="SB-REG-25G",
                division="OTC",
                primary_category="Balms",
                secondary_category="Pain Relief",
                mrp=Decimal("50.00"),
                gst_rate=Decimal("18.00"),
                must_sell=True,
                is_active=True
            ),
            Product(
                name="Safar Extra Strong",
                erp_id="PROD-BALM-EXT",
                sku="SB-EXT-25G",
                division="OTC",
                primary_category="Balms",
                secondary_category="Pain Relief",
                mrp=Decimal("65.00"),
                gst_rate=Decimal("18.00"),
                must_sell=True,
                is_active=True
            ),
            Product(
                name="Safar Pain Relief Spray",
                erp_id="PROD-SPRAY-PR",
                sku="SB-SPRAY-50ML",
                division="OTC",
                primary_category="Sprays",
                secondary_category="Pain Relief",
                mrp=Decimal("120.00"),
                gst_rate=Decimal("18.00"),
                must_sell=False,
                is_active=True
            ),
            Product(
                name="Safar Inhaler",
                erp_id="PROD-INH-01",
                sku="SB-INH-2ML",
                division="OTC",
                primary_category="Inhalers",
                secondary_category="Cold Relief",
                mrp=Decimal("30.00"),
                gst_rate=Decimal("12.00"),
                must_sell=False,
                is_active=True
            ),
            Product(
                name="Safar Herbal Ointment",
                erp_id="PROD-OINT-HB",
                sku="SB-OINT-30G",
                division="OTC",
                primary_category="Ointments",
                secondary_category="Skin Care",
                mrp=Decimal("85.00"),
                gst_rate=Decimal("18.00"),
                must_sell=False,
                is_active=True
            )
        ]

        for p in products:
            db.add(p)
        db.commit()
        print(f"[ok] Seeded {len(products)} default products.")
    except Exception as e:
        db.rollback()
        print(f"[error] Failed to seed products: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_products()
