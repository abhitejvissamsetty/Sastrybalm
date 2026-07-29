import pytest
from fastapi import HTTPException

from app.models.asset_capitalization import AssetMaintenanceLog
from app.models.material_request import MRStatus, MaterialRequest
from app.models.procurement import (
    ProcurementItem,
    QuotationStatus,
    VendorQuotation,
    WorkOrder,
    WorkOrderStatus,
)
from app.models.product_warehouse import ProductWarehouseStock
from app.models.recce import RecceInformation
from app.routers.api.procurement_workflow import (
    AssetFromItemRequest,
    MaintenanceLogRequest,
    ProgressRequest,
    QcCompletionRequest,
    QuotationCreateRequest,
    RecceCreateRequest,
    ReviewRequest,
    WorkOrderQcSubmitRequest,
    acknowledge_work_order,
    approve_quotation,
    approve_recce,
    assign_vendor,
    complete_qc_work_order,
    create_asset_from_item,
    create_maintenance_log,
    create_quotation,
    report_maintenance_progress,
    report_work_order_progress,
    reject_quotation,
    reject_recce,
    submit_recce,
    submit_work_order_qc,
    validate_maintenance_completion,
)


def test_complete_procurement_and_maintenance_lifecycle(
    db_session, acceptance_data
):
    users = acceptance_data["users"]
    vendor = acceptance_data["vendors"]["a"]
    product = acceptance_data["products"]["marketing"]
    mr = MaterialRequest(
        mr_number="ACC-LIFECYCLE-MR",
        user=users["l1"],
        outlet=acceptance_data["outlets"]["a"],
        product=product,
        company_profile=acceptance_data["company"],
        category="Signage",
        description="Lifecycle acceptance signage",
        status=MRStatus.submitted,
    )
    db_session.add(mr)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        assign_vendor(
            mr.id, vendor.id, db=db_session, current_user=users["l2"]
        )
    assert exc.value.status_code == 403

    assign_vendor(mr.id, vendor.id, db=db_session, current_user=users["l3"])
    recce_request = RecceCreateRequest(
        dimensions="120 x 60 cm",
        dimension_length=120,
        dimension_width=60,
        description="Mounting location measured",
        image_urls=["s3://acceptance/recce-a.jpg", "s3://acceptance/recce-b.jpg"],
    )
    recce_result = submit_recce(
        mr.id,
        recce_request,
        idempotency_key="lifecycle-recce",
        db=db_session,
        current_user=users["vendor_technician"],
    )
    assert submit_recce(
        mr.id,
        recce_request,
        idempotency_key="lifecycle-recce",
        db=db_session,
        current_user=users["vendor_technician"],
    ) == recce_result
    assert db_session.query(RecceInformation).count() == 1
    approve_recce(
        recce_result["recce_id"], db=db_session, current_user=users["l3"]
    )

    quotation_request = QuotationCreateRequest(
        material_request_id=mr.id,
        base_amount=1000,
        gst_percent=18,
        lead_time_days=5,
    )
    quote_result = create_quotation(
        quotation_request,
        idempotency_key="lifecycle-quotation",
        db=db_session,
        current_user=users["vendor_admin"],
    )
    assert create_quotation(
        quotation_request,
        idempotency_key="lifecycle-quotation",
        db=db_session,
        current_user=users["vendor_admin"],
    ) == quote_result
    assert db_session.query(VendorQuotation).count() == 1
    wo_result = approve_quotation(
        quote_result["quotation_id"],
        db=db_session,
        current_user=users["l3"],
    )
    work_order = db_session.query(WorkOrder).filter_by(
        id=wo_result["work_order_id"]
    ).one()

    acknowledge_work_order(
        work_order.id, db=db_session, current_user=users["vendor_admin"]
    )
    progress_request = ProgressRequest(
        progress_percent=50, remarks="Manufacturing"
    )
    progress_result = report_work_order_progress(
        work_order.id,
        progress_request,
        idempotency_key="lifecycle-progress",
        db=db_session,
        current_user=users["vendor_admin"],
    )
    assert report_work_order_progress(
        work_order.id,
        progress_request,
        idempotency_key="lifecycle-progress",
        db=db_session,
        current_user=users["vendor_admin"],
    ) == progress_result
    submit_work_order_qc(
        work_order.id,
        WorkOrderQcSubmitRequest(notes="Ready for inspection"),
        db=db_session,
        current_user=users["vendor_admin"],
    )
    qc_request = QcCompletionRequest(
        final_dimensions="120 x 60 cm",
        final_specifications="Weatherproof signage",
        qc_notes="QC passed",
        image_urls=["s3://acceptance/qc-a.jpg", "s3://acceptance/qc-b.jpg"],
    )
    qc_result = complete_qc_work_order(
        work_order.id,
        qc_request,
        idempotency_key="lifecycle-qc",
        db=db_session,
        current_user=users["qc_manager"],
    )
    assert complete_qc_work_order(
        work_order.id,
        qc_request,
        idempotency_key="lifecycle-qc",
        db=db_session,
        current_user=users["qc_manager"],
    ) == qc_result
    item = db_session.query(ProcurementItem).filter_by(
        id=qc_result["item_id"]
    ).one()
    stock = db_session.query(ProductWarehouseStock).filter_by(
        product_id=product.id, warehouse_id=item.warehouse_id
    ).one()
    assert stock.stock_qty == 1
    assert work_order.status == WorkOrderStatus.completed
    assert mr.status == MRStatus.completed

    asset_request = AssetFromItemRequest(
        notes="Installed at outlet",
        image_url="s3://acceptance/installed.jpg",
    )
    asset_result = create_asset_from_item(
        item.id,
        asset_request,
        idempotency_key="lifecycle-asset",
        db=db_session,
        current_user=users["vendor_technician"],
    )
    assert create_asset_from_item(
        item.id,
        asset_request,
        idempotency_key="lifecycle-asset",
        db=db_session,
        current_user=users["vendor_technician"],
    ) == asset_result
    db_session.refresh(stock)
    assert stock.stock_qty == 0

    maintenance_request = MaintenanceLogRequest(
        notes="Loose mounting",
        image_urls=["s3://acceptance/maintenance.jpg"],
    )
    maintenance_result = create_maintenance_log(
        asset_result["asset_id"],
        maintenance_request,
        idempotency_key="lifecycle-maintenance",
        db=db_session,
        current_user=users["vendor_technician"],
    )
    assert create_maintenance_log(
        asset_result["asset_id"],
        maintenance_request,
        idempotency_key="lifecycle-maintenance",
        db=db_session,
        current_user=users["vendor_technician"],
    ) == maintenance_result
    report_maintenance_progress(
        maintenance_result["log_id"],
        ProgressRequest(progress_percent=100, remarks="Mounting tightened"),
        idempotency_key="lifecycle-maintenance-progress",
        db=db_session,
        current_user=users["vendor_technician"],
    )
    validation = validate_maintenance_completion(
        maintenance_result["log_id"],
        db=db_session,
        current_user=users["qc_manager"],
    )
    assert validation["status"] == "Validated"
    log = db_session.query(AssetMaintenanceLog).filter_by(
        id=maintenance_result["log_id"]
    ).one()
    assert log.validated_by_id == users["qc_manager"].id


def test_recce_and_quotation_rejections_require_hierarchy_and_reason(
    db_session, acceptance_data
):
    users = acceptance_data["users"]
    vendor = acceptance_data["vendors"]["a"]
    mr = MaterialRequest(
        mr_number="ACC-REJECTION-MR",
        user=users["l1"],
        outlet=acceptance_data["outlets"]["a"],
        product=acceptance_data["products"]["marketing"],
        company_profile=acceptance_data["company"],
        description="Rejection transition fixture",
        vendor=vendor,
        status=MRStatus.recce_completed,
    )
    recce = RecceInformation(
        material_request=mr,
        vendor=vendor,
        created_by=users["vendor_technician"],
        status="Submitted",
    )
    quote = VendorQuotation(
        material_request=mr,
        vendor=vendor,
        recce=recce,
        quote_amount=1000,
        status=QuotationStatus.pending,
    )
    db_session.add_all([mr, recce, quote])
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        reject_recce(
            recce.id,
            ReviewRequest(reason="Invalid measurements"),
            db=db_session,
            current_user=users["l2"],
        )
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        reject_recce(
            recce.id,
            ReviewRequest(reason=""),
            db=db_session,
            current_user=users["l3"],
        )
    assert exc.value.status_code == 400

    reject_recce(
        recce.id,
        ReviewRequest(reason="Invalid measurements"),
        db=db_session,
        current_user=users["l3"],
    )
    assert recce.status == "Rejected"

    reject_quotation(
        quote.id,
        ReviewRequest(reason="Commercial terms rejected"),
        db=db_session,
        current_user=users["l3"],
    )
    assert quote.status == QuotationStatus.rejected
    with pytest.raises(HTTPException) as exc:
        reject_quotation(
            quote.id,
            ReviewRequest(reason="Again"),
            db=db_session,
            current_user=users["l3"],
        )
    assert exc.value.status_code == 409
