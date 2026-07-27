"""
Self-contained ZAP Adapter Diagnostic & Integration Test Suite.
Launches an in-process HTTP server on a local port to test socket connectivity,
headers, serialization, and data transfer for all specified endpoints.
"""
import asyncio
import http.server
import json
import socketserver
import threading
import sys
from typing import Optional, Union, List, Dict
from urllib.parse import urlparse, parse_qs, unquote
from app.adapters.zap import ZapAdapter


# Port to run mock server on
MOCK_PORT = 8085
mock_server: Optional[socketserver.TCPServer] = None
server_thread: Optional[threading.Thread] = None


class MockZapHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suppress logging request details to keep test output clean
        return

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        parsed_url = urlparse(self.path)
        path = unquote(parsed_url.path)
        query = parse_qs(parsed_url.query)

        # 1. Logged In User
        if path == "/api/method/frappe.auth.get_logged_user":
            if auth == "token test_api_key:test_api_secret":
                self.send_success({"message": "admin@example.com"})
            else:
                self.send_unauthorized("Invalid integration_token")

        # 2. Company Mapping
        elif path.lower() == "/api/resource/company":
            if auth == "token test_api_key:test_api_secret":
                filters_str = query.get("filters", ["[]"])[0]
                filters = json.loads(filters_str)
                if filters == [["name", "=", "Zap Test Enterprise"]]:
                    self.send_success({"data": [{"name": "Zap Test Enterprise"}]})
                else:
                    self.send_bad_request(f"Unexpected filters: {filters}")
            else:
                self.send_unauthorized("Invalid integration_token")

        # 3. User's Access Tokens
        elif path == "/api/method/get_or_generate_credentials":
            if auth == "token test_api_key:test_api_secret":
                user_email = query.get("user_email", [""])[0]
                if user_email == "salesrep@example.com":
                    self.send_success({
                        "message": {
                            "api_key": "user_api_key_xyz",
                            "api_secret": "user_api_secret_abc"
                        }
                    })
                else:
                    self.send_bad_request(f"Unexpected user_email: {user_email}")
            else:
                self.send_unauthorized("Invalid integration_token")

        # 4. Employee details from ZAP
        elif path.lower() == "/api/resource/employee":
            if auth == "token user_api_key_xyz:user_api_secret_abc":
                filters_str = query.get("filters", ["[]"])[0]
                fields_str = query.get("fields", ["[]"])[0]
                filters = json.loads(filters_str)
                fields = json.loads(fields_str)
                if filters == [["user_id", "=", "salesrep@example.com"]] and fields == ["name"]:
                    self.send_success({"data": [{"name": "EMP-001"}]})
                else:
                    self.send_bad_request(f"Unexpected filters {filters} or fields {fields}")
            else:
                self.send_unauthorized("Invalid user_token")

        # 5. List of Products (Item)
        elif path.lower() == "/api/resource/item":
            if auth == "token test_api_key:test_api_secret":
                filters_str = query.get("filters", ["[]"])[0]
                fields_str = query.get("fields", ["[]"])[0]
                filters = json.loads(filters_str)
                fields = json.loads(fields_str)
                expected_filters = [
                    ["has_variants", "=", 0],
                    ["item_group", "=", "Products"],
                    ["disabled", "=", 0],
                    ["Item Default", "company", "=", "Zap Test Enterprise"]
                ]
                if filters == expected_filters and fields == ["name", "item_name"]:
                    self.send_success({"data": [
                        {"name": "PROD-01", "item_name": "Balm Regular"},
                        {"name": "PROD-02", "item_name": "Balm Extra Strong"}
                    ]})
                else:
                    self.send_bad_request(f"Unexpected filters {filters} or fields {fields}")
            else:
                self.send_unauthorized("Invalid integration_token")

        # 6. Get POS Profiles List
        elif path == "/api/resource/POS Profile":
            if auth == "token user_api_key_xyz:user_api_secret_abc":
                filters_str = query.get("filters", ["[]"])[0]
                filters = json.loads(filters_str)
                if ["POS Profile User", "user", "=", "salesrep@example.com"] in filters and ["company", "=", "Zap Test Enterprise"] in filters:
                    self.send_success({"data": [
                        {"name": "POS-01", "warehouse": "Main Warehouse", "company": "Zap Test Enterprise"}
                    ]})
                else:
                    self.send_bad_request(f"Unexpected filters: {filters}")
            else:
                self.send_unauthorized("Invalid user_token")

        # 7. Get POS Profile Detail (Specific Profile ID)
        elif path.startswith("/api/resource/POS Profile/"):
            profile_id = path.split("/")[-1]
            if auth == "token user_api_key_xyz:user_api_secret_abc":
                if profile_id == "POS-01":
                    self.send_success({"data": {
                        "name": "POS-01",
                        "warehouse": "Main Warehouse",
                        "company": "Zap Test Enterprise",
                        "payments": [{"mode_of_payment": "Cash"}]
                    }})
                else:
                    self.send_bad_request(f"Unexpected profile ID: {profile_id}")
            else:
                self.send_unauthorized("Invalid user_token")

        # 8. Customer Details / Outlet Mapping
        elif path == "/api/resource/Customer":
            if auth == "token user_api_key_xyz:user_api_secret_abc":
                filters_str = query.get("filters", ["[]"])[0]
                filters = json.loads(filters_str)
                if filters == [["custom_beat_id_1", "=", "OUTLET-123"]]:
                    self.send_success({"data": [
                        {"name": "CUST-999", "company": "Zap Test Enterprise"}
                    ]})
                else:
                    self.send_bad_request(f"Unexpected filters: {filters}")
            else:
                self.send_unauthorized("Invalid user_token")

        else:
            self.send_response(404)
            self.end_headers()

    def send_success(self, data: dict):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_unauthorized(self, reason: str):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Unauthorized", "reason": reason}).encode())

    def send_bad_request(self, reason: str):
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Bad Request", "reason": reason}).encode())


def start_mock_server():
    global mock_server, server_thread
    socketserver.TCPServer.allow_reuse_address = True
    mock_server = socketserver.TCPServer(("", MOCK_PORT), MockZapHandler)
    server_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    server_thread.start()


def stop_mock_server():
    global mock_server
    if mock_server:
        mock_server.shutdown()
        mock_server.server_close()


async def run_diagnostics():
    print("\n" + "="*80)
    print("🚀 STARTING SAFAR ZAP API INTEGRATION DIAGNOSTIC TEST SUITE")
    print("="*80)

    # 1. Start Server
    print("📡 Spinning up in-process HTTP mock server on port 8085...")
    start_mock_server()
    print("🟢 Mock server is listening on http://localhost:8085")

    # Initialize Adapter
    adapter = ZapAdapter(
        base_url="http://localhost:8085",
        api_key="test_api_key:test_api_secret"
    )

    tests_run = 0
    tests_passed = 0

    try:
        # TEST 1: Connection test (Logged in user)
        print("\n📝 Test 1: Testing Connection (frappe.auth.get_logged_user)...")
        tests_run += 1
        is_connected = await adapter.test_connection()
        if is_connected:
            print("  ✅ Success: Connected cleanly! Authorized with integration_token.")
            tests_passed += 1
        else:
            print("  ❌ Failed: Connection test returned False.")

        # TEST 2: Company Mapping
        print("\n📝 Test 2: Checking Company Name Mapping (Customer / company)...")
        tests_run += 1
        company = await adapter.fetch_company_mapping("Zap Test Enterprise")
        if company and company.get("name") == "Zap Test Enterprise":
            print("  ✅ Success: Company verified and mapped: Zap Test Enterprise")
            tests_passed += 1
        else:
            print(f"  ❌ Failed: Company mapping check failed. Result: {company}")

        # TEST 3: User Access Token retrieval
        print("\n📝 Test 3: Fetching Access Tokens (get_or_generate_credentials)...")
        tests_run += 1
        creds = await adapter.get_or_generate_credentials("salesrep@example.com")
        if creds and creds.get("api_key") == "user_api_key_xyz":
            print("  ✅ Success: Retrieved user credentials successfully!")
            tests_passed += 1
        else:
            print(f"  ❌ Failed: Access credentials retrieval failed. Result: {creds}")

        # Save user credentials for subsequent user-level tests
        user_key = f"{creds.get('api_key')}:{creds.get('api_secret')}" if creds else ""

        # TEST 4: Fetch Employee by Email
        print("\n📝 Test 4: Fetching Employee Details (employee query)...")
        tests_run += 1
        emp = await adapter.fetch_employee_by_email("salesrep@example.com", user_key)
        if emp and emp.get("name") == "EMP-001":
            print("  ✅ Success: Employee looked up successfully! Authenticated with user_token.")
            tests_passed += 1
        else:
            print(f"  ❌ Failed: Employee fetch lookup failed. Result: {emp}")

        # TEST 5: Fetch Products with correct Child Table Filter
        print("\n📝 Test 5: Fetching Products (Item Defaults Child Table Filter)...")
        tests_run += 1
        products = await adapter.fetch_products("Zap Test Enterprise")
        if len(products) == 2 and products[0]["name"] == "PROD-01":
            print("  ✅ Success: Product list fetched and filtered using 'Item Default' child table!")
            tests_passed += 1
        else:
            print(f"  ❌ Failed: Product list fetch failed. Result: {products}")

        # TEST 6: Fetch User POS Profiles
        print("\n📝 Test 6: Fetching POS Profiles associated with User (POS Profile)...")
        tests_run += 1
        profiles = await adapter.fetch_pos_profiles("salesrep@example.com", "Zap Test Enterprise", user_key)
        if len(profiles) == 1 and profiles[0]["name"] == "POS-01":
            print("  ✅ Success: POS Profiles fetched successfully using user_token!")
            tests_passed += 1
        else:
            print(f"  ❌ Failed: POS Profile fetch failed. Result: {profiles}")

        # TEST 7: POS Profile Detail lookup
        print("\n📝 Test 7: Fetching POS Profile Detail child tables...")
        tests_run += 1
        detail = await adapter.fetch_pos_profile_detail("POS-01", user_key)
        if detail and detail.get("warehouse") == "Main Warehouse":
            print("  ✅ Success: POS Profile details retrieved successfully!")
            tests_passed += 1
        else:
            print(f"  ❌ Failed: POS Profile detail lookup failed. Result: {detail}")

        # TEST 8: Customer Beat / Outlet mapping
        print("\n📝 Test 8: Fetching Customer Outlet Beat Mapping (Customer)...")
        tests_run += 1
        mapping = await adapter.fetch_customer_mapping("OUTLET-123", user_key)
        if len(mapping) == 1 and mapping[0]["name"] == "CUST-999":
            print("  ✅ Success: Outlet successfully mapped to ZAP Customer!")
            tests_passed += 1
        else:
            print(f"  ❌ Failed: Outlet mapping look failed. Result: {mapping}")

    finally:
        print("\n📡 Shutting down mock HTTP server...")
        stop_mock_server()
        print("🟢 Mock server stopped.")

    print("\n" + "="*80)
    print(f"📊 DIAGNOSTIC RESULTS: {tests_passed}/{tests_run} TESTS PASSED")
    print("="*80)
    if tests_passed == tests_run:
        print("🎉 CONGRATULATIONS! ALL API ENDPOINTS ARE FULLY OPERATIONAL AND TRANSFERRING DATA PERFECTLY!")
        sys.exit(0)
    else:
        print("🚨 WARN: SOME INTEGRATION TESTS ENCOUNTERED FAILURES.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
