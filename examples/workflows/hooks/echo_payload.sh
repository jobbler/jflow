#!/usr/bin/env bash
# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Created in whole or in part by AI using Cursor (Grok).
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Demo hook for the workflow `run` action: reads stdin payload and echoes it.
set -euo pipefail
echo "=== echo_payload.sh received stdin ==="
cat
echo
echo "=== end ==="
exit 0
