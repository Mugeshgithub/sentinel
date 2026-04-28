#!/usr/bin/env bash
# Install Sentinel pre-commit hook into a target git repository.
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 <path-to-target-repo>" >&2
  exit 1
fi

TARGET_REPO_INPUT="$1"
# Preserve caller path verbatim — `pwd` strips trailing spaces from dirname ("Pyramid revised ").
ABS_TARGET="$TARGET_REPO_INPUT"
if [ ! -d "${ABS_TARGET}/.git" ]; then
  echo "Not a git repository: ${ABS_TARGET}" >&2
  exit 1
fi

if [ -d "${ABS_TARGET}/.husky" ]; then
  HOOK_FILE="${ABS_TARGET}/.husky/pre-commit"
else
  HOOK_FILE="${ABS_TARGET}/.git/hooks/pre-commit"
fi

{
  echo '#!/usr/bin/env bash'
  echo '# Sentinel pre-commit hook — auto-installed by install_hook.sh'
  echo 'set -e'
  echo 'SENTINEL_DIR="/Users/mugesh/Project X/sentinel"'
  printf 'RULES="%s/.sentinel/pyramid.yaml"\n' "${ABS_TARGET%/}"
  echo ''
  echo 'if [ ! -f "$RULES" ]; then'
  echo '  echo "Sentinel: no rules file at $RULES — skipping review."'
  echo '  exit 0'
  echo 'fi'
  echo ''
  echo '# Activate venv and run sentinel against staged changes'
  echo 'source "$SENTINEL_DIR/venv/bin/activate"'
  echo 'cd "$SENTINEL_DIR"'
  printf 'python cli.py "%s" --rules "$RULES" --exit-on-blocker\n' "$ABS_TARGET"
  echo 'STATUS=$?'
  echo ''
  echo 'if [ $STATUS -ne 0 ]; then'
  echo '  echo ""'
  echo '  echo "Sentinel: BLOCKER findings — commit rejected."'
  echo '  echo "Fix the issues above, or run with --no-verify to bypass."'
  echo '  exit 1'
  echo 'fi'
  echo ''
  echo 'exit 0'
} >"$HOOK_FILE"

chmod +x "$HOOK_FILE"

# Also mirror to .git/hooks so the spec path exists; Husky repos use core.hooksPath → .husky.
ALT_HOOK="${ABS_TARGET}/.git/hooks/pre-commit"
if [ "$HOOK_FILE" != "$ALT_HOOK" ]; then
  mkdir -p "${ABS_TARGET}/.git/hooks"
  cp -f "$HOOK_FILE" "$ALT_HOOK"
  chmod +x "$ALT_HOOK"
fi

echo "Installed Sentinel pre-commit hook at $HOOK_FILE"
if [ "$HOOK_FILE" != "$ALT_HOOK" ]; then
  echo "Mirrored to $ALT_HOOK"
fi
