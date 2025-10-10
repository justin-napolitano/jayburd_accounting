# ops/scripts/run_teller_jobs_daily.sh
#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd -P)
sh \"$REPO_ROOT/ops/scripts/queue_teller_daily.sh\"
cd \"$REPO_ROOT\" && docker compose run --rm teller-sync
