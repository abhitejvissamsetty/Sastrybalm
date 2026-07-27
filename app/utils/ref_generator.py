from app.utils.timezone import ist_today


def order_number(db, model) -> str:
    today = ist_today().strftime("%Y%m%d")
    prefix = f"ORD-{today}-"
    count = db.query(model).filter(model.order_number.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def payment_ref(db, model) -> str:
    today = ist_today().strftime("%Y%m%d")
    prefix = f"PAY-{today}-"
    count = db.query(model).filter(model.payment_ref.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def mr_number(db, model) -> str:
    today = ist_today().strftime("%Y%m%d")
    prefix = f"MR-{today}-"
    count = db.query(model).filter(model.mr_number.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"
