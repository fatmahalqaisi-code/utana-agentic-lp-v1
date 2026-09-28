#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repository_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

cd "$repository_root"

./scripts/build-public.sh
python3 scripts/verify-public.py public public-files.txt
python3 scripts/verify-seo.py public public-files.txt
git diff --check
node scripts/browser-smoke.mjs public "${SCREENSHOT_DIR:-/tmp/utana-launch-screenshots}"

if command -v nginx >/dev/null 2>&1; then
  nginx -t
else
  printf 'Nginx is not installed; runtime Nginx validation is deferred to deployment/staging.\n'
fi

printf 'Launch validation passed.\n'
