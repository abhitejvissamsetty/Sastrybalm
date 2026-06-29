"""
CONNECT Distribution API Adapter — Production-grade with retry logic.
All calls are async and routed through the job queue — never block a web request.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 2  # seconds


class ConnectAdapter:

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 30):
        self.base_url = (base_url or settings.connect_base_url).rstrip("/")
        self.api_key = api_key or settings.connect_api_key
        self.timeout = timeout

    def get_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"token {self.api_key}"
        return headers

    async def _request_with_retry(
        self, method: str, path: str,
        json_data: dict | list | None = None,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with exponential backoff retry."""
        url = f"{self.base_url}{path}"
        headers = self.get_headers()
        
        # If urlencoded form-data is sent, let httpx set Content-Type
        if data is not None and "Content-Type" in headers:
            headers = headers.copy()
            headers.pop("Content-Type")

        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method == "GET":
                        resp = await client.get(url, headers=headers, params=params)
                    elif method == "POST":
                        resp = await client.post(url, headers=headers, json=json_data, data=data)
                    elif method == "PUT":
                        resp = await client.put(url, headers=headers, json=json_data, data=data)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    resp.raise_for_status()
                    logger.info(
                        "CONNECT %s %s — %s (attempt %d)",
                        method, path, resp.status_code, attempt,
                    )
                    return resp.json()

            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                body = exc.response.text[:500]
                logger.warning(
                    "CONNECT %s %s — HTTP %s (attempt %d/%d): %s",
                    method, path, status, attempt, MAX_RETRIES, body,
                )
                if 400 <= status < 500 and status != 429:
                    raise

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "CONNECT %s %s — network error (attempt %d/%d): %s",
                    method, path, attempt, MAX_RETRIES, exc,
                )

            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** (attempt - 1))
                logger.info("CONNECT: retrying in %ss…", delay)
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    # ── Public Methods ─────────────────────────────────────────────────────────

    async def submit_order(self, payload: dict[str, Any]) -> dict:
        """Submit an order to the CONNECT distribution platform."""
        logger.info("CONNECT: submitting order ref=%s", payload.get("idempotency_key", "n/a"))
        return await self._request_with_retry("POST", "/api/resource/Connect Order", json_data={"data": payload})

    async def get_order_status(self, order_ref: str) -> dict:
        """Check the sync status of an order on CONNECT."""
        return await self._request_with_retry("GET", f"/api/resource/Connect Order/{order_ref}")

    async def test_connection(self) -> bool:
        """Test CONNECT API connectivity."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = self.get_headers()
                resp = await client.get(f"{self.base_url}/api/method/frappe.auth.get_logged_user", headers=headers)
                return resp.status_code < 400
        except Exception as exc:
            logger.warning("CONNECT connection test failed: %s", exc)
            return False

    # ── Authentication ─────────────────────────────────────────────────────────

    async def send_otp(self, email: str, full_name: str | None = None) -> dict:
        """Sends a 6-digit OTP to the user's email address."""
        data = {"email": email}
        if full_name:
            data["full_name"] = full_name
        return await self._request_with_retry("POST", "/api/method/connect_master.api.send_otp", data=data)

    async def verify_otp(self, email: str, otp: str) -> dict:
        """Verifies the OTP and logs in the user."""
        data = {"email": email, "otp": otp}
        return await self._request_with_retry("POST", "/api/method/connect_master.api.verify_otp", data=data)

    # ── Metadata & Configs ─────────────────────────────────────────────────────

    async def get_user_info(self) -> dict:
        """Returns current logged in user's roles and linked Channel Partners."""
        return await self._request_with_retry("GET", "/api/method/connect_master.api.get_user_info")

    async def get_allowed_territories(self) -> dict:
        """Returns territories the current user has access to."""
        return await self._request_with_retry("GET", "/api/method/connect_master.api.get_allowed_territories")

    async def get_allowed_service_categories(self) -> dict:
        """Returns Service Channels current user has access to."""
        return await self._request_with_retry("GET", "/api/method/connect_master.api.get_allowed_service_categories")

    async def search_addresses_for_punch(self, query: str) -> dict:
        """Returns lists of addresses classified as 'allowed' or 'restricted'."""
        params = {"query": query}
        return await self._request_with_retry("GET", "/api/method/connect_master.api.search_addresses_for_punch", params=params)

    async def get_connect_items(self, fields: list[str] | None = None, filters: dict | None = None) -> dict:
        """Fetches a list of active Connect Items."""
        import json
        params = {}
        if fields:
            params["fields"] = json.dumps(fields)
        if filters:
            params["filters"] = json.dumps(filters)
        return await self._request_with_retry("GET", "/api/resource/Connect Item", params=params)

    async def fetch_product_detail(self, item_code: str) -> dict | None:
        """Fetch the full Connect Item document, including child tables like `taxes`."""
        try:
            result = await self._request_with_retry(
                "GET", f"/api/resource/Connect Item/{item_code}"
            )
            return result.get("data")
        except Exception as exc:
            logger.warning("CONNECT: fetch product detail failed for '%s': %s", item_code, exc)
            return None

    # ── Address & Contact ──────────────────────────────────────────────────────

    async def get_addresses(self, fields: list[str] | None = None, filters: list | None = None) -> dict:
        """Fetches a list of Addresses."""
        import json
        params = {}
        if fields:
            params["fields"] = json.dumps(fields)
        if filters:
            params["filters"] = json.dumps(filters)
        return await self._request_with_retry("GET", "/api/resource/Address", params=params)

    async def create_address(self, address_doc: dict) -> dict:
        """Creates a new Address linked to the User."""
        return await self._request_with_retry("POST", "/api/resource/Address", json_data={"data": address_doc})

    async def get_contacts(self, fields: list[str] | None = None) -> dict:
        """Fetches a list of Contacts."""
        import json
        params = {}
        if fields:
            params["fields"] = json.dumps(fields)
        return await self._request_with_retry("GET", "/api/resource/Contact", params=params)

    async def create_contact(self, contact_doc: dict) -> dict:
        """Creates a new Contact linked to the User and an Address."""
        return await self._request_with_retry("POST", "/api/resource/Contact", json_data={"data": contact_doc})

    # ── Orders Querying ────────────────────────────────────────────────────────

    async def get_compass_orders(
        self, tab: str = "Active", start: int = 0, page_len: int = 50,
        filters: dict | None = None, search: str | None = None
    ) -> dict:
        """Fetches filtered and paginated list of Connect Orders."""
        import json
        params = {"tab": tab, "start": start, "page_len": page_len}
        if filters:
            params["filters"] = json.dumps(filters)
        if search:
            params["search"] = search
        return await self._request_with_retry("GET", "/api/method/connect_master.api.get_compass_orders", params=params)

    async def get_order_counts(self) -> dict:
        """Returns counts for orders classified in 'Active', 'Unresolved', and 'History'."""
        return await self._request_with_retry("GET", "/api/method/connect_master.api.get_order_counts")

    # ── Order Lifecycle ────────────────────────────────────────────────────────

    async def assign_channel_partner(self, order_name: str, channel_partner: str) -> dict:
        """Assigns an order to a localized Channel Partner."""
        data = {"order_name": order_name, "channel_partner": channel_partner}
        return await self._request_with_retry("POST", "/api/method/connect_master.api.assign_channel_partner", data=data)

    async def accept_order(self, order_name: str, notes: str | None = None) -> dict:
        """Invoked by Channel Partner to accept the assigned order."""
        data = {"order_name": order_name}
        if notes:
            data["notes"] = notes
        return await self._request_with_retry("POST", "/api/method/connect_master.api.accept_order", data=data)

    async def reject_order(self, order_name: str, notes: str | None = None) -> dict:
        """Invoked by Channel Partner to reject the assignment."""
        data = {"order_name": order_name}
        if notes:
            data["notes"] = notes
        return await self._request_with_retry("POST", "/api/method/connect_master.api.reject_order", data=data)

    async def mark_order_delivered(self, order_name: str, delivery_date: str, delivery_notes: str | None = None) -> dict:
        """Completes the order workflow by marking it 'Fulfilled'."""
        data = {"order_name": order_name, "delivery_date": delivery_date}
        if delivery_notes:
            data["delivery_notes"] = delivery_notes
        return await self._request_with_retry("POST", "/api/method/connect_master.api.mark_order_delivered", data=data)

    async def cancel_order(self, order_name: str, notes: str | None = None) -> dict:
        """Cancels the order, marking the status as 'Cancelled'."""
        data = {"order_name": order_name}
        if notes:
            data["notes"] = notes
        return await self._request_with_retry("POST", "/api/method/connect_master.api.cancel_order", data=data)

    async def release_territory(self, order_name: str) -> dict:
        """Escalates the order's resolved territory to its parent-most root territory."""
        data = {"order_name": order_name}
        return await self._request_with_retry("POST", "/api/method/connect_master.api.release_territory", data=data)

    async def update_territory(self, order_name: str, new_territory: str) -> dict:
        """Manually updates the address's resolved territory name."""
        data = {"order_name": order_name, "new_territory": new_territory}
        return await self._request_with_retry("POST", "/api/method/connect_master.api.update_territory", data=data)

    async def update_service_category(self, order_name: str, new_category: str) -> dict:
        """Updates both the order service category and delivery address category."""
        data = {"order_name": order_name, "new_category": new_category}
        return await self._request_with_retry("POST", "/api/method/connect_master.api.update_service_category", data=data)

    async def add_comment(self, order_name: str, comment: str, is_internal: int = 0) -> dict:
        """Adds a timeline comment/note to the order."""
        data = {"order_name": order_name, "comment": comment, "is_internal": is_internal}
        return await self._request_with_retry("POST", "/api/method/connect_master.api.add_comment", data=data)

    # ── Order Intelligence ─────────────────────────────────────────────────────

    async def resolve_territory(self, pincode: int) -> dict:
        """Gets Resolved Territory for the Address pincode."""
        return await self._request_with_retry("POST", "/api/method/connect_master.api.resolve_territory", json_data={"pincode": pincode})

    async def get_channel_partners(self, territory: str, channel: str) -> dict:
        """Gets Channel Partner List for the Resolved Service Territory & Service Channel."""
        return await self._request_with_retry(
            "POST",
            "/api/method/connect_master.connect_master.doctype.connect_order.connect_order.get_channel_partners",
            json_data={"territory": territory, "channel": channel}
        )

    async def submit_connect_order_doc(self, order_name: str) -> dict:
        """Submits the Connect Order record manually (sets docstatus=1)."""
        return await self._request_with_retry("PUT", f"/api/resource/Connect Order/{order_name}", json_data={"docstatus": 1})


connect_adapter = ConnectAdapter()
