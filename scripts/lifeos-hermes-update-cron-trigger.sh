#!/usr/bin/env bash
set -euo pipefail

UNIT="lifeos-hermes-update-$(date +%Y%m%d%H%M%S)"
UPDATER="$HOME/.local/bin/lifeos-hermes-update"

if [ ! -x "$UPDATER" ]; then
  echo "Missing updater: $UPDATER" >&2
  exit 1
fi

systemd-run \
  --user \
  --quiet \
  --no-block \
  --collect \
  --unit "$UNIT" \
  --description "LifeOS Hermes fork upstream sync" \
  --working-directory "$HOME/.hermes/hermes-agent" \
  "$UPDATER" >/dev/null
