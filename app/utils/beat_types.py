from sqlalchemy.orm import Session
from app.models.beat_type import BeatTypeMaster

DEFAULT_BEAT_TYPES = [
    {"code": "GT", "name": "General Trade (GT)", "description": "Retail stores, kirana shops, and general trade outlets"},
    {"code": "MT", "name": "Modern Trade (MT)", "description": "Supermarkets, hypermarkets, and chain stores"},
    {"code": "PHARMACY", "name": "Pharmacy", "description": "Medical stores and pharmacies"},
    {"code": "HORECA", "name": "HORECA", "description": "Hotels, restaurants, cafes, and catering"},
    {"code": "INSTITUTIONAL", "name": "Institutional", "description": "Hospitals, corporate offices, and institutional buyers"},
    {"code": "OTHER", "name": "Other", "description": "Miscellaneous and specialized outlets"},
]


def seed_default_beat_types(db: Session) -> None:
    """Ensure default beat types exist in the database."""
    try:
        count = db.query(BeatTypeMaster).count()
        if count == 0:
            for item in DEFAULT_BEAT_TYPES:
                bt = BeatTypeMaster(
                    code=item["code"],
                    name=item["name"],
                    description=item["description"],
                    is_active=True
                )
                db.add(bt)
            db.commit()
    except Exception as e:
        db.rollback()


def get_all_beat_types(db: Session) -> list[dict]:
    """Fetch active beat types from DB, falling back to defaults if unseeded."""
    try:
        types = db.query(BeatTypeMaster).filter(BeatTypeMaster.is_active == True).order_by(BeatTypeMaster.name).all()
        if types:
            return [{"code": t.code, "name": t.name, "description": t.description} for t in types]
    except Exception:
        pass
    return DEFAULT_BEAT_TYPES
