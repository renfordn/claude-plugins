# Builds a repo whose `feature` branch adds two modules that each re-implement the existing
# `app.validation.normalize_email`, and moves `parse_phone` out of app/legacy.py while the
# unchanged app/contacts.py still imports it from there.
set -euo pipefail
g() { git -c user.email=eval@example.com -c user.name=eval "$@"; }
git init -q -b main .
mkdir -p app

cat > app/__init__.py <<'EOF'
EOF
cat > app/validation.py <<'EOF'
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(raw):
    """Trim, lowercase and validate an email address. Raises ValueError if invalid."""
    email = raw.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError(f"invalid email: {raw!r}")
    return email
EOF
cat > app/signup.py <<'EOF'
from app.validation import normalize_email


def register(db, raw_email, name):
    email = normalize_email(raw_email)
    db.insert("users", {"email": email, "name": name})
    return email
EOF
cat > app/legacy.py <<'EOF'
def parse_phone(raw):
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10:
        digits = "1" + digits
    return "+" + digits


def legacy_greeting(name):
    return f"Dear {name}"
EOF
cat > app/contacts.py <<'EOF'
from app.legacy import parse_phone


def add_contact(db, name, raw_phone):
    db.insert("contacts", {"name": name, "phone": parse_phone(raw_phone)})
EOF
g add -A && g commit -qm "Initial app"

git checkout -q -b feature
cat > app/invites.py <<'EOF'
import secrets


def _clean_email(value):
    value = value.strip().lower()
    if "@" not in value or "." not in value.split("@")[-1]:
        raise ValueError("bad email")
    return value


def create_invite(db, inviter_id, raw_email):
    email = _clean_email(raw_email)
    token = secrets.token_urlsafe(16)
    db.insert("invites", {"inviter_id": inviter_id, "email": email, "token": token})
    return token
EOF
cat > app/newsletter.py <<'EOF'
import re


def sanitize_address(addr):
    addr = addr.lower().strip()
    if not re.match(r"[^@]+@[^@]+\.[a-z]+$", addr):
        return None
    return addr


def subscribe(db, raw_email):
    email = sanitize_address(raw_email)
    if email is None:
        return False
    db.insert("subscribers", {"email": email})
    return True
EOF
cat > app/phone.py <<'EOF'
def normalize_phone(raw):
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10:
        digits = "1" + digits
    return "+" + digits
EOF
cat > app/legacy.py <<'EOF'
def legacy_greeting(name):
    return f"Dear {name}"
EOF
g add -A && g commit -qm "Add invites and newsletter; move phone parsing to app/phone.py"
git diff main...feature > PR.diff
