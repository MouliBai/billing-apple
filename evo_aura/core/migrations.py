"""Database migration/index helpers for EvoAura."""

PERFORMANCE_INDEXES = {
    "products": [
        "CREATE INDEX IF NOT EXISTS idx_products_item_code ON products(item_code)",
        "CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)",
        "CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)",
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
        "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)",
    ],
    "suppliers": [
        "CREATE INDEX IF NOT EXISTS idx_suppliers_code ON suppliers(code)",
        "CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)",
    ],
    "supplier_ledger": [
        "CREATE INDEX IF NOT EXISTS idx_supplier_ledger_code ON supplier_ledger(supplier_code)",
    ],
    "purchase_orders": [
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(supplier_code)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_date ON purchase_orders(purchase_date)",
    ],
    "customers": [
        "CREATE INDEX IF NOT EXISTS idx_customers_code ON customers(code)",
        "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone)",
        "CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name)",
    ],
}


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def ensure_performance_indexes(conn):
    """Create search/report indexes for tables that already exist."""
    for table_name, statements in PERFORMANCE_INDEXES.items():
        if not _table_exists(conn, table_name):
            continue
        for statement in statements:
            conn.execute(statement)


def run_migrations(db):
    """Compatibility hook for the current DB wrapper."""
    if hasattr(db, "_migrate"):
        result = db._migrate()
        ensure_performance_indexes(db.con)
        db.con.commit()
        return result
    if hasattr(db, "execute"):
        ensure_performance_indexes(db)
        db.commit()
    return None
