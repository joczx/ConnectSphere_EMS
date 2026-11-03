#!/usr/bin/env bash
# Usage: bash smoke.sh [api-base-url] [web-base-url]
set -euo pipefail

API="${1:-http://127.0.0.1:5000}"
WEB="${2:-http://127.0.0.1:4173}"
API="${API%/}"
WEB="${WEB%/}"

wait_for() {
  local url="$1"

  for attempt in $(seq 1 30); do
    if curl -fsS "$url" > /dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "No response from $url"
  return 1
}

wait_for "$API/"
wait_for "$WEB/"

# The Flask application in the release package starts and returns its expected
# public root response without needing database credentials.
curl -fsS "$API/" | python -c '
import json
import sys

response = json.load(sys.stdin)
assert response["message"] == "ConnectSphere Flask API is running!"
'

# The built React entry point and its generated JavaScript and CSS assets must
# all be present. This catches incomplete release ZIPs before they are offered
# for delivery.
index_file="$(mktemp)"
trap 'rm -f "$index_file"' EXIT
curl -fsS "$WEB/" -o "$index_file"

grep -q '<title>ConnectSphere</title>' "$index_file"
grep -q '<div id="root"></div>' "$index_file"

js_asset="$(grep -oE 'src="/assets/[^"]+\.js"' "$index_file" | head -1 | cut -d'"' -f2)"
css_asset="$(grep -oE 'href="/assets/[^"]+\.css"' "$index_file" | head -1 | cut -d'"' -f2)"

test -n "$js_asset"
test -n "$css_asset"

curl -fsS "$WEB$js_asset" > /dev/null
curl -fsS "$WEB$css_asset" > /dev/null

echo "ConnectSphere release package smoke tests passed."
