"""Product SQL access helpers.

Heavy legacy product functions are imported lazily so non-product pages can
import this repository without loading the Product UI module at startup.
"""

import sqlite3


PRODUCT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_products_item_code ON products(item_code);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
"""


def ensure_product_indexes(db_name):
    with sqlite3.connect(db_name) as conn:
        conn.executescript(PRODUCT_INDEX_SQL)


def init_product_table(db_name, current_user="system"):
    from pages.inventory.product_page import init_product_table as _legacy_init

    _legacy_init(db_name, current_user)
    ensure_product_indexes(db_name)


def fetch_product_list(db_name, search="", limit=100, offset=0):
    """Fast list query: selected columns only, no image/blob fields."""
    term = f"%{search.strip()}%"
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(
            """
            SELECT item_code,name,category,sub_category,brand,size,color,
                   current_stock,mrp,selling_price,status
              FROM products
             WHERE COALESCE(is_deleted,0)=0
               AND (?='' OR name LIKE ? OR item_code LIKE ? OR barcode LIKE ?)
             ORDER BY name
             LIMIT ? OFFSET ?
            """,
            (search.strip(), term, term, term, int(limit), int(offset)),
        )]
