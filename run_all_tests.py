# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from pathlib import Path
import subprocess
import sys

tests_dir = Path(__file__).parent / "tests"

phase_tests = [
    "test_phase1.py",
    "test_phase2.py",
    "test_phase3.py",
    "test_phase3_templates.py",
    "test_phase4.py",
    "test_phase5a.py",
    "test_phase5b.py",
    "test_phase5b_sprint.py",
    "test_phase5c.py",
    "test_phase5d.py",
    "test_phase5e.py",
    "test_phase6.py",
    "test_phase7.py",
    "test_phase8.py",
    "test_phase9.py",
    "test_config_paths.py",
    "test_staging_runner.py",
    "test_adf_text_fields.py",
    "test_field_schema.py",
    "test_staging_workflow_fixture.py",
    "test_run_cmd.py",
    "test_boards_resolve.py",
    "test_status_version.py",
    "test_formatter_flatten.py",
    "test_issue_show_list.py",
    "test_cli_ux.py",
    "test_oauth.py",
    "test_trailing_text.py",
    "test_current_sprint_link_pr.py",
    "test_client_empty_body.py",
    "test_workflow_vars.py",
    "test_issue_convert.py",
]

failed = False
for test_file in phase_tests:
    test_path = tests_dir / test_file
    print(f"Running {test_file}...", end=" ")
    res = subprocess.run([sys.executable, str(test_path)], capture_output=True, text=True)
    if res.returncode == 0:
        print("PASSED")
    else:
        print("FAILED")
        print("--- Output ---")
        print(res.stdout or res.stderr)
        print("--------------")
        failed = True

if not failed:
    print("\nAll phase verification tests passed!")
