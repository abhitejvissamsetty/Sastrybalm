"""
ZAP (ERPNext) HTTP Adapter — Token-based auth.
Handles: Invoices, Payments, Journal Entries, Expenses, Timesheets, Employee lookup,
User Credentials, POS Profiles, and Customer beat/outlet mappings.
All external calls go through here — business logic never calls ZAP directly.
"""
from __future__ import annotations
import asyncio
import logging
import json
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 2  # seconds


class ZapAdapter:

    def __init__(self, base_url: str = "", api_key: str = "", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key  # format: api_key:api_secret
        self.timeout = timeout

    @property
    def _headers(self) -> dict:
        """Backward compatibility fallback: standard ERPNext token prefix."""
        return {
            "Authorization": f"token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_auth_headers(self, token_type: str = "integration", api_key: str | None = None) -> dict:
        """Token-based auth using standard ERPNext 'token' prefix."""
        key = api_key or self.api_key
        return {
            "Authorization": f"token {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request_with_retry(
        self, method: str, path: str,
        data: dict | None = None,
        params: dict | None = None,
        token_type: str = "integration",
        api_key: str | None = None,
        use_fallback_auth: bool = False,
    ) -> dict[str, Any]:
        """Execute an HTTP request with exponential backoff retry."""
        url = f"{self.base_url}{path}"
        headers = self._headers if use_fallback_auth else self.get_auth_headers(token_type, api_key)
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method == "GET":
                        resp = await client.get(url, headers=headers, params=params)
                    elif method == "POST":
                        resp = await client.post(url, headers=headers, json=data)
                    elif method == "PUT":
                        resp = await client.put(url, headers=headers, json=data)
                    elif method == "DELETE":
                        resp = await client.delete(url, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    resp.raise_for_status()
                    logger.info(
                        "ZAP %s %s — %s (attempt %d)",
                        method, path, resp.status_code, attempt,
                    )
                    return resp.json()

            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                body = exc.response.text[:500]
                logger.warning(
                    "ZAP %s %s — HTTP %s (attempt %d/%d): %s",
                    method, path, status, attempt, MAX_RETRIES, body,
                )
                # Don't retry client errors (4xx) except 429
                if 400 <= status < 500 and status != 429:
                    raise

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "ZAP %s %s — network error (attempt %d/%d): %s",
                    method, path, attempt, MAX_RETRIES, exc,
                )

            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** (attempt - 1))
                logger.info("ZAP: retrying in %ss…", delay)
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    # ── Public Methods ─────────────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        """Test ZAP API connectivity by fetching logged-in user (Integration level)."""
        try:
            result = await self._request_with_retry(
                "GET", "/api/method/frappe.auth.get_logged_user",
                token_type="integration"
            )
            return bool(result.get("message"))
        except Exception as exc:
            logger.warning("ZAP connection test failed with integration_token: %s. Retrying with token fallback...", exc)
            try:
                result = await self._request_with_retry(
                    "GET", "/api/method/frappe.auth.get_logged_user",
                    use_fallback_auth=True
                )
                return bool(result.get("message"))
            except Exception as fallback_exc:
                logger.warning("ZAP connection test fallback failed: %s", fallback_exc)
                return False

    async def fetch_company_mapping(self, company_name: str) -> dict | None:
        """Validate mapped company exist in ZAP (Integration level)."""
        params = {
            "filters": json.dumps([["name", "=", company_name]]),
        }
        try:
            result = await self._request_with_retry(
                "GET", "/api/resource/Company",
                params=params, token_type="integration"
            )
            data = result.get("data", [])
            return data[0] if data else None
        except Exception as exc:
            logger.warning("ZAP: company mapping check failed for '%s': %s", company_name, exc)
            return None

    async def get_or_generate_credentials(self, user_email: str) -> dict | None:
        """Retrieve/generate user credentials from ZAP (Integration level)."""
        params = {
            "user_email": user_email,
        }
        try:
            result = await self._request_with_retry(
                "GET", "/api/method/get_or_generate_credentials",
                params=params, token_type="integration"
            )
            return result.get("message")
        except Exception as exc:
            logger.warning("ZAP: credentials generation failed for user '%s': %s", user_email, exc)
            return None

    async def fetch_employee_by_email(self, email: str, user_api_key: str) -> dict | None:
        """Fetch employee details using the salesperson's user token."""
        params = {
            "filters": json.dumps([["user_id", "=", email]]),
            "fields": json.dumps(["name"]),
        }
        try:
            result = await self._request_with_retry(
                "GET", "/api/resource/Employee",
                params=params, token_type="user", api_key=user_api_key
            )
            data = result.get("data", [])
            return data[0] if data else None
        except Exception as exc:
            logger.warning("ZAP: employee fetch failed for '%s': %s", email, exc)
            return None

    async def fetch_products(self, company: str | None = None) -> list[dict]:
        """Fetch item master from ZAP (Integration level)."""
        filters = [
            ["has_variants", "=", 0],
            ["item_group", "=", "Products"],
            ["disabled", "=", 0]
        ]
        if company:
            filters.append(["Item Default", "company", "=", company])
            
        params = {
            "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate"]),
            "filters": json.dumps(filters),
            "limit_page_length": 0,
        }
        try:
            result = await self._request_with_retry(
                "GET", "/api/resource/Item",
                params=params, token_type="integration"
            )
            return result.get("data", [])
        except Exception as exc:
            logger.warning("ZAP: fetch products failed: %s", exc)
            return []

    async def fetch_product_detail(self, item_code: str) -> dict | None:
        """Fetch the full Item document from ZAP, including child tables like `taxes`.
        Required to extract the GST rate, which lives in the `taxes` child table
        as `item_tax_template` (e.g. 'GST 12% - SE-K'), not a flat field.
        """
        try:
            result = await self._request_with_retry(
                "GET", f"/api/resource/Item/{item_code}",
                token_type="integration"
            )
            return result.get("data")
        except Exception as exc:
            logger.warning("ZAP: fetch product detail failed for '%s': %s", item_code, exc)
            return None

    async def fetch_pos_profiles(self, user_email: str, company: str, user_api_key: str | None = None) -> list[dict]:
        """Get POS Profiles associated with a User - List (User level or Integration level fallback)."""
        params = {
            "filters": json.dumps([
                ["POS Profile User", "user", "=", user_email],
                ["company", "=", company]
            ]),
            "fields": json.dumps([
                "name", "warehouse", "company", "write_off_account", "write_off_cost_center", "selling_price_list"
            ]),
        }
        key = user_api_key or self.api_key
        token_type = "user" if user_api_key else "integration"
        try:
            result = await self._request_with_retry(
                "GET", "/api/resource/POS Profile",
                params=params, token_type=token_type, api_key=key
            )
            return result.get("data", [])
        except Exception as exc:
            logger.warning("ZAP: fetch POS Profiles failed for '%s': %s", user_email, exc)
            return []

    async def fetch_pos_profile_detail(self, profile_id: str, user_api_key: str | None = None) -> dict | None:
        """Query detailed fields and child tables of a POS Profile (User level or Integration level fallback)."""
        params = {
            "fields": json.dumps([
                "name", "warehouse", "company", "write_off_account", "write_off_cost_center", "selling_price_list"
            ]),
        }
        key = user_api_key or self.api_key
        token_type = "user" if user_api_key else "integration"
        try:
            result = await self._request_with_retry(
                "GET", f"/api/resource/POS Profile/{profile_id}",
                params=params, token_type=token_type, api_key=key
            )
            return result.get("data")
        except Exception as exc:
            logger.warning("ZAP: fetch POS Profile detail failed for '%s': %s", profile_id, exc)
            return None

    async def fetch_customer_mapping(self, outlet_id: str, user_api_key: str | None = None) -> list[dict]:
        """Get Customer Details/ Outlet mapping by beat ID (User level or Integration level fallback)."""
        params = {
            "filters": json.dumps([["custom_beat_id_1", "=", outlet_id]]),
            "fields": json.dumps([
                "name", "customer_name", "customer_group", "territory"
            ]),
        }
        key = user_api_key or self.api_key
        token_type = "user" if user_api_key else "integration"
        try:
            result = await self._request_with_retry(
                "GET", "/api/resource/Customer",
                params=params, token_type=token_type, api_key=key
            )
            return result.get("data", [])
        except Exception as exc:
            logger.warning("ZAP: Customer mapping failed for beat outlet ID '%s': %s", outlet_id, exc)
            return []

    # ── Legacy/Submissions Methods (Using Fallback Auth) ─────────────────────

    async def create_sales_invoice(self, payload: dict[str, Any]) -> dict:
        """Create a Sales Invoice in ZAP."""
        logger.info("ZAP: creating sales invoice — ref=%s", payload.get("naming_series", "n/a"))
        return await self._request_with_retry(
            "POST", "/api/resource/Sales Invoice",
            data={"data": payload}, use_fallback_auth=True
        )

    async def create_payment_entry(self, payload: dict[str, Any]) -> dict:
        """Create a Payment Entry in ZAP."""
        logger.info("ZAP: creating payment entry — amount=%s", payload.get("paid_amount", "n/a"))
        return await self._request_with_retry(
            "POST", "/api/resource/Payment Entry",
            data={"data": payload}, use_fallback_auth=True
        )

    async def create_journal_entry(self, payload: dict[str, Any]) -> dict:
        """Create a Journal Entry in ZAP (for payment denomination submissions)."""
        logger.info("ZAP: creating journal entry — ref=%s", payload.get("cheque_no", "n/a"))
        return await self._request_with_retry(
            "POST", "/api/resource/Journal Entry",
            data={"data": payload}, use_fallback_auth=True
        )
