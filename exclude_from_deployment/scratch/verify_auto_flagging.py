import sys
import os
from datetime import datetime, timedelta

# Set up python path to find 'app'
sys.path.append("/Users/johnwesleygovada/Desktop/Safar")

# Load environment
from dotenv import load_dotenv
load_dotenv("/Users/johnwesleygovada/Desktop/Safar/.env")

from app.database import SessionLocal
from app.models.timesheet import VisitRecord
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.auto_flag import AutoFlag, FlagType
from app.models.outlet import Outlet, OutletStatus
from app.models.user import User, UserRole
from app.models.geography import Geography, GeoLevel
from app.models.beat import Beat, BeatType
from app.services.auto_flagging import flag_visit_gps, flag_visit_duration, flag_payment_mismatch

def run_tests():
    db = SessionLocal()
    
    # Store items to delete at the end
    to_delete = []
    
    try:
        print("=== Starting Auto-Flagging Verification ===")
        
        # 1. Seed temporary Geography
        print("Seeding temporary Geography...")
        geo = Geography(
            name="Test Zone",
            code="T-ZONE",
            level=GeoLevel.zone,
            is_active=True
        )
        db.add(geo)
        db.flush()
        to_delete.append(geo)
        
        # 2. Seed temporary Beat
        print("Seeding temporary Beat...")
        beat = Beat(
            name="Test Beat",
            code="T-BEAT",
            beat_type=BeatType.GT,
            is_active=True
        )
        db.add(beat)
        db.flush()
        to_delete.append(beat)
        
        # 3. Seed temporary User
        print("Seeding temporary User...")
        user = User(
            email="testrep@safar.com",
            username="testrep",
            full_name="Test Representative",
            hashed_password="dummy",
            role=UserRole.field_rep,
            is_active=True,
            phone="1234567890"
        )
        db.add(user)
        db.flush()
        to_delete.append(user)
        
        # 4. Seed temporary Outlet
        print("Seeding temporary Outlet...")
        outlet = Outlet(
            name="Test Medicals",
            code="T-MED",
            owner_name="Mr. Test",
            mobile="9876543210",
            address="123 Test Street",
            gps_lat=17.4483,
            gps_lng=78.3915,
            is_active=True,
            status=OutletStatus.active,
            beat_id=beat.id,
            territory_id=None
        )
        db.add(outlet)
        db.flush()
        to_delete.append(outlet)
        
        # ── Test 1: GPS Out Of Range Visit ──────────────────────────────────────
        print("\n--- Testing GPS Out Of Range Visit Flagging ---")
        # Simulate visit check-in far away (e.g., ~500m away)
        # Outlet is at 17.4483, 78.3915. Let's check in at 17.4533, 78.3965
        visit_lat = 17.4533
        visit_lng = 78.3965
        
        from app.utils.haversine import haversine_distance
        dist = haversine_distance(visit_lat, visit_lng, outlet.gps_lat, outlet.gps_lng)
        print(f"Simulating check-in at distance: {dist:.1f} meters")
        
        visit = VisitRecord(
            user_id=user.id,
            outlet_id=outlet.id,
            gps_lat=visit_lat,
            gps_lng=visit_lng,
            distance_from_outlet=dist,
            visit_time=datetime.now() - timedelta(seconds=10), # started 10 sec ago
            purpose="Routine Check"
        )
        db.add(visit)
        db.flush()
        to_delete.append(visit)
        
        gps_flag = flag_visit_gps(db, visit)
        if gps_flag:
            db.flush()
            to_delete.append(gps_flag)
            print(f"SUCCESS: GPS Flag created! Title: {gps_flag.title}, Severity: {gps_flag.severity.value}, Metric: {gps_flag.metric_value:.1f}m")
        else:
            print("FAILURE: GPS Flag not created.")

        # ── Test 2: Short Visit Duration ─────────────────────────────────────────
        print("\n--- Testing Short Visit Duration Flagging ---")
        visit.checkout_time = datetime.now()
        db.flush()
        
        print(f"Simulating checkout. Duration: {visit.duration_minutes:.2f} minutes")
        duration_flag = flag_visit_duration(db, visit)
        if duration_flag:
            db.flush()
            if duration_flag not in to_delete:
                to_delete.append(duration_flag)
            print(f"SUCCESS: Duration Flag created! Title: {duration_flag.title}, Severity: {duration_flag.severity.value}, Metric: {duration_flag.metric_value:.1f} seconds")
        else:
            print("FAILURE: Duration Flag not created.")

        # ── Test 3: Cash Payment Denomination Mismatch ───────────────────────────
        print("\n--- Testing Cash Payment Denomination Mismatch ---")
        # Collect cash payment for amount ₹1500 but input no denominations (denom total = 0)
        p = Payment(
            payment_ref="TESTPAYREF001",
            outlet_id=outlet.id,
            user_id=user.id,
            amount=1500.00,
            method=PaymentMethod.cash,
            status=PaymentStatus.collected,
            denom_500=1, denom_200=0, denom_100=0,
            denom_50=0, denom_20=0, denom_10=0, denom_2000=0
        )
        db.add(p)
        db.flush()
        to_delete.append(p)
        
        mismatch_flag = flag_payment_mismatch(db, p)
        if mismatch_flag:
            db.flush()
            to_delete.append(mismatch_flag)
            print(f"SUCCESS: Payment Mismatch Flag created! Title: {mismatch_flag.title}, Severity: {mismatch_flag.severity.value}, Metric: {mismatch_flag.metric_value:.2f}")
        else:
            print("FAILURE: Payment Mismatch Flag not created.")

    except Exception as e:
        print(f"An error occurred during verification: {e}")
    finally:
        # Clean up database in reverse order of creation
        print("\nCleaning up test records from database...")
        for obj in reversed(to_delete):
            try:
                db.delete(obj)
            except Exception as e:
                print(f"Failed to delete {obj}: {e}")
        db.commit()
        db.close()
        print("Database cleanup complete. Verification run finished.")

if __name__ == "__main__":
    run_tests()
