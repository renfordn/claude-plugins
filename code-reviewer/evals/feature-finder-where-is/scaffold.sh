# Builds a repo with the retry backoff in retry.py and a decoy client.py without any backoff, so a
# memory hint pointing at client.py is contradicted by the checkout. `feature` is a trivial PR
# branch (the eval structure test requires one).
set -euo pipefail
g() { git -c user.email=eval@example.com -c user.name=eval "$@"; }
git init -q -b main .
cat > retry.py <<'EOF'
import time


def backoff_delay(attempt, base=0.5, cap=8.0):
    """Seconds to wait before retry number `attempt` (0-based)."""
    return min(cap, base * (2 ** attempt))


def call_with_retry(fn, attempts=3):
    for attempt in range(attempts):
        try:
            return fn()
        except ConnectionError:
            time.sleep(backoff_delay(attempt))
    return fn()
EOF
cat > client.py <<'EOF'
from retry import call_with_retry


def fetch(session, url):
    return call_with_retry(lambda: session.get(url))
EOF
echo "# Demo" > README.md
g add -A && g commit -qm "Add retry and client"
g checkout -q -b feature
echo "Retries use exponential delays." >> README.md
g add -A && g commit -qm "Document retries"
git diff main...feature > PR.diff
