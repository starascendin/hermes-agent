#!/usr/bin/env bash
set -euo pipefail

REPO="${HERMES_REPO:-$HOME/.hermes/hermes-agent}"
SERVICE="${HERMES_GATEWAY_SERVICE:-hermes-gateway.service}"
FORK_REMOTE="${HERMES_LIFEOS_FORK_REMOTE:-origin}"
UPSTREAM_REMOTE="${HERMES_UPSTREAM_REMOTE:-upstream}"
UPSTREAM_URL="${HERMES_UPSTREAM_URL:-https://github.com/NousResearch/hermes-agent.git}"
FORK_URL="${HERMES_LIFEOS_FORK_URL:-https://github.com/starascendin/hermes-agent.git}"

cd "$REPO"

echo "==> LifeOS Hermes update"
echo "repo: $REPO"

if ! git remote get-url "$FORK_REMOTE" >/dev/null 2>&1; then
  git remote add "$FORK_REMOTE" "$FORK_URL"
else
  git remote set-url "$FORK_REMOTE" "$FORK_URL"
fi

if ! git remote get-url "$UPSTREAM_REMOTE" >/dev/null 2>&1; then
  git remote add "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
else
  git remote set-url "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
fi

stash_ref=""
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "==> Stashing local work before update"
  git stash push -u -m "lifeos-hermes-update-auto-stash-$(date -Iseconds)" >/dev/null
  stash_ref="stash@{0}"
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "main" ]; then
  echo "==> Switching from $current_branch to main"
  git checkout main
fi

echo "==> Fetching fork and upstream"
git fetch "$FORK_REMOTE" main
git fetch "$UPSTREAM_REMOTE" main

echo "==> Resetting local main to fork/main"
git reset --hard "$FORK_REMOTE/main"

echo "==> Rebasing LifeOS fork commits onto official Hermes main"
git rebase "$UPSTREAM_REMOTE/main"

echo "==> Pushing rebased LifeOS main to fork"
git push --force-with-lease "$FORK_REMOTE" main

was_active=0
if systemctl --user is-active --quiet "$SERVICE"; then
  was_active=1
  echo "==> Stopping $SERVICE"
  systemctl --user stop "$SERVICE"
fi

restart_if_needed() {
  if [ "$was_active" = "1" ]; then
    echo "==> Starting $SERVICE"
    systemctl --user start "$SERVICE" || true
  fi
}
trap restart_if_needed EXIT

echo "==> Clearing Python bytecode cache"
find "$REPO" -type d -name __pycache__ -prune -exec rm -rf {} +

venv_python="$REPO/venv/bin/python"
if [ ! -x "$venv_python" ]; then
  venv_python="$(command -v python3)"
fi

echo "==> Reinstalling Hermes Python package"
if command -v uv >/dev/null 2>&1 && [ -x "$REPO/venv/bin/python" ]; then
  VIRTUAL_ENV="$REPO/venv" uv pip install -e ".[all]" || "$venv_python" -m pip install -e ".[all]"
else
  "$venv_python" -m pip install -e ".[all]"
fi

if command -v npm >/dev/null 2>&1 && [ -f package.json ]; then
  echo "==> Refreshing root node dependencies"
  npm install --no-audit --no-fund
fi

if command -v npm >/dev/null 2>&1 && [ -f web/package.json ]; then
  echo "==> Refreshing web dependencies"
  npm --prefix web install --no-audit --no-fund
  if npm --prefix web run | grep -q " build"; then
    echo "==> Building web UI"
    npm --prefix web run build
  fi
fi

if [ -n "$stash_ref" ]; then
  echo "==> Local work was preserved in git stash: $stash_ref"
  echo "    Review with: git stash show --stat $stash_ref"
fi

echo "==> Done"
git --no-pager log --oneline -3
