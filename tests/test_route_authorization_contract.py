"""Regression guard: identifier routes must use centralized object access."""

import inspect

from app.main import app


ADMIN_ONLY_IDENTIFIER_CREATION = {
    ("app.routers.vendors", "vendor_create"),
}


def _endpoint_routes():
    return [route for route in app.routes if hasattr(route, "endpoint")]


def test_every_parameterized_object_route_uses_central_access_service():
    failures = []
    for route in _endpoint_routes():
        if "{" not in route.path or route.endpoint.__module__ == "app.main":
            continue
        source = inspect.getsource(inspect.unwrap(route.endpoint))
        if "require_" not in source:
            failures.append(
                f"{','.join(sorted(route.methods or []))} {route.path} "
                f"({route.endpoint.__module__}.{route.endpoint.__name__})"
            )
    assert failures == []


def test_query_and_body_identifiers_are_scoped_or_admin_only():
    failures = []
    for route in _endpoint_routes():
        endpoint = inspect.unwrap(route.endpoint)
        parameters = inspect.signature(endpoint).parameters
        identifiers = [
            name
            for name in parameters
            if name.endswith("_id") or name.endswith("_ids")
        ]
        if not identifiers or route.endpoint.__module__ == "app.main":
            continue
        source = inspect.getsource(endpoint)
        identity = (route.endpoint.__module__, route.endpoint.__name__)
        if (
            "require_" not in source
            and identity not in ADMIN_ONLY_IDENTIFIER_CREATION
        ):
            failures.append(
                f"{route.path} ({'.'.join(identity)}): {identifiers}"
            )
    assert failures == []
