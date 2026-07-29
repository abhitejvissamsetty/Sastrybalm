from datetime import datetime
from sqlalchemy.orm import Session
from app.models.timesheet import Timesheet, TimesheetStatus, TimesheetLineItem, VisitRecord
from app.utils.timezone import ist_now, ist_today


def get_or_create_open_timesheet(db: Session, user_id: int) -> Timesheet:
    """Retrieves current user's open timesheet for today, or auto-creates one."""
    today = ist_today()
    ts = db.query(Timesheet).filter(
        Timesheet.user_id == user_id,
        Timesheet.work_date == today
    ).first()

    if not ts:
        now = ist_now()
        ts = Timesheet(
            user_id=user_id,
            work_date=today,
            checkin_time=now,
            status=TimesheetStatus.open,
            version=1
        )
        db.add(ts)
        db.flush()
    return ts


def sync_auto_timesheet_line_item(db: Session, visit: VisitRecord):
    """
    Automatically creates/updates a read-only TimesheetLineItem when an outlet visit is checked out
    or recorded under Retailing Work or Joint Working.
    """
    if not visit:
        return

    ts = visit.timesheet or get_or_create_open_timesheet(db, visit.user_id)
    if not visit.timesheet_id:
        visit.timesheet_id = ts.id

    category = "Joint Working" if visit.is_joint_visit else "Retailing Work"
    start_time = visit.visit_time or ist_now()
    end_time = visit.checkout_time or ist_now()

    # Check if auto line item already exists for this visit
    line_item = db.query(TimesheetLineItem).filter(
        TimesheetLineItem.timesheet_id == ts.id,
        TimesheetLineItem.visit_record_id == visit.id
    ).first()

    if line_item:
        line_item.category = category
        line_item.start_time = start_time
        line_item.end_time = end_time
    else:
        line_item = TimesheetLineItem(
            timesheet_id=ts.id,
            category=category,
            start_time=start_time,
            end_time=end_time,
            is_automated=True,
            visit_record_id=visit.id,
            notes=f"Automated logging for Outlet Visit #{visit.outlet_id}"
        )
        db.add(line_item)
    db.flush()
