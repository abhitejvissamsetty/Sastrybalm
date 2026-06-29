"""
CMMS HTTP Adapter — Production-grade with retry logic.
All external calls go through here — business logic never calls CMMS directly.
Credentials come from Company Profile (passed in at runtime, not baked into the adapter).
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


class CMSAdapter:

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 30):
        self.base_url = (base_url or settings.cmms_base_url).rstrip("/")
        self.api_key = api_key or settings.cmms_api_key
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
                        "CMMS %s %s — %s (attempt %d)",
                        method, path, resp.status_code, attempt,
                    )
                    return resp.json()

            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                body = exc.response.text[:500]
                logger.warning(
                    "CMMS %s %s — HTTP %s (attempt %d/%d): %s",
                    method, path, status, attempt, MAX_RETRIES, body,
                )
                # Don't retry client errors (4xx) except 429
                if 400 <= status < 500 and status != 429:
                    raise

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "CMMS %s %s — network error (attempt %d/%d): %s",
                    method, path, attempt, MAX_RETRIES, exc,
                )

            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** (attempt - 1))
                logger.info("CMMS: retrying in %ss…", delay)
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    # ── Public Methods ─────────────────────────────────────────────────────────

    async def create_material_request(self, payload: dict[str, Any]) -> dict:
        """Submit a material request to CMMS (create draft and submit)."""
        logger.info("CMMS: creating material request — ref=%s", payload.get("idempotency_key", "n/a"))
        # 1. Create Draft
        res = await self._request_with_retry("POST", "/api/resource/Material Request", json_data={"data": payload})
        doc_name = res.get("data", {}).get("name") or res.get("name")
        if not doc_name:
            raise ValueError(f"Failed to get document name from creation response: {res}")
            
        # 2. Submit document
        submit_res = await self._request_with_retry("PUT", f"/api/resource/Material Request/{doc_name}", json_data={"docstatus": 1})
        return submit_res.get("data") or submit_res

    async def get_work_order_status(self, work_order_id: str) -> dict:
        """Fetch the current status of a CMMS Material Request."""
        return await self._request_with_retry("GET", f"/api/resource/Material Request/{work_order_id}")

    async def update_work_order_status(self, work_order_id: str, status: str, notes: str = "") -> dict:
        """Update the status of a CMMS Material Request."""
        return await self._request_with_retry(
            "PUT",
            f"/api/resource/Material Request/{work_order_id}",
            json_data={"status": status, "custom_notes": notes},
        )

    async def create_asset_capitalization(self, payload: dict[str, Any]) -> dict:
        """Submit an asset capitalization request to CMMS (create draft and submit)."""
        logger.info("CMMS: creating asset capitalization — ref=%s", payload.get("idempotency_key", "n/a"))
        # 1. Create Draft
        res = await self._request_with_retry("POST", "/api/resource/Asset Capitalization", json_data={"data": payload})
        doc_name = res.get("data", {}).get("name") or res.get("name")
        if not doc_name:
            raise ValueError(f"Failed to get document name from creation response: {res}")
            
        # 2. Submit document
        submit_res = await self._request_with_retry("PUT", f"/api/resource/Asset Capitalization/{doc_name}", json_data={"docstatus": 1})
        return submit_res.get("data") or submit_res

    async def fetch_product_detail(self, item_code: str) -> dict | None:
        """Fetch the full Item document from CMMS, including child tables like `taxes`.
        Required to extract the GST rate, which lives in the `taxes` child table
        as `item_tax_template` (e.g. 'GST 18% - SE-K'), not a flat field.
        """
        try:
            result = await self._request_with_retry(
                "GET", f"/api/resource/Item/{item_code}"
            )
            return result.get("data")
        except Exception as exc:
            logger.warning("CMMS: fetch product detail failed for '%s': %s", item_code, exc)
            return None

    async def test_connection(self) -> bool:
        """Test CMMS API connectivity."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = self.get_headers()
                resp = await client.get(f"{self.base_url}/api/method/frappe.auth.get_logged_user", headers=headers)
                return resp.status_code < 400
        except Exception as exc:
            logger.warning("CMMS connection test failed: %s", exc)
            return False


cmms_adapter = CMSAdapter()
