"""Deterministic acceptance-data factories shared by backend tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.asset_capitalization import (
    ACStatus,
    AssetCapitalization,
    AssetMaintenanceLog,
    DeployedByType,
)
from app.models.beat import Beat, BeatGrade, BeatType
from app.models.company import CompanyProfile
from app.models.expense import Expense, ExpenseCategory, ExpenseStatus
from app.models.geography import Geography, GeoLevel
from app.models.leave import Leave, LeaveStatus, LeaveType
from app.models.local_distribution import LocalChannelPartner
from app.models.material_request import MRStatus, MaterialRequest
from app.models.order import Order, OrderItem, OrderStatus, OrderType
from app.models.outlet import ChannelType, Outlet, OutletStatus, ShopType
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.position import Position, PositionLevel
from app.models.procurement import (
    ProcurementItem,
    QCStatus,
    QuotationStatus,
    VendorQuotation,
    WorkOrder,
    WorkOrderStatus,
)
from app.models.product import Product, ProductCategory
from app.models.product_warehouse import ProductWarehouseStock
from app.models.recce import RecceInformation
from app.models.timesheet import (
    Timesheet,
    TimesheetApproval,
    TimesheetStatus,
    VisitRecord,
)
from app.models.user import User, UserRole
from app.models.vendor import Vendor, VendorStatus
from app.models.warehouse import Warehouse
from app.utils.security import hash_password


def user(
    *,
    username: str,
    role: UserRole,
    company: CompanyProfile,
    geography: Geography | None = None,
    vendor: Vendor | None = None,
    positions: tuple[Position, ...] = (),
) -> User:
    item = User(
        email=f"{username}@acceptance.test",
        username=username,
        full_name=username.replace("_", " ").title(),
        hashed_password=hash_password("Acceptance-Only-Password!"),
        role=role,
        company_profile=company,
        geography=geography,
        vendor=vendor,
        is_active=True,
        is_registered=True,
    )
    item.positions.extend(positions)
    return item


def acceptance_environment(db) -> dict:
    """Create two isolated hierarchy branches and every supported application role."""
    company = CompanyProfile(code="ACCEPTANCE", name="Acceptance Company")

    zone_a = Geography(name="Zone A", code="ACC-ZA", level=GeoLevel.zone)
    region_a = Geography(
        name="Region A", code="ACC-RA", level=GeoLevel.region, parent=zone_a
    )
    territory_a = Geography(
        name="Territory A",
        code="ACC-TA",
        level=GeoLevel.territory,
        parent=region_a,
    )
    zone_b = Geography(name="Zone B", code="ACC-ZB", level=GeoLevel.zone)
    region_b = Geography(
        name="Region B", code="ACC-RB", level=GeoLevel.region, parent=zone_b
    )
    territory_b = Geography(
        name="Territory B",
        code="ACC-TB",
        level=GeoLevel.territory,
        parent=region_b,
    )

    warehouse_a = Warehouse(
        name="Warehouse A", code="ACC-WHA", geography=region_a, pincode="500001"
    )
    warehouse_b = Warehouse(
        name="Warehouse B", code="ACC-WHB", geography=region_b, pincode="600001"
    )

    beat_a = Beat(
        name="Beat A",
        code="ACC-BA",
        territory=territory_a,
        beat_type=BeatType.GT,
        beat_grade=BeatGrade.urban,
    )
    beat_b = Beat(
        name="Beat B",
        code="ACC-BB",
        territory=territory_b,
        beat_type=BeatType.GT,
        beat_grade=BeatGrade.urban,
    )

    l4_position = Position(
        name="L4 Position A",
        code="ACC-L4A",
        level=PositionLevel.L4,
        warehouse=warehouse_a,
    )
    l3_position = Position(
        name="L3 Position A",
        code="ACC-L3A",
        level=PositionLevel.L3,
        reporting_to=l4_position,
        warehouse=warehouse_a,
    )
    l2_position = Position(
        name="L2 Position A",
        code="ACC-L2A",
        level=PositionLevel.L2,
        reporting_to=l3_position,
    )
    l1_position = Position(
        name="L1 Position A",
        code="ACC-L1A",
        level=PositionLevel.L1,
        reporting_to=l2_position,
    )
    l1_position.beats.append(beat_a)

    other_l1_position = Position(
        name="L1 Position B",
        code="ACC-L1B",
        level=PositionLevel.L1,
        warehouse=warehouse_b,
    )
    other_l1_position.beats.append(beat_b)

    sales_product = Product(
        name="Acceptance Sales Product",
        sku="ACC-SALES-1",
        category_type=ProductCategory.sales,
        mrp=100,
        unit_cost=60,
        gst_rate=18,
        is_stockable=True,
        warehouse=warehouse_a,
    )
    marketing_product = Product(
        name="Acceptance Marketing Asset",
        sku="ACC-MKT-1",
        category_type=ProductCategory.marketing_procurement,
        mrp=250,
        unit_cost=150,
        is_stockable=True,
        warehouse=warehouse_a,
    )
    db.add_all([
        company,
        zone_a,
        zone_b,
        warehouse_a,
        warehouse_b,
        beat_a,
        beat_b,
        l4_position,
        l3_position,
        l2_position,
        l1_position,
        other_l1_position,
        sales_product,
        marketing_product,
    ])
    db.flush()

    stock_a = ProductWarehouseStock(
        product=sales_product, warehouse=warehouse_a, stock_qty=100, reorder_level=10
    )
    stock_b = ProductWarehouseStock(
        product=sales_product, warehouse=warehouse_b, stock_qty=75, reorder_level=10
    )
    vendor_a = Vendor(
        name="Vendor A",
        email="vendor-a@acceptance.test",
        geography=territory_a,
        status=VendorStatus.active,
    )
    vendor_b = Vendor(
        name="Vendor B",
        email="vendor-b@acceptance.test",
        geography=territory_b,
        status=VendorStatus.active,
    )
    partner_a = LocalChannelPartner(
        code="ACC-CPA", name="Partner A", geography=territory_a, is_active=True
    )
    partner_b = LocalChannelPartner(
        code="ACC-CPB", name="Partner B", geography=territory_b, is_active=True
    )
    outlet_a = Outlet(
        name="Outlet A",
        code="ACC-OA",
        beat=beat_a,
        territory=territory_a,
        channel=ChannelType.GT,
        shop_type=ShopType.kirana,
        status=OutletStatus.active,
        gps_lat=17.385,
        gps_lng=78.4867,
    )
    outlet_b = Outlet(
        name="Outlet B",
        code="ACC-OB",
        beat=beat_b,
        territory=territory_b,
        channel=ChannelType.GT,
        shop_type=ShopType.kirana,
        status=OutletStatus.active,
        gps_lat=13.0827,
        gps_lng=80.2707,
    )
    db.add_all([
        stock_a,
        stock_b,
        vendor_a,
        vendor_b,
        partner_a,
        partner_b,
        outlet_a,
        outlet_b,
    ])
    db.flush()

    users = {
        "admin": user(username="admin", role=UserRole.admin, company=company),
        "l4": user(
            username="l4_manager",
            role=UserRole.territory_manager,
            company=company,
            geography=zone_a,
            positions=(l4_position,),
        ),
        "l3": user(
            username="l3_manager",
            role=UserRole.territory_manager,
            company=company,
            geography=region_a,
            positions=(l3_position,),
        ),
        "l2": user(
            username="l2_manager",
            role=UserRole.territory_manager,
            company=company,
            geography=region_a,
            positions=(l2_position,),
        ),
        "l1": user(
            username="l1_rep",
            role=UserRole.field_rep,
            company=company,
            geography=territory_a,
            positions=(l1_position,),
        ),
        "other_l1": user(
            username="other_l1_rep",
            role=UserRole.field_rep,
            company=company,
            geography=territory_b,
            positions=(other_l1_position,),
        ),
        "vendor_admin": user(
            username="vendor_admin",
            role=UserRole.vendor_admin,
            company=company,
            geography=territory_a,
            vendor=vendor_a,
        ),
        "vendor_technician": user(
            username="vendor_technician",
            role=UserRole.vendor_technician,
            company=company,
            geography=territory_a,
            vendor=vendor_a,
        ),
        "qc_manager": user(
            username="qc_manager",
            role=UserRole.qc_manager,
            company=company,
            geography=region_a,
        ),
    }
    users["l3"].scoped_warehouses.append(warehouse_a)
    users["qc_manager"].qc_vendors.append(vendor_a)
    db.add_all(users.values())
    db.commit()

    return {
        "company": company,
        "geographies": {
            "zone_a": zone_a,
            "region_a": region_a,
            "territory_a": territory_a,
            "zone_b": zone_b,
            "region_b": region_b,
            "territory_b": territory_b,
        },
        "warehouses": {"a": warehouse_a, "b": warehouse_b},
        "beats": {"a": beat_a, "b": beat_b},
        "positions": {
            "l4": l4_position,
            "l3": l3_position,
            "l2": l2_position,
            "l1": l1_position,
            "other_l1": other_l1_position,
        },
        "products": {"sales": sales_product, "marketing": marketing_product},
        "vendors": {"a": vendor_a, "b": vendor_b},
        "partners": {"a": partner_a, "b": partner_b},
        "outlets": {"a": outlet_a, "b": outlet_b},
        "users": users,
    }


def operational_environment(db, acceptance: dict) -> dict:
    """Seed one deterministic, linked record for each core operational domain."""
    now = datetime(2026, 1, 15, 10, 0, 0)
    rep = acceptance["users"]["l1"]
    manager = acceptance["users"]["l2"]
    qc_manager = acceptance["users"]["qc_manager"]
    outlet = acceptance["outlets"]["a"]
    sales_product = acceptance["products"]["sales"]
    marketing_product = acceptance["products"]["marketing"]
    vendor = acceptance["vendors"]["a"]
    warehouse = acceptance["warehouses"]["a"]

    timesheet = Timesheet(
        user=rep,
        work_date=now.date(),
        checkin_time=now,
        checkout_time=now + timedelta(hours=8),
        checkin_lat=outlet.gps_lat,
        checkin_lng=outlet.gps_lng,
        status=TimesheetStatus.closed,
        approval_status=TimesheetApproval.approved,
        approved_by=manager,
        approved_at=now + timedelta(hours=9),
    )
    visit = VisitRecord(
        user=rep,
        outlet=outlet,
        timesheet=timesheet,
        visit_time=now + timedelta(hours=1),
        checkout_time=now + timedelta(hours=1, minutes=30),
        gps_lat=outlet.gps_lat,
        gps_lng=outlet.gps_lng,
        distance_from_outlet=0,
        purpose="Order collection",
        visit_type="in_location",
    )
    db.add_all([timesheet, visit])
    db.flush()
    order = Order(
        order_number="ACC-ORD-0001",
        outlet=outlet,
        user=rep,
        beat=acceptance["beats"]["a"],
        visit_id=visit.id,
        warehouse=warehouse,
        order_type=OrderType.secondary,
        status=OrderStatus.delivered,
        order_date=now.date(),
    )
    order.items.append(
        OrderItem(
            product=sales_product,
            quantity=5,
            unit_price=118,
            gst_rate=18,
        )
    )
    db.add(order)
    db.flush()
    visit.order_id = order.id
    payment = Payment(
        payment_ref="ACC-PAY-0001",
        order=order,
        outlet=outlet,
        user=rep,
        amount=590,
        method=PaymentMethod.upi,
        status=PaymentStatus.verified,
        transaction_ref="ACC-UPI-0001",
        collected_at=now + timedelta(hours=2),
    )
    expense = Expense(
        user=rep,
        category=ExpenseCategory.travel,
        amount=250,
        description="Acceptance route travel",
        expense_date=now.date(),
        status=ExpenseStatus.approved,
        approved_by=manager,
        approved_at=now + timedelta(days=1),
    )
    leave = Leave(
        user=rep,
        leave_type=LeaveType.casual,
        start_date=(now + timedelta(days=7)).date(),
        end_date=(now + timedelta(days=7)).date(),
        reason="Acceptance fixture leave",
        status=LeaveStatus.approved,
        approved_by=manager,
        approved_at=now,
    )
    material_request = MaterialRequest(
        mr_number="ACC-MR-0001",
        user=rep,
        outlet=outlet,
        product=marketing_product,
        company_profile=acceptance["company"],
        category="Signage",
        description="Install acceptance marketing signage",
        vendor=vendor,
        status=MRStatus.work_order_issued,
        submitted_at=now,
    )
    db.add_all([payment, expense, leave, material_request])
    db.flush()

    recce = RecceInformation(
        material_request=material_request,
        vendor=vendor,
        created_by=acceptance["users"]["vendor_technician"],
        dimensions="120 x 60 cm",
        status="Approved",
        description="Site suitable for signage",
        approved_by=manager,
        approved_at=now + timedelta(days=1),
    )
    db.add(recce)
    db.flush()
    quotation = VendorQuotation(
        material_request=material_request,
        vendor=vendor,
        recce=recce,
        quote_amount=1180,
        base_amount=1000,
        gst_percent=18,
        gst_amount=180,
        total_amount=1180,
        status=QuotationStatus.approved,
        submitted_at=now + timedelta(days=2),
        approved_by=manager,
        approved_at=now + timedelta(days=3),
    )
    db.add(quotation)
    db.flush()
    work_order = WorkOrder(
        quotation=quotation,
        material_request=material_request,
        vendor=vendor,
        outlet=outlet,
        wo_number="ACC-WO-0001",
        status=WorkOrderStatus.completed,
        progress_percent=100,
        qc_status=QCStatus.passed,
        qc_verified_by=qc_manager,
        qc_verified_at=now + timedelta(days=5),
    )
    db.add(work_order)
    db.flush()
    procurement_item = ProcurementItem(
        work_order=work_order,
        product=marketing_product,
        warehouse=warehouse,
        vendor=vendor,
        outlet=outlet,
        item_name="Acceptance Marketing Signage",
        batch_number="ACC-BATCH-0001",
        final_dimensions="120 x 60 cm",
        qc_manager=qc_manager,
        status="QC Passed",
    )
    db.add(procurement_item)
    db.flush()
    asset = AssetCapitalization(
        ac_number="ACC-ASSET-0001",
        user=rep,
        outlet=outlet,
        product=marketing_product,
        warehouse=warehouse,
        company_profile=acceptance["company"],
        item_name="Acceptance Marketing Signage",
        item_code="ACC-MKT-1",
        deployed_by=DeployedByType.rep,
        vendor=vendor,
        status=ACStatus.deployed,
        qc_verified=ACStatus.deployed,
        procurement_item=procurement_item,
        deployed_at=now + timedelta(days=6),
    )
    db.add(asset)
    db.flush()
    maintenance = AssetMaintenanceLog(
        asset=asset,
        created_by=rep,
        notes="Acceptance preventive maintenance complete",
        issue_description="Loose mounting inspected",
        status="Completed",
        progress_percent=100,
        vendor=vendor,
        completed_at=now + timedelta(days=30),
        validated_by=qc_manager,
        validated_at=now + timedelta(days=31),
    )
    db.add(maintenance)
    db.commit()

    return {
        "timesheet": timesheet,
        "visit": visit,
        "order": order,
        "payment": payment,
        "expense": expense,
        "leave": leave,
        "material_request": material_request,
        "recce": recce,
        "quotation": quotation,
        "work_order": work_order,
        "procurement_item": procurement_item,
        "asset": asset,
        "maintenance": maintenance,
    }
