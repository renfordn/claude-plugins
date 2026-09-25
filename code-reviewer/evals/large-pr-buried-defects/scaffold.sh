# Builds the large-pr-buried-defects repo: `main`, then a `feature` branch PR (see make_repo.py).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
g() { git -c user.email=eval@example.com -c user.name=eval "$@"; }
git init -q -b main .
python3 "$here/make_repo.py" base
g add -A && g commit -qm "Inventory service"
git checkout -q -b feature
python3 "$here/make_repo.py" feature
g add -A && g commit -qm "Warehouse-scoped stock, prices in cents, structured logging"
git diff main...feature > PR.diff
