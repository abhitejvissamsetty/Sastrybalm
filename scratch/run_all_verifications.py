import subprocess
import sys
import os

test_files = [
    "scratch/test_order_flows.py",
    "scratch/test_ist_timezone.py",
    "scratch/test_mobile_api.py",
    "scratch/test_beat_creation_scoping.py",
    "scratch/test_core_infrastructure.py",
    "scratch/test_dashboard_kpis.py",
    "scratch/test_dual_pane_alerts.py",
    "scratch/test_restricted_modules.py",
    "scratch/test_alerts_scoping.py",
]

def run_verifications():
    print("==================================================")
    print("   SAFAR SYSTEM-WIDE VERIFICATION TEST SUITE     ")
    print("==================================================")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    passed = 0
    failed = 0
    failures = []

    for test_file in test_files:
        print(f"\n▶ Running {test_file}...")
        res = subprocess.run([sys.executable, test_file], env=env, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ PASSED: {test_file}")
            passed += 1
        else:
            print(f"❌ FAILED: {test_file}")
            print(res.stdout)
            print(res.stderr)
            failed += 1
            failures.append(test_file)

    print("\n==================================================")
    print(f"SUMMARY: {passed} PASSED, {failed} FAILED")
    print("==================================================")

    if failed > 0:
        print(f"FAILED TESTS: {failures}")
        sys.exit(1)
    else:
        print("ALL SYSTEM VERIFICATIONS 100% SUCCESSFUL! 🎉")

if __name__ == "__main__":
    run_verifications()
