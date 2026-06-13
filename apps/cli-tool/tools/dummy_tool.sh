#!/usr/bin/env bash

set -euo pipefail

case "${1:-}" in
  --ping)
    cat <<'JSON'
{"tool":"dummy_tool","status":"ok","message":"dummy tool reached"}
JSON
    ;;
  *)
    cat <<'JSON'
{"tool":"dummy_tool","status":"ok","message":"pass --ping to verify tool plumbing"}
JSON
    ;;
esac
