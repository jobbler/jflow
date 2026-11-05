#!/usr/bin/env bash
# ==============================================================================
# jflow - dev environment setup (source me!)
# Co-created through collaborative AI pair programming with Gemini.
# ==============================================================================
# Usage:   source scripts/setup-env.sh
# Creates .venv, installs the package editable + pytest, copies
# examples/config/user.yaml to user.yaml.local (if missing), wires
# JFLOW_USER_YAML into the venv activate/deactivate scripts, and activates
# the venv in the caller's shell.
# ==============================================================================

# --- Must be sourced: executing this directly cannot activate the venv ------
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    echo "error: this script must be sourced, not executed:" >&2
    echo "  source ${BASH_SOURCE[0]}" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Create .venv if missing ------------------------------------------------
if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
    echo "Creating .venv ..."
    python3 -m venv "$REPO_ROOT/.venv" || { echo "error: venv creation failed" >&2; return 1 2>/dev/null || exit 1; }
fi

# --- Upgrade pip, install package editable + test deps ----------------------
"$REPO_ROOT/.venv/bin/python" -m pip install --upgrade pip
"$REPO_ROOT/.venv/bin/pip" install -e "$REPO_ROOT"
"$REPO_ROOT/.venv/bin/pip" install pytest

# --- Local config ------------------------------------------------------------
if [ ! -f "$REPO_ROOT/user.yaml.local" ]; then
    cp "$REPO_ROOT/examples/config/user.yaml" "$REPO_ROOT/user.yaml.local"
    echo
    echo "==================================================================="
    echo "Copied examples/config/user.yaml to user.yaml.local"
    echo "Edit it and add your Jira credentials before running tests."
    echo "==================================================================="
    echo
else
    echo "user.yaml.local already exists; leaving it untouched."
fi

# --- Activate-script hooks ---------------------------------------------------
ACTIVATE="$REPO_ROOT/.venv/bin/activate"

if ! grep -q 'jflow: point JFLOW_USER_YAML' "$ACTIVATE"; then
    printf '\n# jflow: point JFLOW_USER_YAML at the repo-local test config\nexport JFLOW_USER_YAML="%s/user.yaml.local"\n' \
        "$REPO_ROOT" >> "$ACTIVATE"
else
    echo "activate hook already present; not duplicating."
fi

if ! grep -q 'jflow: unset JFLOW_USER_YAML' "$ACTIVATE"; then
    # insert unset as the first statement of deactivate(), right after its
    # opening line, via python for a safe anchored multi-line edit.
    "$REPO_ROOT/.venv/bin/python" - "$ACTIVATE" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text()
needle = "deactivate () {\n"
assert needle in text, "no deactivate() function found in activate script"
text = text.replace(needle, needle + "    # jflow: unset JFLOW_USER_YAML\n    unset JFLOW_USER_YAML\n", 1)
p.write_text(text)
EOF
else
    echo "deactivate hook already present; not duplicating."
fi

# --- Activate in the caller's shell ------------------------------------------
. "$REPO_ROOT/.venv/bin/activate"

echo
echo "Environment ready. Follow-ups:"
echo "  pytest                                        # unit suite (repo root)"
echo "      note: tests/test_phase1.py asserts real credentials, so fill in"
echo "      user.yaml.local first"
echo "  python scripts/run_all_tests.py               # alternative runner"
echo "  python -m jflow.staging.cli --user-yaml $REPO_ROOT/user.yaml.local --board-id <id>"
echo "      see docs/staging-tests.md"
echo "  secrets can stay out of user.yaml.local via its \${VAR} expansion"
echo "  (e.g. api_token: \"\${JIRA_API_TOKEN}\")"
