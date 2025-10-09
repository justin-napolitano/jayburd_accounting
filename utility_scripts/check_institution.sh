#!/usr/bin/env bash
# find_institution.sh
# Prints ONLY the institution object(s) whose id or name contains the query (case-insensitive).
# Usage: ./find_institution.sh "wells"

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required. Install it and try again." >&2
  exit 3
fi

URL="${TELLER_INSTITUTIONS_URL:-https://api.teller.io/institutions}"
QUERY="${1:-}"

if [[ -z "$QUERY" ]]; then
  echo "usage: $0 <institution-substring>" >&2
  exit 2
fi

CURL_OPTS=(--silent --show-error --fail --connect-timeout 10)

# Optional auth knobs because Teller loves “options.”
[[ -n "${TELLER_SECRET:-}"   ]] && CURL_OPTS+=(-u "${TELLER_SECRET}:")
[[ -n "${TELLER_CERT:-}"     ]] && CURL_OPTS+=(--cert "${TELLER_CERT}")
[[ -n "${TELLER_KEY:-}"      ]] && CURL_OPTS+=(--key "${TELLER_KEY}")
[[ -n "${TELLER_CA_PATH:-}"  ]] && CURL_OPTS+=(--cacert "${TELLER_CA_PATH}")

JSON="$(curl "${CURL_OPTS[@]}" "$URL")"

# Filter to only matching objects; print as a JSON array or, if 1 match, the object itself.
FILTERED="$(jq -c --arg q "$QUERY" '
  [ .[]
    | select(
        ((.id // "") + " " + (.name // ""))
        | ascii_downcase
        | contains($q | ascii_downcase)
      )
  ]' <<<"$JSON")"

COUNT="$(jq 'length' <<<"$FILTERED")"

if [[ "$COUNT" -eq 0 ]]; then
  # nothing. cry about it.
  exit 1
elif [[ "$COUNT" -eq 1 ]]; then
  # unwrap single result to just the object
  jq '.[0]' <<<"$FILTERED"
else
  # multiple hits; return the array so you can pick your poison upstream
  jq '.' <<<"$FILTERED"
fi
