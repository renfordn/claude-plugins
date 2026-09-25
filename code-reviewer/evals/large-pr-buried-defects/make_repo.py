"""Generate the large-pr-buried-defects fixture: an inventory service whose `feature` branch is a
~35-file PR ("warehouse-scoped stock, prices in cents, structured logging") with six planted
defects hidden among ~1,000 lines of mechanical logging/type-hint churn:

  1. jobs/reorder.py (untouched) still calls repos.stock.get_stock, which the PR renamed.
  2. api/export.py renders price_cents with a dollar format (100x too high).
  3. api/admin.py's new delete_warehouse lacks the @require_role("admin") every sibling has.
  4. jobs/batch_import.py's refactor loops range(1, total), skipping the first batch.
  5. services/tax.py swaps Decimal ROUND_HALF_UP for float round(); tests/test_tax.py unchanged.
  6. utils/money.py's new cents_to_str duplicates utils/formatting.format_cents.

Run from an empty directory: python3 make_repo.py <stage>  (stage = base | feature).
"""
import os
import sys
import textwrap

NOUNS = {
    "app/models/warehouse.py": "warehouse", "app/models/order.py": "order",
    "app/models/supplier.py": "supplier", "app/repos/products.py": "product",
    "app/repos/orders.py": "order", "app/repos/suppliers.py": "supplier",
    "app/services/notifications.py": "notice", "app/services/shipping.py": "shipment",
    "app/services/discounts.py": "discount", "app/services/reorder_policy.py": "policy",
    "app/services/inventory.py": "item", "app/api/orders.py": "order",
    "app/api/warehouses.py": "warehouse", "app/api/health.py": "probe",
    "app/api/products.py": "product", "app/api/export.py": "row",
    "app/api/admin.py": "request", "app/jobs/nightly_report.py": "report",
    "app/jobs/cleanup.py": "record", "app/jobs/batch_import.py": "batch",
    "app/utils/dates.py": "date", "app/utils/ids.py": "ident",
    "app/utils/validation.py": "field", "app/services/pricing.py": "line",
    "app/repos/stock.py": "entry", "app/services/tax.py": "rate",
    "app/utils/formatting.py": "value", "app/models/product.py": "product",
    "app/jobs/reorder.py": "item",
}
UNTOUCHED = {"app/jobs/reorder.py", "app/auth.py"}
FILLERS = 7


def filler(noun, i, feature):
    name = f"summarize_{noun}_{i}"
    if not feature:
        return textwrap.dedent(f"""
            def {name}(records, limit=None):
                out = []
                for r in records[:limit]:
                    if r.get("active"):
                        out.append(r.get("{noun}_id"))
                return out
            """)
    return textwrap.dedent(f"""
        def {name}(records: list, limit: int | None = None) -> list:
            \"\"\"Return ids of active {noun} records, up to `limit`.\"\"\"
            out = []
            for record in records[:limit]:
                if record.get("active"):
                    out.append(record.get("{noun}_id"))
            log.debug("{name}: %d of %d active", len(out), len(records))
            return out
        """)


CORE_BASE = {
    "app/__init__.py": "",
    "app/auth.py": '''
        import functools


        def require_role(role):
            def wrap(fn):
                @functools.wraps(fn)
                def inner(req, *a, **kw):
                    if role not in req.get("roles", ()):
                        raise PermissionError(role)
                    return fn(req, *a, **kw)
                return inner
            return wrap
        ''',
    "app/models/product.py": '''
        from dataclasses import dataclass


        @dataclass
        class Product:
            sku: str
            name: str
            price: float
        ''',
    "app/repos/stock.py": '''
        _STOCK = {}


        def get_stock(sku):
            return _STOCK.get(sku, 0)


        def set_stock(sku, qty):
            _STOCK[sku] = qty
        ''',
    "app/services/inventory.py": '''
        from app.repos import stock


        def available(sku):
            return stock.get_stock(sku) > 0


        def restock(sku, qty):
            stock.set_stock(sku, stock.get_stock(sku) + qty)
        ''',
    "app/api/products.py": '''
        from app.repos import stock


        def product_view(product):
            return {"sku": product.sku, "name": product.name, "in_stock": stock.get_stock(product.sku)}
        ''',
    "app/jobs/reorder.py": '''
        from app.repos import stock

        REORDER_AT = 5


        def items_to_reorder(items):
            return [item for item in items if stock.get_stock(item["sku"]) < REORDER_AT]
        ''',
    "app/services/pricing.py": '''
        def line_total(product, qty):
            return round(product.price * qty, 2)
        ''',
    "app/utils/formatting.py": '''
        def format_cents(cents):
            """Render an integer amount of cents as dollars, e.g. 1999 -> "19.99"."""
            return f"{cents / 100:.2f}"


        def title_case(s):
            return s.title()
        ''',
    "app/api/export.py": '''
        def export_row(p):
            return f"{p.sku},{p.name},{p.price:.2f}"


        def export_csv(products):
            return "\\n".join(["sku,name,price"] + [export_row(p) for p in products])
        ''',
    "app/api/admin.py": '''
        from app.auth import require_role
        from app.repos import warehouses


        @require_role("admin")
        def create_warehouse(req):
            return warehouses.create(req["name"])


        @require_role("admin")
        def rename_warehouse(req):
            warehouses.rename(req["warehouse_id"], req["name"])
            return {"ok": True}
        ''',
    "app/repos/warehouses.py": '''
        _W = {}


        def create(name):
            wid = len(_W) + 1
            _W[wid] = name
            return wid


        def rename(wid, name):
            _W[wid] = name


        def delete(wid):
            _W.pop(wid, None)
        ''',
    "app/jobs/batch_import.py": '''
        def import_batches(batches, store):
            for batch in batches:
                for row in batch:
                    store.add(row)
        ''',
    "app/services/tax.py": '''
        from decimal import ROUND_HALF_UP, Decimal


        def tax_cents(amount_cents, rate):
            """Tax on an amount in cents, rounded half-up to a whole cent."""
            exact = Decimal(amount_cents) * Decimal(str(rate))
            return int(exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        ''',
    "tests/test_tax.py": '''
        from app.services.tax import tax_cents


        def test_eight_percent():
            assert tax_cents(1000, 0.08) == 80
        ''',
    "tests/test_formatting.py": '''
        from app.utils.formatting import format_cents


        def test_format_cents():
            assert format_cents(1999) == "19.99"
        ''',
}

CORE_FEATURE = {
    "app/models/product.py": '''
        from dataclasses import dataclass


        @dataclass
        class Product:
            sku: str
            name: str
            price_cents: int
        ''',
    "app/repos/stock.py": '''
        _STOCK = {}


        def fetch_stock(sku, warehouse):
            return _STOCK.get((warehouse, sku), 0)


        def set_stock(sku, qty, warehouse):
            _STOCK[(warehouse, sku)] = qty
        ''',
    "app/services/inventory.py": '''
        from app.repos import stock

        DEFAULT_WAREHOUSE = "main"


        def available(sku, warehouse=DEFAULT_WAREHOUSE):
            return stock.fetch_stock(sku, warehouse) > 0


        def restock(sku, qty, warehouse=DEFAULT_WAREHOUSE):
            stock.set_stock(sku, stock.fetch_stock(sku, warehouse) + qty, warehouse)
        ''',
    "app/api/products.py": '''
        from app.repos import stock
        from app.services.inventory import DEFAULT_WAREHOUSE


        def product_view(product, warehouse=DEFAULT_WAREHOUSE):
            return {"sku": product.sku, "name": product.name,
                    "in_stock": stock.fetch_stock(product.sku, warehouse)}
        ''',
    "app/services/pricing.py": '''
        def line_total(product, qty):
            """Line total in cents."""
            return product.price_cents * qty
        ''',
    "app/api/export.py": '''
        def export_row(p):
            return f"{p.sku},{p.name},{p.price_cents:.2f}"


        def export_csv(products):
            rows = [export_row(p) for p in products]
            log.info("exporting %d products", len(rows))
            return "\\n".join(["sku,name,price"] + rows)
        ''',
    "app/api/admin.py": '''
        from app.auth import require_role
        from app.repos import warehouses


        @require_role("admin")
        def create_warehouse(req):
            log.info("create warehouse %s", req["name"])
            return warehouses.create(req["name"])


        @require_role("admin")
        def rename_warehouse(req):
            log.info("rename warehouse %s", req["warehouse_id"])
            warehouses.rename(req["warehouse_id"], req["name"])
            return {"ok": True}


        def delete_warehouse(req):
            log.info("delete warehouse %s", req["warehouse_id"])
            warehouses.delete(req["warehouse_id"])
            return {"ok": True}
        ''',
    "app/jobs/batch_import.py": '''
        def import_batches(batches, store):
            total = len(batches)
            for i in range(1, total):
                log.info("importing batch %d/%d", i + 1, total)
                for row in batches[i]:
                    store.add(row)
        ''',
    "app/services/tax.py": '''
        def tax_cents(amount_cents: int, rate: float) -> int:
            """Tax on an amount in cents, rounded to a whole cent."""
            return round(amount_cents * rate)
        ''',
    "app/utils/money.py": '''
        def cents_to_str(amount_cents: int) -> str:
            """Format cents as a dollar string, e.g. 250 -> "2.50"."""
            dollars, cents = divmod(amount_cents, 100)
            return f"{dollars}.{cents:02d}"
        ''',
    "README.md": '''
        # Inventory service

        Stock is tracked per warehouse (`repos.stock.fetch_stock(sku, warehouse)`); prices are
        stored as integer cents (`Product.price_cents`). Every module logs through `logging`.
        ''',
}


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def build(feature):
    files = dict(CORE_BASE)
    if feature:
        files.update(CORE_FEATURE)
    else:
        files["README.md"] = "# Inventory service\n"
    for path in set(NOUNS) | set(files):
        if not path.endswith(".py") or path.startswith("tests/") or path.endswith("__init__.py"):
            continue
        touched = feature and path not in UNTOUCHED
        body = textwrap.dedent(files.get(path, "")).strip("\n")
        header = "import logging\n\nlog = logging.getLogger(__name__)\n" if touched else ""
        fill = "".join(filler(NOUNS[path], i, touched) for i in range(FILLERS)) if path in NOUNS else ""
        files[path] = "\n\n".join(p for p in (header.strip("\n"), body, fill.strip("\n")) if p) + "\n"
    for path, text in files.items():
        write(path, text if path.endswith(".py") and not path.startswith("tests/")
              else textwrap.dedent(text).lstrip("\n"))
    for pkg in {os.path.dirname(p) for p in files if p.startswith("app/")}:
        if not os.path.exists(os.path.join(pkg, "__init__.py")):
            write(os.path.join(pkg, "__init__.py"), "")


if __name__ == "__main__":
    build(sys.argv[1] == "feature")
