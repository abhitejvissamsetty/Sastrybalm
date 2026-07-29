"""Write short-lived deterministic role tokens for Flutter backend E2E tests."""

import argparse
import json
from pathlib import Path

from app.database import SessionLocal
from app.models.outlet import Outlet
from app.models.user import User
from app.utils.security import create_access_token


USERS = {
    "E2E_ADMIN_TOKEN": "admin",
    "E2E_L4_TOKEN": "l4_manager",
    "E2E_L3_TOKEN": "l3_manager",
    "E2E_L2_TOKEN": "l2_manager",
    "E2E_L1_TOKEN": "l1_rep",
    "E2E_VENDOR_ADMIN_TOKEN": "vendor_admin",
    "E2E_VENDOR_TECHNICIAN_TOKEN": "vendor_technician",
    "E2E_QC_MANAGER_TOKEN": "qc_manager",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8091/api/v1")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        payload = {"E2E_BASE_URL": args.base_url}
        for key, username in USERS.items():
            user = db.query(User).filter(User.username == username).one()
            payload[key] = create_access_token(
                {
                    "sub": str(user.id),
                    "role": user.role.value,
                    "ver": user.token_version,
                }
            )
        payload["E2E_ALLOWED_OUTLET_ID"] = str(
            db.query(Outlet.id).filter(Outlet.code == "ACC-OA").scalar()
        )
        payload["E2E_DENIED_OUTLET_ID"] = str(
            db.query(Outlet.id).filter(Outlet.code == "ACC-OB").scalar()
        )
        Path(args.output).write_text(json.dumps(payload))
    finally:
        db.close()


if __name__ == "__main__":
    main()
