import ast
from pathlib import Path

from app.models.user import User
from app.utils.pagination import MAX_PER_PAGE, paginate


COLLECTION_ENDPOINTS = {
    "app/routers/admin_leaves.py": {"list_leaves"},
    "app/routers/analytics.py": {"reps_data"},
    "app/routers/company.py": {
        "profile_list", "product_mappings_list", "account_mappings_list",
    },
    "app/routers/outlets.py": {"outlet_history"},
    "app/routers/retailing.py": {"api_retailing_beats", "retailing_beat_view"},
    "app/routers/settings.py": {
        "sales_channels_list", "warehouses_list", "webhooks_settings_form",
    },
    "app/routers/tracking.py": {"gps_map_data"},
    "app/routers/api/leaves.py": {"get_my_leaves"},
    "app/routers/api/journey_plan.py": {"get_journey_plan"},
    "app/routers/api/master.py": {
        "geography_tree",
        "beat_daily_plan",
        "outlet_list",
        "product_list",
        "get_beats",
        "get_my_beats",
        "get_l1_position_beats",
    },
    "app/routers/api/operations.py": {
        "get_my_timesheets",
        "get_outlet_today_l1_orders",
        "my_orders",
        "get_my_expenses",
        "material_request_context",
        "outlet_asset_products",
        "outlet_assets",
        "attendance_history",
        "my_visits",
        "my_payments",
        "my_expenses",
        "my_material_requests",
        "pending_qc_work_orders",
        "get_subordinate_beats",
    },
    "app/routers/api/procurement_workflow.py": {
        "list_procurement_material_requests",
        "get_maintenance_logs",
        "list_work_orders",
        "list_procurement_items",
        "list_procured_assets",
        "list_maintenance_logs",
        "list_vendors",
    },
}


def test_all_mobile_collection_endpoints_declare_bounded_pagination():
    root = Path(__file__).parents[1]
    failures = []
    for relative_path, expected_functions in COLLECTION_ENDPOINTS.items():
        tree = ast.parse((root / relative_path).read_text())
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name in expected_functions:
            node = functions[name]
            args = {argument.arg for argument in node.args.args}
            calls = {
                call.func.attr
                for call in ast.walk(node)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            }
            named_calls = {
                call.func.id
                for call in ast.walk(node)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            }
            delegates_to_bounded_helper = "resolve_user_hierarchy_beats" in named_calls
            delegates_to_bounded_helper |= "paginate" in named_calls
            required_args = {"page"} if "paginate" in named_calls else {"page", "per_page"}
            if not required_args <= args:
                failures.append(
                    f"{relative_path}:{name} lacks {sorted(required_args - args)}"
                )
            if not {"offset", "limit"} <= calls and not delegates_to_bounded_helper:
                failures.append(f"{relative_path}:{name} lacks offset/limit")
    assert failures == []


def test_shared_web_paginator_enforces_server_side_maximum(db_session):
    result = paginate(db_session.query(User), page=-3, per_page=10_000)
    assert result.page == 1
    assert result.per_page == MAX_PER_PAGE
    assert MAX_PER_PAGE == 100
