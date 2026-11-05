#!/usr/bin/env bash
# ==============================================================================
# jflow - interactive release helper
# Co-created through collaborative AI pair programming with Gemini.
# ==============================================================================
# Suggests the next semver (patch bump by default; manual entry allowed),
# updates pyproject.toml and jflow/version.py, appends changelog entries to
# the [Unreleased] section, and converts it into a new dated release.
# File edits only: no git commit / tag / push.
# ==============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SECTIONS=(Added Changed Deprecated Removed Fixed Security)

die() {
    echo "error: $*" >&2
    exit 1
}

# --- Guardrail: refuse to run over uncommitted changes to the files we edit ---
if command -v git >/dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    if ! git -C "$REPO_ROOT" diff --quiet -- pyproject.toml jflow/version.py CHANGELOG.md 2>/dev/null \
       || ! git -C "$REPO_ROOT" diff --cached --quiet -- pyproject.toml jflow/version.py CHANGELOG.md 2>/dev/null; then
        die "uncommitted changes to pyproject.toml, jflow/version.py, or CHANGELOG.md; commit or stash them first"
    fi
fi

# --- Read current version from both sources; they must agree ---------------
py_version="$(python3 - "$REPO_ROOT" <<'EOF'
import re, sys, pathlib
text = (pathlib.Path(sys.argv[1]) / "pyproject.toml").read_text()
m = re.search(r'^version = "([^"]+)"', text, re.M)
if not m:
    sys.exit(1)
print(m.group(1))
EOF
)" || die "no version = \"...\" line found in pyproject.toml"

vpy_version="$(python3 - "$REPO_ROOT" <<'EOF'
import re, sys, pathlib
text = (pathlib.Path(sys.argv[1]) / "jflow" / "version.py").read_text()
m = re.search(r'^__version__ = "([^"]+)"', text, re.M)
if not m:
    sys.exit(1)
print(m.group(1))
EOF
)" || die "no __version__ = \"...\" line found in jflow/version.py"

[ "$py_version" = "$vpy_version" ] \
    || die "version mismatch: pyproject.toml says $py_version, jflow/version.py says $vpy_version"

CURRENT="$py_version"
python3 -c "x,y,z = '$CURRENT'.split('.'); int(x); int(y); int(z)" \
    || die "current version $CURRENT is not X.Y.Z semver"

IFS='.' read -r CX CY CZ <<<"$CURRENT"
SUGGESTED="$CX.$CY.$((CZ + 1))"

echo "Current version: $CURRENT"

# --- Ask for the new version ------------------------------------------------
NEW=""
while :; do
    if ! read -r -p "New version [$SUGGESTED]: " NEW; then
        echo
        NEW="$SUGGESTED"
    fi
    [ -z "$NEW" ] && NEW="$SUGGESTED"
    if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "  '$NEW' is not X.Y.Z; try again."
        continue
    fi
    if ! python3 -c "import sys; sys.exit(0 if tuple(map(int, sys.argv[1].split('.'))) > tuple(map(int, sys.argv[2].split('.'))) else 1)" "$NEW" "$CURRENT"; then
        echo "  $NEW is not greater than $CURRENT; try again."
        continue
    fi
    break
done


echo "Bumping $CURRENT -> $NEW"
echo

# --- Collect changelog entries ----------------------------------------------
for section in "${SECTIONS[@]}"; do
    entries=""
    echo "$section:"
    while :; do
        if ! read -r -p "  $section entry (blank line to finish): " line; then
            echo
            break
        fi
        [ -z "$line" ] && break
        entries+="$line"$'\n'
    done
    echo
    export "JFLOW_ENTRIES_${section}=${entries%$'\n'}"
done

# --- Apply all file edits in one python3 pass -------------------------------
export JFLOW_OLD_VERSION="$CURRENT" JFLOW_NEW_VERSION="$NEW"
python3 - "$REPO_ROOT" <<'EOF'
import datetime, os, pathlib, re, subprocess, sys

root = pathlib.Path(sys.argv[1])
old, new = os.environ["JFLOW_OLD_VERSION"], os.environ["JFLOW_NEW_VERSION"]
sections = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
entries = {s: [l for l in os.environ.get(f"JFLOW_ENTRIES_{s}", "").splitlines() if l]
           for s in sections}

# --- pyproject.toml ---
p = root / "pyproject.toml"
text, n = re.subn(r'^version = "[^"]+"$', f'version = "{new}"',
                  p.read_text(), count=1, flags=re.M)
assert n == 1, "pyproject.toml: expected exactly one version = line"
p.write_text(text)

# --- jflow/version.py ---
p = root / "jflow" / "version.py"
text, n = re.subn(r'^__version__ = "[^"]+"$', f'__version__ = "{new}"',
                  p.read_text(), count=1, flags=re.M)
assert n == 1, "jflow/version.py: expected exactly one __version__ = line"
p.write_text(text)

# --- CHANGELOG.md ---
p = root / "CHANGELOG.md"
text = p.read_text()

m = re.search(r"^## \[Unreleased\][ \t]*$", text, re.M)
assert m, "CHANGELOG.md: no '## [Unreleased]' heading found"
start = m.end()
nm = re.search(r"^## ", text[start:], re.M)
end = start + nm.start() if nm else len(text)
unreleased_body = text[start:end]

# Parse existing bullets per section (duplicate headings of the same section
# are merged in the order encountered). A line starting with anything other
# than "- " is a wrapped continuation of the previous bullet and is re-joined
# with a single space, so re-wrapping after appending stays consistent.
existing = {s: [] for s in sections}
for hm in re.finditer(r"^### (\w+)[ \t]*$", unreleased_body, re.M):
    sec = hm.group(1)
    if sec not in existing:
        continue
    bstart = hm.end()
    bn = re.search(r"^### ", unreleased_body[bstart:], re.M)
    bend = bstart + bn.start() if bn else len(unreleased_body)
    for line in unreleased_body[bstart:bend].splitlines():
        if not line.strip():
            continue
        if line.startswith("- "):
            existing[sec].append(line[2:])
        elif existing[sec]:
            existing[sec][-1] += " " + line.strip()
        else:
            raise AssertionError(f"unexpected line under ### {sec}: {line!r}")

def wrap_bullet(entry):
    # fold the entry text at 77 cols (space-split); first line gets "- "
    # (2 chars), continuations get 2 spaces -> rendered width <= 79.
    proc = subprocess.run(["fold", "-s", "-w", "77"], input=entry, text=True,
                          capture_output=True, check=True)
    lines = proc.stdout.rstrip("\n").split("\n")
    return "- " + lines[0].rstrip() + "".join("\n  " + l.rstrip() for l in lines[1:])

today = datetime.date.today().isoformat()
rebuilt = ""
for s in sections:
    bullets = [wrap_bullet(e) for e in existing[s] + entries[s]]
    if not bullets:
        continue
    rebuilt += f"### {s}\n\n" + "\n".join(bullets) + "\n\n"

new_text = (text[:m.start()]
            + f"## [Unreleased]\n\n## [{new}] - {today}\n\n"
            + rebuilt
            + text[end:])
p.write_text(new_text)

print("Files updated:")
print(f"  pyproject.toml:   version {old} -> {new}")
print(f"  jflow/version.py: __version__ {old} -> {new}")
print(f"  CHANGELOG.md:     [Unreleased] -> [{new}] - {today}")
for s in sections:
    if entries[s]:
        print(f"    {s}: {len(entries[s])} new entr{'y' if len(entries[s]) == 1 else 'ies'}")
EOF

echo
echo "Done. Review the changes; no git actions were taken."
