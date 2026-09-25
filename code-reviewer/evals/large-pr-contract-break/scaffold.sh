# Builds a small repo whose `feature` branch is a 9-file PR against `main` with three planted
# defects: an unchanged caller broken by a signature change (app/reports.py), an off-by-one
# buried in a refactor (app/pagination.py), and a behavior change with no test change
# (app/pricing.py). Everything else in the PR is benign noise.
set -euo pipefail
g() { git -c user.email=eval@example.com -c user.name=eval "$@"; }
git init -q -b main .
mkdir -p app tests migrations

cat > app/__init__.py <<'EOF'
EOF
cat > app/users.py <<'EOF'
def get_user(conn, user_id):
    row = conn.execute(
        "SELECT id, email, name FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def list_users(conn):
    return [dict(r) for r in conn.execute("SELECT id, email, name FROM users")]
EOF
cat > app/reports.py <<'EOF'
from app import users


def monthly_report(conn, user_ids):
    lines = []
    for uid in user_ids:
        user = users.get_user(conn, uid)
        if user is None:
            continue
        lines.append(f"{user['name']} <{user['email']}>")
    return "\n".join(lines)
EOF
cat > app/pricing.py <<'EOF'
def apply_discount(total, pct):
    return total * (1 - pct / 100)
EOF
cat > tests/test_pricing.py <<'EOF'
from app.pricing import apply_discount


def test_ten_percent():
    assert apply_discount(100, 10) == 90
EOF
cat > app/pagination.py <<'EOF'
def paginate(items, page, size):
    """Return the 1-indexed `page` of `items`, `size` items per page."""
    start = (page - 1) * size
    return items[start:start + size]
EOF
cat > app/orders.py <<'EOF'
from app import users


def order_summary(conn, order):
    user = users.get_user(conn, order["user_id"])
    return f"Order {order['id']} for {user['email']}: {order['total']}"
EOF
cat > app/notify.py <<'EOF'
def build_message(user, text):
    return f"Hi {user['name']}, {text}"
EOF
cat > app/config.py <<'EOF'
PAGE_SIZE = 20
EOF
cat > app/formatting.py <<'EOF'
def title_case(s):
    return s.title()
EOF
echo "# Shop service" > README.md
g add -A && g commit -qm "Initial service"

git checkout -q -b feature
cat > app/users.py <<'EOF'
def get_user(conn, user_id, include_deleted):
    query = "SELECT id, email, name, deleted_at FROM users WHERE id = ?"
    if not include_deleted:
        query += " AND deleted_at IS NULL"
    row = conn.execute(query, (user_id,)).fetchone()
    return dict(row) if row else None


def list_users(conn, include_deleted=False):
    query = "SELECT id, email, name, deleted_at FROM users"
    if not include_deleted:
        query += " WHERE deleted_at IS NULL"
    return [dict(r) for r in conn.execute(query)]


def soft_delete(conn, user_id):
    conn.execute("UPDATE users SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
EOF
cat > app/pricing.py <<'EOF'
MAX_DISCOUNT_PCT = 50


def apply_discount(total, pct):
    """Apply a percentage discount, capped at MAX_DISCOUNT_PCT, rounded to cents."""
    pct = min(pct, MAX_DISCOUNT_PCT)
    return round(total * (1 - pct / 100), 2)
EOF
cat > app/pagination.py <<'EOF'
from app.config import PAGE_SIZE


def paginate(items, page, size=PAGE_SIZE):
    """Return the 1-indexed `page` of `items`, `size` items per page."""
    if page < 1:
        raise ValueError("page must be >= 1")
    if size < 1:
        raise ValueError("size must be >= 1")
    start = page * size
    return items[start:start + size]


def page_count(items, size=PAGE_SIZE):
    return (len(items) + size - 1) // size
EOF
cat > app/orders.py <<'EOF'
from app import users
from app.formatting import format_money


def order_summary(conn, order):
    user = users.get_user(conn, order["user_id"], include_deleted=True)
    return f"Order {order['id']} for {user['email']}: {format_money(order['total'])}"
EOF
cat > app/notify.py <<'EOF'
import logging

log = logging.getLogger(__name__)


def build_message(recipient, body):
    log.debug("building message for %s", recipient.get("email"))
    return f"Hi {recipient['name']}, {body}"
EOF
cat > app/config.py <<'EOF'
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
SOFT_DELETE_ENABLED = True
EOF
cat > app/formatting.py <<'EOF'
def title_case(s):
    return s.title()


def format_money(amount):
    return f"${amount:,.2f}"
EOF
cat > migrations/002_add_deleted_at.sql <<'EOF'
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP NULL;
CREATE INDEX idx_users_deleted_at ON users (deleted_at);
EOF
cat > README.md <<'EOF'
# Shop service

Users are soft-deleted: `users.soft_delete()` sets `deleted_at`, and lookups hide deleted
users unless `include_deleted` is passed. Lists are paginated 20 per page by default.
EOF
g add -A && g commit -qm "Soft-delete users, cap discounts, pagination defaults"
git diff main...feature > PR.diff
