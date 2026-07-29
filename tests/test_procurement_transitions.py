import asyncio

import pytest
from fastapi import HTTPException

from app.routers.api.operations import (
    api_work_order_qc_approve,
    collect_payment,
    get_order_detail,
)
from app.models.procurement import QCStatus, WorkOrderStatus
from app.routers.api.procurement_workflow import (
    AssetFromItemRequest,
    QcCompletionRequest,
    approve_quotation,
    approve_recce,
    create_asset_from_item,
    complete_qc_work_order,
)


def test_completed_procurement_steps_are_idempotent(
    db_session, acceptance_data, operational_data
):
    records = operational_data

    quotation_result = approve_quotation(
        records["quotation"].id,
        db=db_session,
        current_user=acceptance_data["users"]["l3"],
    )
    assert quotation_result["work_order_id"] == records["work_order"].id

    qc_result = complete_qc_work_order(
        records["work_order"].id,
        QcCompletionRequest(
            final_dimensions="120 x 60 cm",
            final_specifications="Acceptance signage",
            qc_notes="Duplicate submission",
            image_urls=["s3://acceptance/qc-1.jpg", "s3://acceptance/qc-2.jpg"],
        ),
        idempotency_key="acceptance-qc-complete",
        db=db_session,
        current_user=acceptance_data["users"]["qc_manager"],
    )
    assert qc_result["item_id"] == records["procurement_item"].id

    asset_result = create_asset_from_item(
        records["procurement_item"].id,
        AssetFromItemRequest(notes="Duplicate deployment"),
        idempotency_key="acceptance-asset-create",
        db=db_session,
        current_user=acceptance_data["users"]["vendor_technician"],
    )
    assert asset_result["asset_id"] == records["asset"].id


def test_invalid_approval_transition_is_rejected(
    db_session, acceptance_data, operational_data
):
    with pytest.raises(HTTPException) as exc:
        approve_recce(
            operational_data["recce"].id,
            db=db_session,
            current_user=acceptance_data["users"]["l3"],
        )
    assert exc.value.status_code == 409


def test_payment_rejects_mismatched_or_inaccessible_objects(
    db_session, acceptance_data, operational_data
):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            collect_payment(
                outlet_id=acceptance_data["outlets"]["b"].id,
                amount=100,
                method="upi",
                order_id=operational_data["order"].id,
                idempotency_key="mismatched-payment",
                current_user=acceptance_data["users"]["admin"],
                db=db_session,
            )
        )
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            get_order_detail(
                operational_data["order"].id,
                current_user=acceptance_data["users"]["other_l1"],
                db=db_session,
            )
        )
    assert exc.value.status_code == 404


def test_qc_failure_is_terminal_for_the_review_attempt(
    db_session, acceptance_data, operational_data
):
    work_order = operational_data["work_order"]
    work_order.status = WorkOrderStatus.qc_pending
    work_order.qc_status = QCStatus.pending
    db_session.commit()

    result = asyncio.run(
        api_work_order_qc_approve(
            work_order.id,
            qc_result="failed",
            qc_notes="Mounting dimensions differ",
            qc_photo=None,
            current_user=acceptance_data["users"]["qc_manager"],
            db=db_session,
        )
    )
    assert result["status"] == "failed"
    assert work_order.qc_status == QCStatus.failed

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            api_work_order_qc_approve(
                work_order.id,
                qc_result="passed",
                qc_notes=None,
                qc_photo=None,
                current_user=acceptance_data["users"]["qc_manager"],
                db=db_session,
            )
        )
    assert exc.value.status_code == 409
