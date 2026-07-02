"""Supplier SQL access helpers."""

import sqlite3


SUPPLIER_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_suppliers_code ON suppliers(code);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
CREATE INDEX IF NOT EXISTS idx_supplier_ledger_code ON supplier_ledger(supplier_code);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(supplier_code);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_date ON purchase_orders(purchase_date);
"""


def ensure_supplier_indexes(db_name):
    with sqlite3.connect(db_name) as conn:
        conn.executescript(SUPPLIER_INDEX_SQL)


def init_supplier_tables(db_name):
    from pages.inventory.supplier_page import init_supplier_tables as _legacy_init

    _legacy_init(db_name)
    ensure_supplier_indexes(db_name)
