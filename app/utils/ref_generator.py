from datetime import date


def order_number(db, model) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"ORD-{today}-"
    count = db.query(model).filter(model.order_number.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def payment_ref(db, model) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"PAY-{today}-"
    count = db.query(model).filter(model.payment_ref.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def mr_number(db, model) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"MR-{today}-"
    count = db.query(model).filter(model.mr_number.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def submission_ref(db, model) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"SUB-{today}-"
    count = db.query(model).filter(model.submission_ref.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"
