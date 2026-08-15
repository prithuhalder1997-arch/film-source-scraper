#!/usr/bin/env bash
# One-click launcher. Double-click (after chmod +x) or run: ./run.sh ["Film Title"]
set -e
cd "$(dirname "$0")"

# --- your keys (edit once) ---------------------------------------
export BRAVE_API_KEY="${BRAVE_API_KEY:-PUT_YOUR_BRAVE_KEY}"
export ZOTERO_USER_ID="${ZOTERO_USER_ID:-PUT_YOUR_USER_ID}"
export ZOTERO_API_KEY="${ZOTERO_API_KEY:-PUT_YOUR_API_KEY}"
export HITS_PER_SOURCE="${HITS_PER_SOURCE:-3}"
# -----------------------------------------------------------------

echo ">> Capturing sources (Zotero must be running)…"
python3 scrape.py "$@"

echo ">> Filing into per-film collections…"
python3 zotero_collections.py

echo ">> All done."
