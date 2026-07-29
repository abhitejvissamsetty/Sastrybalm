#!/usr/bin/env python3
"""High-volume, self-cleaning release performance gate.

Run inside the app container so cgroup CPU/memory measurements cover Gunicorn
and the load generator. Every seeded row has a unique run prefix and is removed
in dependency order even when a budget fails.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal
from app.models.beat import Beat
from app.models.order import Order, OrderItem
from app.models.outlet import Outlet
from app.models.product import Product
from app.models.user import User, UserRole
from app.utils.security import create_access_token


ROOT = Path(__file__).resolve().parent


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percent * len(ordered)) - 1)
    return ordered[index]


def read_number(path: str) -> int:
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return 0


def cpu_usage_usec() -> int:
    try:
        for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines():
            if line.startswith("usage_usec "):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def allocated_cpu_count() -> float:
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            return max(0.1, int(quota) / int(period))
    except (OSError, ValueError):
        pass
    return float(os.cpu_count() or 1)


class MemorySampler:
    def __init__(self) -> None:
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(0.05):
            self.peak = max(
                self.peak, read_number("/sys/fs/cgroup/memory.current")
            )

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_args):
        self._stop.set()
        self._thread.join()
        self.peak = max(
            self.peak, read_number("/sys/fs/cgroup/memory.current")
        )


def seed_dataset(db, prefix: str, outlet_count: int, order_count: int):
    rep = (
        db.query(User)
        .filter(User.role == UserRole.field_rep, User.is_active == True)
        .first()
    )
    product = db.query(Product).filter(Product.is_active == True).first()
    beat = None
    if rep:
        for position in rep.positions:
            beat = next((item for item in position.beats if item.is_active), None)
            if beat:
                break
    beat = beat or db.query(Beat).filter(Beat.is_active == True).first()
    if not rep or not product or not beat:
        raise RuntimeError(
            "Deterministic base fixtures require an active field rep, product, and beat."
        )

    db.bulk_insert_mappings(
        Outlet,
        [
            {
                "name": f"{prefix} Outlet {index:05d}",
                "code": f"{prefix}-OUT-{index:05d}",
                "beat_id": beat.id,
                "territory_id": beat.territory_id,
                "gps_lat": 13.0827 + (index % 100) / 10000,
                "gps_lng": 80.2707 + (index % 100) / 10000,
                "status": "active",
                "is_active": True,
            }
            for index in range(outlet_count)
        ],
    )
    db.commit()
    outlet_ids = [
        row[0]
        for row in db.query(Outlet.id)
        .filter(Outlet.code.like(f"{prefix}-OUT-%"))
        .order_by(Outlet.id)
        .all()
    ]

    db.bulk_insert_mappings(
        Order,
        [
            {
                "order_number": f"{prefix}-ORD-{index:06d}",
                "outlet_id": outlet_ids[index % len(outlet_ids)],
                "party_id": outlet_ids[index % len(outlet_ids)],
                "party_type": "Outlet",
                "user_id": rep.id,
                "beat_id": beat.id,
                "company_profile_id": rep.company_profile_id,
                "order_type": "secondary",
                "status": "confirmed",
                "flow_type": "native_order",
                "sync_status": "not_applicable",
                "payment_settlement": "unpaid",
                "order_date": date.today(),
                "is_company_order": False,
                "is_paid": False,
                "is_archived": False,
                "sync_retries": 0,
            }
            for index in range(order_count)
        ],
    )
    db.commit()
    order_ids = [
        row[0]
        for row in db.query(Order.id)
        .filter(Order.order_number.like(f"{prefix}-ORD-%"))
        .order_by(Order.id)
        .all()
    ]
    db.bulk_insert_mappings(
        OrderItem,
        [
            {
                "order_id": order_id,
                "product_id": product.id,
                "quantity": 2,
                "unit_price": 100,
                "gst_rate": 18,
                "discount_pct": 0,
                "is_archived": False,
            }
            for order_id in order_ids
        ],
    )
    db.commit()
    return rep, outlet_ids, order_ids


def cleanup_dataset(db, prefix: str) -> None:
    order_ids = db.query(Order.id).filter(
        Order.order_number.like(f"{prefix}-ORD-%")
    )
    db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids)).delete(
        synchronize_session=False
    )
    db.query(Order).filter(
        Order.order_number.like(f"{prefix}-ORD-%")
    ).delete(synchronize_session=False)
    db.query(Outlet).filter(
        Outlet.code.like(f"{prefix}-OUT-%")
    ).delete(synchronize_session=False)
    db.commit()


def request_once(base_url: str, path: str, token: str | None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(base_url + path, headers=headers), timeout=15
        ) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
    except Exception:
        status = 0
    return path, status, (time.perf_counter() - started) * 1000


def database_metrics(db, rep_id: int) -> tuple[float, float]:
    started = time.perf_counter()
    (
        db.query(Order.id)
        .filter(Order.user_id == rep_id)
        .order_by(Order.created_at.desc())
        .offset(0)
        .limit(100)
        .all()
    )
    query_ms = (time.perf_counter() - started) * 1000
    connected = int(db.execute(text("SHOW STATUS LIKE 'Threads_connected'")).one()[1])
    maximum = int(db.execute(text("SHOW VARIABLES LIKE 'max_connections'")).one()[1])
    return query_ms, connected / maximum * 100


def run(args) -> dict:
    budgets = json.loads(Path(args.budgets).read_text())
    if args.outlets < budgets["dataset"]["outlets_minimum"]:
        raise ValueError("Outlet count is below the release dataset minimum.")
    if args.orders < budgets["dataset"]["orders_minimum"]:
        raise ValueError("Order count is below the release dataset minimum.")

    prefix = "PERF" + uuid.uuid4().hex[:10].upper()
    db = SessionLocal()
    report = {"run_id": prefix, "started_at": datetime.utcnow().isoformat() + "Z"}
    try:
        rep, outlet_ids, order_ids = seed_dataset(
            db, prefix, args.outlets, args.orders
        )
        token = create_access_token({"sub": str(rep.id), "ver": rep.token_version})
        db_query_ms, db_connection_pct = database_metrics(db, rep.id)

        scenarios = [
            ("/api/v1/outlets?page=1&per_page=200", token, "sync_outlets"),
            ("/api/v1/orders/my?page=1&per_page=100", token, "sync_orders"),
            ("/api/v1/beats?page=1&per_page=100", token, "hierarchy"),
            ("/static/performance-probe.svg", None, "image"),
        ]
        expanded = [scenarios[index % len(scenarios)] for index in range(args.requests)]
        cpu_start = cpu_usage_usec()
        wall_start = time.perf_counter()
        with MemorySampler() as memory:
            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                futures = [
                    executor.submit(request_once, args.base_url, path, auth)
                    for path, auth, _name in expanded
                ]
                raw = [future.result() for future in as_completed(futures)]
        wall_seconds = time.perf_counter() - wall_start
        cpu_seconds = max(0, cpu_usage_usec() - cpu_start) / 1_000_000

        latencies = [row[2] for row in raw]
        image_latencies = [
            row[2] for row in raw if row[0].endswith("performance-probe.svg")
        ]
        errors = [row for row in raw if not 200 <= row[1] < 400]
        allocated_cpus = allocated_cpu_count()
        report.update({
            "dataset": {"outlets": len(outlet_ids), "orders": len(order_ids)},
            "requests": len(raw),
            "concurrency": args.concurrency,
            "p50_latency_ms": round(percentile(latencies, 0.50), 2),
            "p95_latency_ms": round(percentile(latencies, 0.95), 2),
            "image_p95_latency_ms": round(percentile(image_latencies, 0.95), 2),
            "error_rate_pct": round(len(errors) / len(raw) * 100, 4),
            "throughput_rps": round(len(raw) / wall_seconds, 2),
            "database_query_ms": round(db_query_ms, 2),
            "database_connection_utilization_pct": round(db_connection_pct, 2),
            "average_cpu_pct": round(
                cpu_seconds / wall_seconds / allocated_cpus * 100, 2
            ),
            "memory_peak_mb": round(memory.peak / 1024 / 1024, 2),
        })
        checks = {
            "dataset_outlets": report["dataset"]["outlets"] >= budgets["dataset"]["outlets_minimum"],
            "dataset_orders": report["dataset"]["orders"] >= budgets["dataset"]["orders_minimum"],
            "latency": report["p95_latency_ms"] <= budgets["http"]["p95_latency_ms_max"],
            "image_latency": report["image_p95_latency_ms"] <= budgets["http"]["image_p95_latency_ms_max"],
            "error_rate": report["error_rate_pct"] <= budgets["http"]["error_rate_pct_max"],
            "throughput": report["throughput_rps"] >= budgets["http"]["throughput_rps_min"],
            "database_latency": report["database_query_ms"] <= budgets["database"]["representative_query_ms_max"],
            "database_connections": report["database_connection_utilization_pct"] <= budgets["database"]["connection_utilization_pct_max"],
            "cpu": report["average_cpu_pct"] <= budgets["resources"]["average_cpu_pct_max"],
            "memory": report["memory_peak_mb"] <= budgets["resources"]["memory_peak_mb_max"],
        }
        report["checks"] = checks
        report["passed"] = all(checks.values())
        return report
    finally:
        cleanup_dataset(db, prefix)
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8090")
    parser.add_argument("--budgets", default=str(ROOT / "budgets.json"))
    parser.add_argument("--outlets", type=int, default=2000)
    parser.add_argument("--orders", type=int, default=5000)
    parser.add_argument("--requests", type=int, default=400)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--report", default=str(ROOT / "latest-report.json"))
    args = parser.parse_args()
    report = run(args)
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
