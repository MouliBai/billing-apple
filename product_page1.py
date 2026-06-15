"""
product_page.py  —  Evo Aura  •  Advanced Product Manager
==========================================================
7-tab form: Basic · Pricing · Inventory · Supplier · Compliance · Sales History · Audit
Supporting tables: batches, stock_adjustments, price_history, suppliers, product_suppliers
List page: filter bar, expiry badges, MRP/margin columns, inline stock-adjust button
Soft-delete, audit trail, image upload, live margin %, days-of-stock-left
"""

import sys
import os
import glob
import sqlite3
from datetime import datetime, date, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QMessageBox,
    QGridLayout, QComboBox, QAbstractItemView,
    QCheckBox, QTabWidget, QScrollArea, QDateEdit, QDoubleSpinBox,
    QSpinBox, QTextEdit, QStackedWidget, QApplication,
    QDialog, QFileDialog, QSizePolicy, QListView
)
from PyQt5.QtGui import QFont, QColor, QBrush, QPixmap
from PyQt5.QtCore import Qt, QDate, QTimer


# ─────────────────────────────────────────────────────────
#  DESIGN TOKENS  (mirror dashboard.py exactly)
# ─────────────────────────────────────────────────────────
PRIMARY  = "#1a7fe8"   # C_PRIMARY
DANGER   = "#ef4444"   # C_DANGER
SUCCESS  = "#10b981"   # C_ACCENT (green)
WARNING  = "#f59e0b"   # C_WARN
BG_LIGHT = "#f1f5f9"   # C_BG
WHITE    = "#ffffff"   # C_CARD
BORDER   = "#e2e8f0"   # C_BORDER
TEXT     = "#1e293b"   # C_TEXT
MUTED    = "#64748b"   # C_TEXT_MUTED
FONT     = "Segoe UI"  # FONT_BODY

FIELD_STYLE = """
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit {
        border: 1px solid #cbd5e1; border-radius: 7px;
        padding: 5px 10px; font-size: 13px;
        background: white; color: #1e293b; min-height: 32px;
        selection-background-color: #1a7fe8; selection-color: white;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
    QDoubleSpinBox:focus, QDateEdit:focus, QTextEdit:focus {
        border: 1.5px solid #1a7fe8; background: #f8fbff;
    }
    QLineEdit:read-only { background: #f8fafc; color: #94a3b8; }

    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox::down-arrow {
        image: none; border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid #64748b; margin-right: 6px;
    }

    /* ── Dropdown popup ─────────────────────────────── */
    QComboBox QAbstractItemView {
        background-color: white;
        color: #1e293b;
        selection-background-color: #1a7fe8;
        selection-color: white;
        border: 1.5px solid #1a7fe8;
        border-radius: 8px;
        padding: 4px;
        outline: none;
        alternate-background-color: white;
        show-decoration-selected: 1;
    }
    QComboBox QAbstractItemView::item {
        color: #1e293b;
        background-color: white;
        min-height: 30px;
        padding: 4px 12px;
        border-radius: 5px;
    }
    QComboBox QAbstractItemView::item:alternate {
        background-color: white;
    }
    QComboBox QAbstractItemView::item:hover {
        background-color: #eef5ff;
        color: #1a7fe8;
    }
    QComboBox QAbstractItemView::item:selected {
        background-color: #1a7fe8;
        color: white;
    }

    QCheckBox { font-size: 13px; color: #334155; }
    QCheckBox::indicator {
        width: 17px; height: 17px; border-radius: 4px;
        border: 1.5px solid #94a3b8; background: white;
    }
    QCheckBox::indicator:checked { background: #1a7fe8; border-color: #1a7fe8; }

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        width: 20px; border: none; background: #f1f5f9;
    }
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-bottom: 5px solid #64748b;
    }
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-top: 5px solid #64748b;
    }
    QCalendarWidget { background: white; color: #222; }
"""

LABEL_STYLE = "font-size: 12px; color: #475569; font-weight: 600;"
HINT_STYLE  = "font-size: 11px; color: #94a3b8; margin-top: 1px;"
SEC_STYLE   = """
    QFrame#section {
        background: white; border: 1px solid #e8eef5; border-radius: 12px;
    }
"""
TAB_STYLE = """
    QTabWidget::pane { border: none; background: #f1f5f9; }
    QTabBar::tab {
        background: #e2e8f0; color: #64748b;
        padding: 8px 14px; border-radius: 7px;
        margin-right: 4px; font-size: 12px; font-weight: 600;
    }
    QTabBar::tab:selected { background: #1a7fe8; color: white; }
    QTabBar::tab:hover:!selected { background: #cbd5e1; color: #1e293b; }
"""


def _btn(bg, fg="#ffffff", hover=None):
    h = hover or bg
    return f"""
        QPushButton {{
            background:{bg}; color:{fg}; border:none; border-radius:7px;
            font-size:13px; font-weight:700; padding:0 16px;
        }}
        QPushButton:hover {{ background:{h}; }}
    """


def fix_combo(combo):
    """
    Bulletproof fix for black QComboBox dropdown on Windows.
    Qt ignores stylesheets for native popup views on Windows —
    we must set the palette AND force a non-native view.
    """
    from PyQt5.QtGui  import QPalette
    from PyQt5.QtWidgets import QListView

    # Force a non-native view (this alone fixes most Windows dark popup issues)
    view = QListView()
    combo.setView(view)

    # Set palette on both the combo and its new view
    for widget in (combo, view):
        pal = widget.palette()
        pal.setColor(QPalette.Base,            QColor(WHITE))
        pal.setColor(QPalette.AlternateBase,   QColor(WHITE))
        pal.setColor(QPalette.Text,            QColor(TEXT))
        pal.setColor(QPalette.HighlightedText, QColor(WHITE))
        pal.setColor(QPalette.Highlight,       QColor(PRIMARY))
        pal.setColor(QPalette.Window,          QColor(WHITE))
        pal.setColor(QPalette.WindowText,      QColor(TEXT))
        widget.setPalette(pal)

    # Also apply stylesheet directly to the new view
    view.setStyleSheet(
        "QListView {"
        f"  background-color: {WHITE};"
        f"  color: {TEXT};"
        "  border: 1.5px solid #1a7fe8;"
        "  border-radius: 8px;"
        "  padding: 4px;"
        "  outline: none;"
        "}"
        "QListView::item {"
        f"  color: {TEXT};"
        f"  background-color: {WHITE};"
        "  min-height: 30px;"
        "  padding: 4px 12px;"
        "  border-radius: 5px;"
        "}"
        "QListView::item:hover {"
        "  background-color: #eef5ff;"
        "  color: #1a7fe8;"
        "}"
        "QListView::item:selected {"
        "  background-color: #1a7fe8;"
        "  color: white;"
        "}"
    )
    view.setAlternatingRowColors(False)


# ─────────────────────────────────────────────────────────
#  DATABASE — ALL TABLES + HELPERS
# ─────────────────────────────────────────────────────────

# Guard: track which DB files have already been fully migrated this session.
# This prevents the 75+ ALTER TABLE loop from running on every navigation click.
_initialized_dbs: set = set()


def init_product_table(db_name, current_user="system"):
    global _initialized_dbs
    if db_name in _initialized_dbs:
        return                          # already done this session — skip entirely
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code             TEXT UNIQUE NOT NULL,
            sku                   TEXT DEFAULT '',
            name                  TEXT NOT NULL,
            alias_names           TEXT DEFAULT '',
            description           TEXT DEFAULT '',
            product_type          TEXT DEFAULT 'Goods',
            tax_category          TEXT DEFAULT 'Standard',
            category              TEXT DEFAULT '',
            product_group         TEXT DEFAULT '',
            sub_category          TEXT DEFAULT '',
            brand                 TEXT DEFAULT '',
            manufacturer          TEXT DEFAULT '',
            country_of_origin     TEXT DEFAULT 'India',
            hsn_code              TEXT DEFAULT '',
            barcode               TEXT DEFAULT '',
            tags                  TEXT DEFAULT '',
            unit                  TEXT DEFAULT '',
            pack_size             INTEGER DEFAULT 1,
            meter                 TEXT DEFAULT '',
            shelf_life_days       INTEGER DEFAULT 0,
            storage_condition     TEXT DEFAULT 'Room Temp',
            image                 BLOB,
            mrp                   REAL DEFAULT 0,
            purchase_price        REAL DEFAULT 0,
            selling_price         REAL DEFAULT 0,
            retail_price          REAL DEFAULT 0,
            wholesale_price       REAL DEFAULT 0,
            dealer_price          REAL DEFAULT 0,
            min_selling_price     REAL DEFAULT 0,
            special_price         REAL DEFAULT 0,
            special_price_from    TEXT DEFAULT '',
            special_price_to      TEXT DEFAULT '',
            discount_pct          REAL DEFAULT 0,
            tax_inclusive         INTEGER DEFAULT 0,
            gst_rate              TEXT DEFAULT '0%',
            igst_rate             TEXT DEFAULT '0%',
            tax_type              TEXT DEFAULT 'CGST+SGST',
            cess_pct              REAL DEFAULT 0,
            tcs_applicable        INTEGER DEFAULT 0,
            gst_exemption_reason  TEXT DEFAULT '',
            opening_stock         INTEGER DEFAULT 0,
            stock                 INTEGER DEFAULT 0,
            reserved_stock        INTEGER DEFAULT 0,
            damaged_stock         INTEGER DEFAULT 0,
            in_transit_stock      INTEGER DEFAULT 0,
            reorder_level         INTEGER DEFAULT 0,
            safety_stock          INTEGER DEFAULT 0,
            reorder_qty           INTEGER DEFAULT 0,
            min_order_qty         INTEGER DEFAULT 1,
            max_stock             INTEGER DEFAULT 0,
            auto_reorder          INTEGER DEFAULT 0,
            allow_neg_stock       INTEGER DEFAULT 0,
            is_returnable         INTEGER DEFAULT 1,
            warehouse             TEXT DEFAULT '',
            rack_location         TEXT DEFAULT '',
            bin_location          TEXT DEFAULT '',
            track_batch           INTEGER DEFAULT 0,
            track_expiry          INTEGER DEFAULT 0,
            track_serial          INTEGER DEFAULT 0,
            mfg_date              TEXT DEFAULT '',
            expiry_date           TEXT DEFAULT '',
            expiry_alert_days     INTEGER DEFAULT 30,
            supplier_name         TEXT DEFAULT '',
            supplier_code         TEXT DEFAULT '',
            supplier_phone        TEXT DEFAULT '',
            supplier_email        TEXT DEFAULT '',
            supplier_gstin        TEXT DEFAULT '',
            lead_time_days        INTEGER DEFAULT 0,
            last_purchase_price   REAL DEFAULT 0,
            weight_kg             REAL DEFAULT 0,
            length_cm             REAL DEFAULT 0,
            width_cm              REAL DEFAULT 0,
            height_cm             REAL DEFAULT 0,
            has_variants          INTEGER DEFAULT 0,
            variant_type          TEXT DEFAULT '',
            fssai_number          TEXT DEFAULT '',
            drug_license_no       TEXT DEFAULT '',
            is_scheduled_drug     INTEGER DEFAULT 0,
            schedule_type         TEXT DEFAULT '',
            e_invoice_applicable  INTEGER DEFAULT 0,
            e_way_bill_applicable INTEGER DEFAULT 0,
            print_mrp_on_invoice  INTEGER DEFAULT 1,
            print_hsn_on_invoice  INTEGER DEFAULT 1,
            label_format          TEXT DEFAULT '40x25',
            total_qty_sold        INTEGER DEFAULT 0,
            total_revenue         REAL DEFAULT 0,
            last_sold_date        TEXT DEFAULT '',
            return_count          INTEGER DEFAULT 0,
            sale_count            INTEGER DEFAULT 0,
            internal_notes        TEXT DEFAULT '',
            status                TEXT DEFAULT 'Active',
            is_deleted            INTEGER DEFAULT 0,
            deleted_at            TEXT DEFAULT '',
            deleted_by            TEXT DEFAULT '',
            created_at            TEXT DEFAULT '',
            created_by            TEXT DEFAULT '',
            updated_at            TEXT DEFAULT '',
            updated_by            TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code   TEXT NOT NULL,
            batch_number   TEXT NOT NULL,
            qty            INTEGER DEFAULT 0,
            mfg_date       TEXT DEFAULT '',
            expiry_date    TEXT DEFAULT '',
            purchase_price REAL DEFAULT 0,
            supplier_name  TEXT DEFAULT '',
            received_date  TEXT DEFAULT '',
            created_by     TEXT DEFAULT '',
            UNIQUE(product_code, batch_number)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            adj_type     TEXT NOT NULL,
            qty          INTEGER NOT NULL,
            reason       TEXT DEFAULT '',
            batch_number TEXT DEFAULT '',
            adj_date     TEXT DEFAULT '',
            created_by   TEXT DEFAULT '',
            note         TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code   TEXT NOT NULL,
            purchase_price REAL DEFAULT 0,
            selling_price  REAL DEFAULT 0,
            mrp            REAL DEFAULT 0,
            changed_at     TEXT DEFAULT '',
            changed_by     TEXT DEFAULT '',
            note           TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            gstin           TEXT DEFAULT '',
            phone           TEXT DEFAULT '',
            email           TEXT DEFAULT '',
            address         TEXT DEFAULT '',
            city            TEXT DEFAULT '',
            state           TEXT DEFAULT '',
            pincode         TEXT DEFAULT '',
            payment_terms   TEXT DEFAULT 'Net 30',
            credit_limit    REAL DEFAULT 0,
            current_balance REAL DEFAULT 0,
            bank_account    TEXT DEFAULT '',
            ifsc            TEXT DEFAULT '',
            status          TEXT DEFAULT 'Active',
            created_at      TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS product_suppliers (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code          TEXT NOT NULL,
            supplier_code         TEXT NOT NULL,
            supplier_product_code TEXT DEFAULT '',
            unit_price            REAL DEFAULT 0,
            pack_size             INTEGER DEFAULT 1,
            is_primary            INTEGER DEFAULT 0,
            moq                   INTEGER DEFAULT 1,
            discount_pct          REAL DEFAULT 0,
            lead_time_days        INTEGER DEFAULT 0,
            last_ordered_date     TEXT DEFAULT '',
            last_received_price   REAL DEFAULT 0,
            UNIQUE(product_code, supplier_code)
        )
    """)

    # safe migration for existing DBs
    c.execute("PRAGMA table_info(products)")
    existing = {r[1] for r in c.fetchall()}
    new_cols = [
        ("sku","TEXT DEFAULT ''"), ("alias_names","TEXT DEFAULT ''"),
        ("product_type","TEXT DEFAULT 'Goods'"), ("tax_category","TEXT DEFAULT 'Standard'"),
        ("product_group","TEXT DEFAULT ''"), ("country_of_origin","TEXT DEFAULT 'India'"),
        ("tags","TEXT DEFAULT ''"), ("shelf_life_days","INTEGER DEFAULT 0"),
        ("storage_condition","TEXT DEFAULT 'Room Temp'"), ("image","BLOB"),
        ("mrp","REAL DEFAULT 0"), ("retail_price","REAL DEFAULT 0"),
        ("dealer_price","REAL DEFAULT 0"), ("special_price","REAL DEFAULT 0"),
        ("special_price_from","TEXT DEFAULT ''"), ("special_price_to","TEXT DEFAULT ''"),
        ("igst_rate","TEXT DEFAULT '0%'"), ("tcs_applicable","INTEGER DEFAULT 0"),
        ("gst_exemption_reason","TEXT DEFAULT ''"), ("reserved_stock","INTEGER DEFAULT 0"),
        ("damaged_stock","INTEGER DEFAULT 0"), ("in_transit_stock","INTEGER DEFAULT 0"),
        ("safety_stock","INTEGER DEFAULT 0"), ("reorder_qty","INTEGER DEFAULT 0"),
        ("auto_reorder","INTEGER DEFAULT 0"), ("bin_location","TEXT DEFAULT ''"),
        ("track_serial","INTEGER DEFAULT 0"), ("supplier_phone","TEXT DEFAULT ''"),
        ("supplier_email","TEXT DEFAULT ''"), ("supplier_gstin","TEXT DEFAULT ''"),
        ("fssai_number","TEXT DEFAULT ''"), ("drug_license_no","TEXT DEFAULT ''"),
        ("is_scheduled_drug","INTEGER DEFAULT 0"), ("schedule_type","TEXT DEFAULT ''"),
        ("e_invoice_applicable","INTEGER DEFAULT 0"), ("e_way_bill_applicable","INTEGER DEFAULT 0"),
        ("print_mrp_on_invoice","INTEGER DEFAULT 1"), ("print_hsn_on_invoice","INTEGER DEFAULT 1"),
        ("label_format","TEXT DEFAULT '40x25'"), ("total_qty_sold","INTEGER DEFAULT 0"),
        ("total_revenue","REAL DEFAULT 0"), ("last_sold_date","TEXT DEFAULT ''"),
        ("return_count","INTEGER DEFAULT 0"), ("sale_count","INTEGER DEFAULT 0"),
        ("is_deleted","INTEGER DEFAULT 0"), ("deleted_at","TEXT DEFAULT ''"),
        ("deleted_by","TEXT DEFAULT ''"), ("created_at","TEXT DEFAULT ''"),
        ("created_by","TEXT DEFAULT ''"), ("updated_at","TEXT DEFAULT ''"),
        ("updated_by","TEXT DEFAULT ''"),
        # keep legacy columns
        ("description","TEXT DEFAULT ''"), ("sub_category","TEXT DEFAULT ''"),
        ("brand","TEXT DEFAULT ''"), ("manufacturer","TEXT DEFAULT ''"),
        ("hsn_code","TEXT DEFAULT ''"), ("barcode","TEXT DEFAULT ''"),
        ("pack_size","INTEGER DEFAULT 1"), ("purchase_price","REAL DEFAULT 0"),
        ("selling_price","REAL DEFAULT 0"), ("wholesale_price","REAL DEFAULT 0"),
        ("min_selling_price","REAL DEFAULT 0"), ("discount_pct","REAL DEFAULT 0"),
        ("tax_inclusive","INTEGER DEFAULT 0"), ("gst_rate","TEXT DEFAULT '0%'"),
        ("tax_type","TEXT DEFAULT 'CGST+SGST'"), ("cess_pct","REAL DEFAULT 0"),
        ("opening_stock","INTEGER DEFAULT 0"), ("reorder_level","INTEGER DEFAULT 0"),
        ("min_order_qty","INTEGER DEFAULT 1"), ("max_stock","INTEGER DEFAULT 0"),
        ("warehouse","TEXT DEFAULT ''"), ("rack_location","TEXT DEFAULT ''"),
        ("track_batch","INTEGER DEFAULT 0"), ("track_expiry","INTEGER DEFAULT 0"),
        ("mfg_date","TEXT DEFAULT ''"), ("expiry_date","TEXT DEFAULT ''"),
        ("expiry_alert_days","INTEGER DEFAULT 30"), ("is_returnable","INTEGER DEFAULT 1"),
        ("allow_neg_stock","INTEGER DEFAULT 0"), ("supplier_name","TEXT DEFAULT ''"),
        ("supplier_code","TEXT DEFAULT ''"), ("lead_time_days","INTEGER DEFAULT 0"),
        ("last_purchase_price","REAL DEFAULT 0"), ("weight_kg","REAL DEFAULT 0"),
        ("length_cm","REAL DEFAULT 0"), ("width_cm","REAL DEFAULT 0"),
        ("height_cm","REAL DEFAULT 0"), ("has_variants","INTEGER DEFAULT 0"),
        ("variant_type","TEXT DEFAULT ''"), ("internal_notes","TEXT DEFAULT ''"),
    ]
    for col, defn in new_cols:
        if col not in existing:
            try:
                c.execute(f"ALTER TABLE products ADD COLUMN {col} {defn}")
            except Exception:
                pass

    conn.commit()
    conn.close()
    _initialized_dbs.add(db_name)      # ← mark done; never runs again this session


# ── Query helpers ─────────────────────────────────────────

def get_all_products(db_name, filters=None):
    filters = filters or {}
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    sql = """
        SELECT item_code, name, category, unit, selling_price, mrp,
               stock, reorder_level, status, gst_rate,
               expiry_date, last_sold_date, purchase_price, brand
        FROM products WHERE is_deleted=0
    """
    params = []
    if filters.get("status") and filters["status"] != "All":
        sql += " AND status=?"; params.append(filters["status"])
    if filters.get("category") and filters["category"] not in ("All", ""):
        sql += " AND category=?"; params.append(filters["category"])
    if filters.get("stock_filter") == "Low Stock":
        sql += " AND stock <= reorder_level AND reorder_level > 0"
    elif filters.get("stock_filter") == "Out of Stock":
        sql += " AND stock = 0"
    if filters.get("search"):
        q = f"%{filters['search']}%"
        sql += " AND (item_code LIKE ? OR name LIKE ? OR alias_names LIKE ? OR barcode LIKE ?)"
        params += [q, q, q, q]
    sql += " ORDER BY name"
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows


def get_categories(db_name):
    try:
        with sqlite3.connect(db_name) as c:
            rows = c.execute(
                "SELECT DISTINCT category FROM products WHERE category!='' AND is_deleted=0 ORDER BY category"
            ).fetchall()
        return ["All"] + [r[0] for r in rows]
    except Exception:
        return ["All"]


def get_all_supplier_names(db_name):
    try:
        with sqlite3.connect(db_name) as c:
            rows = c.execute("SELECT name FROM suppliers ORDER BY name").fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def get_next_item_code(db_name):
    with sqlite3.connect(db_name) as c:
        count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    return f"P{str(count + 1).zfill(5)}"


def get_product_full(db_name, item_code):
    with sqlite3.connect(db_name) as conn:
        cur = conn.execute("SELECT * FROM products WHERE item_code=?", (item_code,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def get_batches(db_name, product_code):
    try:
        with sqlite3.connect(db_name) as c:
            return c.execute(
                "SELECT batch_number, qty, mfg_date, expiry_date, purchase_price, supplier_name, received_date "
                "FROM batches WHERE product_code=? ORDER BY expiry_date",
                (product_code,)
            ).fetchall()
    except Exception:
        return []


def get_price_history(db_name, product_code):
    try:
        with sqlite3.connect(db_name) as c:
            return c.execute(
                "SELECT purchase_price, selling_price, mrp, changed_at, changed_by, note "
                "FROM price_history WHERE product_code=? ORDER BY changed_at DESC LIMIT 10",
                (product_code,)
            ).fetchall()
    except Exception:
        return []


def get_stock_adjustments(db_name, product_code):
    try:
        with sqlite3.connect(db_name) as c:
            return c.execute(
                "SELECT adj_type, qty, reason, adj_date, created_by, note "
                "FROM stock_adjustments WHERE product_code=? ORDER BY adj_date DESC LIMIT 20",
                (product_code,)
            ).fetchall()
    except Exception:
        return []


def save_product(db_name, data: dict, current_user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["created_at"] = now; data["created_by"] = current_user
    data["updated_at"] = now; data["updated_by"] = current_user
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    try:
        cols = ", ".join(data.keys())
        ph   = ", ".join(["?"] * len(data))
        c.execute(f"INSERT INTO products ({cols}) VALUES ({ph})", list(data.values()))
        c.execute("""
            INSERT INTO price_history
            (product_code, purchase_price, selling_price, mrp, changed_at, changed_by, note)
            VALUES (?,?,?,?,?,?,'Initial')
        """, (data["item_code"], data.get("purchase_price", 0),
              data.get("selling_price", 0), data.get("mrp", 0), now, current_user))
        conn.commit(); return True
    except Exception as e:
        print("Save error:", e); return False
    finally:
        conn.close()


def update_product(db_name, item_code, data: dict, current_user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["updated_at"] = now; data["updated_by"] = current_user
    old = get_product_full(db_name, item_code)
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    set_cl = ", ".join([f"{k}=?" for k in data.keys()])
    c.execute(f"UPDATE products SET {set_cl} WHERE item_code=?",
              list(data.values()) + [item_code])
    if old and (old.get("purchase_price") != data.get("purchase_price") or
                old.get("selling_price")  != data.get("selling_price")):
        c.execute("""
            INSERT INTO price_history
            (product_code, purchase_price, selling_price, mrp, changed_at, changed_by)
            VALUES (?,?,?,?,?,?)
        """, (item_code, data.get("purchase_price", 0),
              data.get("selling_price", 0), data.get("mrp", 0), now, current_user))
    conn.commit(); conn.close()


def soft_delete_product(db_name, item_code, current_user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_name) as c:
        c.execute(
            "UPDATE products SET is_deleted=1, deleted_at=?, deleted_by=?, status='Inactive' WHERE item_code=?",
            (now, current_user, item_code)
        )


def save_stock_adjustment(db_name, product_code, adj_type, qty, reason,
                          batch="", note="", user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_name) as c:
        c.execute("""
            INSERT INTO stock_adjustments
            (product_code, adj_type, qty, reason, batch_number, adj_date, created_by, note)
            VALUES (?,?,?,?,?,?,?,?)
        """, (product_code, adj_type, qty, reason, batch, now, user, note))
        if adj_type == "IN":
            c.execute("UPDATE products SET stock=stock+? WHERE item_code=?", (qty, product_code))
        else:
            c.execute("UPDATE products SET stock=MAX(0,stock-?) WHERE item_code=?", (qty, product_code))


def save_batch(db_name, product_code, batch_no, qty, mfg, expiry, price, supplier, user="system"):
    now = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(db_name) as c:
        try:
            c.execute("""
                INSERT INTO batches
                (product_code, batch_number, qty, mfg_date, expiry_date,
                 purchase_price, supplier_name, received_date, created_by)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (product_code, batch_no, qty, mfg, expiry, price, supplier, now, user))
        except sqlite3.IntegrityError:
            c.execute("UPDATE batches SET qty=qty+? WHERE product_code=? AND batch_number=?",
                      (qty, product_code, batch_no))
    save_stock_adjustment(db_name, product_code, "IN", qty, f"Batch {batch_no} received", batch_no, user=user)


# ─────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────

def make_section(title, icon=""):
    frame = QFrame()
    frame.setObjectName("section")
    frame.setStyleSheet(SEC_STYLE)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(18, 14, 18, 16)
    outer.setSpacing(10)
    hdr = QHBoxLayout(); hdr.setSpacing(6)
    if icon:
        ico = QLabel(icon)
        ico.setStyleSheet("font-size:15px; color:#1a7fe8; background:transparent;")
        hdr.addWidget(ico)
    lbl = QLabel(title)
    lbl.setStyleSheet("font-size:13px; font-weight:700; color:#1e3a5f; background:transparent;")
    hdr.addWidget(lbl); hdr.addStretch()
    outer.addLayout(hdr)
    sep = QFrame(); sep.setFrameShape(QFrame.HLine)
    sep.setStyleSheet("background:#e8eef5; border:none; max-height:1px;")
    outer.addWidget(sep)
    grid = QGridLayout(); grid.setSpacing(8)
    grid.setColumnMinimumWidth(0, 140)
    grid.setColumnMinimumWidth(1, 170)
    grid.setColumnMinimumWidth(2, 140)
    grid.setColumnMinimumWidth(3, 170)
    outer.addLayout(grid)
    return frame, grid


def add_field(grid, row, col, label, widget, required=False, hint="", span=1):
    """
    Place a label + widget pair into a QGridLayout.
    Hint text is shown as a small grey label placed BELOW the widget
    inside a QVBoxLayout wrapper — this prevents the hint from ever
    sharing a grid row with the next field's label/widget.
    """
    lbl = QLabel(label)
    lbl.setStyleSheet(LABEL_STYLE)
    if required:
        lbl.setText(label + "  <span style='color:#ef4444'>*</span>")
        lbl.setTextFormat(Qt.RichText)
    grid.addWidget(lbl, row, col)

    col_span = 1 + (span - 1) * 2

    if hint:
        # Wrap widget + hint in a vertical container so the hint
        # sits directly below the widget without consuming a grid row.
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)
        vbox.addWidget(widget)
        h_lbl = QLabel(hint)
        h_lbl.setStyleSheet(HINT_STYLE)
        h_lbl.setWordWrap(True)
        vbox.addWidget(h_lbl)
        grid.addWidget(container, row, col + 1, 1, col_span)
    else:
        grid.addWidget(widget, row, col + 1, 1, col_span)


def ro_label(text="—"):
    l = QLabel(text)
    l.setStyleSheet(
        "background:#f8fafc; border:1px solid #e2e8f0; border-radius:7px; "
        "padding:5px 10px; font-size:13px; color:#475569; min-height:32px;"
    )
    return l


def price_spin():
    s = QDoubleSpinBox()
    s.setRange(0, 9999999); s.setDecimals(2); s.setPrefix("₹ ")
    return s


def mini_table(cols, height=130):
    t = QTableWidget()
    t.setColumnCount(len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.verticalHeader().setVisible(False)
    t.setFixedHeight(height)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setStyleSheet("""
        QTableWidget{background:white;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;}
        QHeaderView::section{background:#f8fafc;font-weight:600;padding:6px;
            border:none;border-bottom:1px solid #e2e8f0;color:#475569;}
        QTableWidget::item{padding:4px;color:#1e293b;}
        QTableWidget::item:selected{background:#eef5ff;color:#111;}
    """)
    return t


# ─────────────────────────────────────────────────────────
#  STOCK ADJUSTMENT DIALOG
# ─────────────────────────────────────────────────────────

class StockAdjDialog(QDialog):
    def __init__(self, db_name, product_code, product_name, current_stock, user="Admin", parent=None):
        super().__init__(parent)
        self.db_name = db_name; self.product_code = product_code; self.user = user
        self.setWindowTitle(f"Stock Adjustment — {product_name}")
        self.setFixedSize(440, 360)
        self.setStyleSheet(FIELD_STYLE + "QDialog{background:#f1f5f9;}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24); lay.setSpacing(12)

        lay.addWidget(QLabel(f"<b>Current Stock:</b>  {current_stock} units",
                             styleSheet="font-size:14px; color:#1e293b;"))

        self.adj_type = QComboBox()
        self.adj_type.addItems(["IN — Stock Received", "OUT — Damaged / Expired",
                                "OUT — Return to Supplier", "OUT — Lost / Theft",
                                "IN — Manual Correction", "OUT — Manual Correction"])
        lay.addWidget(QLabel("Adjustment Type:", styleSheet=LABEL_STYLE))
        lay.addWidget(self.adj_type)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Quantity:", styleSheet=LABEL_STYLE))
        self.qty_spin = QSpinBox(); self.qty_spin.setRange(1, 999999)
        row2.addWidget(self.qty_spin)
        lay.addLayout(row2)

        lay.addWidget(QLabel("Reason:", styleSheet=LABEL_STYLE))
        self.reason = QLineEdit(); self.reason.setPlaceholderText("e.g. Supplier delivery, breakage…")
        lay.addWidget(self.reason)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Batch No (optional):", styleSheet=LABEL_STYLE))
        self.batch = QLineEdit(); self.batch.setPlaceholderText("Optional")
        row4.addWidget(self.batch)
        lay.addLayout(row4)

        self.note = QTextEdit(); self.note.setFixedHeight(52)
        self.note.setPlaceholderText("Additional notes…")
        lay.addWidget(self.note)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        ok = QPushButton("✅  Apply Adjustment")
        ok.setFixedHeight(36); ok.setStyleSheet(_btn(PRIMARY))
        ok.clicked.connect(self._apply)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(36); cancel.setStyleSheet(_btn("#e2e8f0", "#475569"))
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        lay.addLayout(btn_row)

    def _apply(self):
        adj_raw  = self.adj_type.currentText()
        adj_type = "IN" if adj_raw.startswith("IN") else "OUT"
        qty      = self.qty_spin.value()
        reason   = self.reason.text().strip() or adj_raw
        save_stock_adjustment(self.db_name, self.product_code, adj_type, qty,
                              reason, self.batch.text().strip(),
                              self.note.toPlainText().strip(), self.user)
        QMessageBox.information(self, "Done",
            f"Stock {'increased' if adj_type=='IN' else 'reduced'} by {qty} units.")
        self.accept()


# ─────────────────────────────────────────────────────────
#  BATCH ADD DIALOG
# ─────────────────────────────────────────────────────────

class BatchAddDialog(QDialog):
    def __init__(self, db_name, product_code, user="Admin", parent=None):
        super().__init__(parent)
        self.db_name = db_name; self.product_code = product_code; self.user = user
        self.setWindowTitle("Add / Receive Batch")
        self.setFixedSize(420, 330)
        self.setStyleSheet(FIELD_STYLE + "QDialog{background:#f1f5f9;}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(10)

        grid = QGridLayout(); grid.setSpacing(8)
        self.f_batch = QLineEdit(); self.f_batch.setPlaceholderText("e.g. B2024-001")
        self.f_qty   = QSpinBox(); self.f_qty.setRange(1, 999999)
        self.f_mfg   = QDateEdit(); self.f_mfg.setCalendarPopup(True)
        self.f_mfg.setDate(QDate.currentDate()); self.f_mfg.setDisplayFormat("dd-MM-yyyy")
        self.f_exp   = QDateEdit(); self.f_exp.setCalendarPopup(True)
        self.f_exp.setDate(QDate.currentDate().addYears(1)); self.f_exp.setDisplayFormat("dd-MM-yyyy")
        self.f_price = QDoubleSpinBox(); self.f_price.setRange(0, 999999); self.f_price.setPrefix("₹ ")
        self.f_sup   = QLineEdit(); self.f_sup.setPlaceholderText("Supplier name")

        add_field(grid, 0, 0, "Batch No",       self.f_batch, required=True)
        add_field(grid, 0, 2, "Qty Received",   self.f_qty)
        add_field(grid, 1, 0, "Mfg Date",       self.f_mfg)
        add_field(grid, 1, 2, "Expiry Date",    self.f_exp)
        add_field(grid, 2, 0, "Purchase Price", self.f_price)
        add_field(grid, 2, 2, "Supplier",       self.f_sup)
        lay.addLayout(grid)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        ok = QPushButton("💾  Save Batch")
        ok.setFixedHeight(36); ok.setStyleSheet(_btn(SUCCESS))
        ok.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(36); cancel.setStyleSheet(_btn("#e2e8f0", "#475569"))
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        lay.addLayout(btn_row)

    def _save(self):
        bn = self.f_batch.text().strip()
        if not bn:
            QMessageBox.warning(self, "Error", "Batch number is required."); return
        save_batch(self.db_name, self.product_code, bn,
                   self.f_qty.value(),
                   self.f_mfg.date().toString("yyyy-MM-dd"),
                   self.f_exp.date().toString("yyyy-MM-dd"),
                   self.f_price.value(), self.f_sup.text().strip(), self.user)
        QMessageBox.information(self, "Done", f"Batch {bn} saved and stock updated.")
        self.accept()


# ─────────────────────────────────────────────────────────
#  PRODUCT FORM WIDGET  (7 tabs)
# ─────────────────────────────────────────────────────────

class ProductFormWidget(QWidget):
    def __init__(self, db_name, on_saved, on_cancel, current_user="Admin", parent=None):
        super().__init__(parent)
        self.db_name      = db_name
        self.on_saved     = on_saved
        self.on_cancel    = on_cancel
        self.current_user = current_user
        self.edit_code    = None
        self.prod         = {}
        self._image_blob  = b""

        self.setStyleSheet(f"background:{BG_LIGHT};" + FIELD_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # top bar
        top = QFrame(); top.setFixedHeight(58)
        top.setStyleSheet(f"background:{WHITE}; border-bottom:1px solid {BORDER};")
        tl = QHBoxLayout(top); tl.setContentsMargins(16, 0, 16, 0)

        self.btn_back = QPushButton("← Back")
        self.btn_back.setFixedSize(90, 34)
        self.btn_back.setStyleSheet(_btn("#eef5ff", PRIMARY)); self.btn_back.clicked.connect(self._cancel)

        self.title_lbl = QLabel("Add Product")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.title_lbl.setStyleSheet("color:#1e3a5f; background:transparent;")

        self.btn_save = QPushButton("💾  Save Product")
        self.btn_save.setFixedHeight(34); self.btn_save.setMinimumWidth(150)
        self.btn_save.setStyleSheet(_btn(PRIMARY)); self.btn_save.clicked.connect(self._save)

        tl.addWidget(self.btn_back); tl.addStretch()
        tl.addWidget(self.title_lbl); tl.addStretch()
        tl.addWidget(self.btn_save)
        root.addWidget(top)

        # tabs
        self.tabs = QTabWidget(); self.tabs.setStyleSheet(TAB_STYLE)
        self._build_tab_basic()
        self._build_tab_pricing()
        self._build_tab_inventory()
        self._build_tab_supplier()
        self._build_tab_compliance()
        self._build_tab_history()
        self._build_tab_audit()

        # Fix black dropdown on Windows for every QComboBox in the form
        for combo in self.findChildren(QComboBox):
            fix_combo(combo)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame); scroll.setStyleSheet("background:transparent;")
        wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(wrap); wl.setContentsMargins(22, 14, 22, 14); wl.setSpacing(0)
        wl.addWidget(self.tabs)
        scroll.setWidget(wrap)
        root.addWidget(scroll, 1)

    # ── TAB 1: BASIC INFO ────────────────────────────────

    def _build_tab_basic(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)

        sec, g = make_section("Identity & Legal", "🔖")
        self.f_item_code  = QLineEdit(); self.f_item_code.setPlaceholderText("e.g. P00001")
        self.f_auto_code  = QCheckBox("Auto-generate code")
        self.f_auto_code.stateChanged.connect(self._toggle_code)
        self.f_sku        = QLineEdit(); self.f_sku.setPlaceholderText("Internal SKU")
        self.f_barcode    = QLineEdit(); self.f_barcode.setPlaceholderText("EAN-13 / QR")
        self.f_name       = QLineEdit(); self.f_name.setPlaceholderText("Full product name")
        self.f_alias      = QLineEdit(); self.f_alias.setPlaceholderText("Alt names, comma-separated")
        self.f_hsn        = QLineEdit(); self.f_hsn.setPlaceholderText("e.g. 2202")
        self.f_prod_type  = QComboBox()
        self.f_prod_type.addItems(["Goods","Service","Digital","Composite"])
        self.f_tax_cat    = QComboBox()
        self.f_tax_cat.addItems(["Standard","Nil Rated","Exempt","Zero Rated","Non-GST"])

        r = 0
        add_field(g, r, 0, "Item Code",    self.f_item_code, required=True)
        add_field(g, r, 2, "SKU",          self.f_sku)
        r += 1; g.addWidget(self.f_auto_code, r, 1)
        r += 1
        add_field(g, r, 0, "Product Name", self.f_name, required=True, span=2)
        r += 1
        add_field(g, r, 0, "Alias / Alt Names", self.f_alias, hint="Used in billing search", span=2)
        r += 1
        add_field(g, r, 0, "Barcode / EAN", self.f_barcode)
        add_field(g, r, 2, "HSN Code",     self.f_hsn, hint="Mandatory for GST")
        r += 1
        add_field(g, r, 0, "Product Type", self.f_prod_type)
        add_field(g, r, 2, "Tax Category", self.f_tax_cat)
        lay.addWidget(sec)

        # image
        sec_img, g_img = make_section("Product Image", "🖼️")
        img_row = QHBoxLayout()
        self.img_label = QLabel("No Image")
        self.img_label.setFixedSize(100, 100); self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet(
            "border:2px dashed #cbd5e1; border-radius:10px; color:#94a3b8; font-size:12px;")
        img_row.addWidget(self.img_label)
        img_btns = QVBoxLayout(); img_btns.setSpacing(6)
        btn_up = QPushButton("📁  Upload Image")
        btn_up.setFixedHeight(32); btn_up.setStyleSheet(_btn("#eef5ff", PRIMARY))
        btn_up.clicked.connect(self._upload_image)
        btn_rm = QPushButton("🗑  Remove")
        btn_rm.setFixedHeight(32); btn_rm.setStyleSheet(_btn("#fee2e2", DANGER))
        btn_rm.clicked.connect(self._clear_image)
        img_btns.addWidget(btn_up); img_btns.addWidget(btn_rm); img_btns.addStretch()
        img_row.addLayout(img_btns); img_row.addStretch()
        g_img.addLayout(img_row, 0, 0, 1, 4)
        lay.addWidget(sec_img)

        # classification
        sec2, g2 = make_section("Classification & Properties", "🗂️")
        self.f_product_group = QLineEdit(); self.f_product_group.setPlaceholderText("e.g. Food & Beverages")
        self.f_category = QComboBox(); self.f_category.setEditable(True)
        self.f_category.addItems(["","Groceries","Household","Beverages","Stationery",
            "Electronics","Pharma","Clothing","Hardware","Cosmetics","Food","FMCG"])
        self.f_sub_cat      = QLineEdit(); self.f_sub_cat.setPlaceholderText("e.g. Cold Drinks")
        self.f_brand        = QLineEdit(); self.f_brand.setPlaceholderText("e.g. Parle")
        self.f_manufacturer = QLineEdit(); self.f_manufacturer.setPlaceholderText("e.g. Parle Products Pvt Ltd")
        self.f_country      = QLineEdit(); self.f_country.setText("India")
        self.f_unit = QComboBox(); self.f_unit.setEditable(True)
        self.f_unit.addItems(["Pcs","Kg","g","L","ml","Box","Dozen","Bag","Strip","Pack","Nos","Pair","Set","Roll","Bottle"])
        self.f_pack_size    = QSpinBox(); self.f_pack_size.setRange(1,99999); self.f_pack_size.setValue(1)
        self.f_meter        = QLineEdit(); self.f_meter.setPlaceholderText("e.g. 500 ml bottle")
        self.f_shelf_life   = QSpinBox(); self.f_shelf_life.setRange(0,9999); self.f_shelf_life.setSuffix(" days")
        self.f_storage      = QComboBox()
        self.f_storage.addItems(["Room Temp","Refrigerated","Frozen","Cool & Dry","Dark & Dry"])
        self.f_tags         = QLineEdit(); self.f_tags.setPlaceholderText("organic, diabetic-safe, offer")

        r2 = 0
        add_field(g2, r2, 0, "Product Group", self.f_product_group)
        add_field(g2, r2, 2, "Category",      self.f_category)
        r2 += 1
        add_field(g2, r2, 0, "Sub-category",  self.f_sub_cat)
        add_field(g2, r2, 2, "Brand",         self.f_brand)
        r2 += 1
        add_field(g2, r2, 0, "Manufacturer",  self.f_manufacturer)
        add_field(g2, r2, 2, "Country of Origin", self.f_country)
        r2 += 1
        add_field(g2, r2, 0, "Unit",          self.f_unit)
        add_field(g2, r2, 2, "Pack Size",     self.f_pack_size)
        r2 += 1
        add_field(g2, r2, 0, "Display Unit",  self.f_meter, hint="Shows on invoice")
        add_field(g2, r2, 2, "Shelf Life",    self.f_shelf_life)
        r2 += 1
        add_field(g2, r2, 0, "Storage Condition", self.f_storage)
        add_field(g2, r2, 2, "Tags",          self.f_tags, hint="Comma separated")
        lay.addWidget(sec2)

        # description
        sec3, g3 = make_section("Description & Notes", "📝")
        self.f_desc   = QTextEdit(); self.f_desc.setFixedHeight(70)
        self.f_desc.setPlaceholderText("Short product description (printed on invoice/label)…")
        self.f_notes  = QTextEdit(); self.f_notes.setFixedHeight(60)
        self.f_notes.setPlaceholderText("Internal notes — staff only, not printed…")
        self.f_status = QComboBox()
        self.f_status.addItems(["Active","Draft","Inactive","Discontinued"])
        g3.addWidget(QLabel("Description", styleSheet=LABEL_STYLE), 0, 0)
        g3.addWidget(self.f_desc, 0, 1, 1, 3)
        g3.addWidget(QLabel("Internal Notes", styleSheet=LABEL_STYLE), 1, 0)
        g3.addWidget(self.f_notes, 1, 1, 1, 3)
        add_field(g3, 2, 0, "Status", self.f_status, required=True)
        lay.addWidget(sec3)
        lay.addStretch()
        self.tabs.addTab(page, "🏷️  Basic Info")

    # ── TAB 2: PRICING & TAX ─────────────────────────────

    def _build_tab_pricing(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)

        # ── Price Tiers ───────────────────────────────────
        sec, g = make_section("Price Tiers", "💰")
        self.f_mrp               = price_spin()
        self.f_purchase_price    = price_spin()
        self.f_selling_price     = price_spin()
        self.f_retail_price      = price_spin()
        self.f_wholesale_price   = price_spin()
        self.f_dealer_price      = price_spin()
        self.f_min_selling_price = price_spin()
        self.f_discount_pct      = QDoubleSpinBox()
        self.f_discount_pct.setRange(0,100); self.f_discount_pct.setDecimals(2)
        self.f_discount_pct.setSuffix(" %")
        self.lbl_margin = ro_label("—")
        self.lbl_markup = ro_label("—")

        # connect margin live update
        self.f_purchase_price.valueChanged.connect(self._update_margin)
        self.f_selling_price.valueChanged.connect(self._update_margin)

        r = 0
        add_field(g, r, 0, "MRP",               self.f_mrp, required=True,
                  hint="Legally printed on invoice & label")
        add_field(g, r, 2, "Purchase Price",     self.f_purchase_price, required=True)
        r += 1
        add_field(g, r, 0, "Selling Price",      self.f_selling_price, required=True)
        add_field(g, r, 2, "Retail Price",       self.f_retail_price, hint="Walk-in customer")
        r += 1
        add_field(g, r, 0, "Wholesale Price",    self.f_wholesale_price)
        add_field(g, r, 2, "Dealer Price",       self.f_dealer_price, hint="For distributors")
        r += 1
        add_field(g, r, 0, "Min Selling Price",  self.f_min_selling_price,
                  hint="Floor — cannot sell below")
        add_field(g, r, 2, "Discount %",         self.f_discount_pct)
        r += 1
        add_field(g, r, 0, "Margin %",  self.lbl_margin, hint="(Sell−Buy)÷Buy×100  — live")
        add_field(g, r, 2, "Markup %",  self.lbl_markup, hint="(Sell−Buy)÷Sell×100")
        lay.addWidget(sec)

        # ── Special / Offer Price ─────────────────────────
        sec2, g2 = make_section("Special / Offer Price", "🏷️")
        self.f_special_price = price_spin()
        self.f_sp_from = QDateEdit(); self.f_sp_from.setCalendarPopup(True)
        self.f_sp_from.setDate(QDate.currentDate())
        self.f_sp_from.setDisplayFormat("dd-MM-yyyy")
        self.f_sp_to = QDateEdit(); self.f_sp_to.setCalendarPopup(True)
        self.f_sp_to.setDate(QDate.currentDate().addDays(7))
        self.f_sp_to.setDisplayFormat("dd-MM-yyyy")
        self.f_sp_from.setStyleSheet("""
            background: white;
            color: black; """)
        r2 = 0
        add_field(g2, r2, 0, "Special Price", self.f_special_price, hint="0 = not active")
        add_field(g2, r2, 2, "Valid From",    self.f_sp_from)
        r2 += 1
        add_field(g2, r2, 0, "Valid To",      self.f_sp_to)
        lay.addWidget(sec2)

        # ── GST & Tax ─────────────────────────────────────
        sec3, g3 = make_section("GST & Tax", "🧾")

        self.f_gst_rate = QComboBox()
        self.f_gst_rate.addItems(["0%", "5%", "12%", "18%", "28%"])
        self.f_igst_rate = QComboBox()
        self.f_igst_rate.addItems(["0%", "5%", "12%", "18%", "28%"])
        self.f_tax_type = QComboBox()
        self.f_tax_type.addItems(["CGST + SGST (local)", "IGST (interstate)"])
        self.f_cess_pct = QDoubleSpinBox()
        self.f_cess_pct.setRange(0,100); self.f_cess_pct.setDecimals(2)
        self.f_cess_pct.setSuffix(" %")
        self.f_tcs   = QCheckBox("TCS Applicable (Tax Collected at Source)")
        self.f_gst_ex = QLineEdit()
        self.f_gst_ex.setPlaceholderText("e.g. Agriculture produce, Essential medicine")

        # ── "Price includes GST" checkbox ─────────────────
        self.f_tax_inclusive = QCheckBox("Price includes GST  "
                                         "(GST is already baked into the selling price)")
        self.f_tax_inclusive.setStyleSheet(
            "font-size:13px; color:#1e3a5f; font-weight:600;"
        )

        r3 = 0
        add_field(g3, r3, 0, "GST Rate (CGST+SGST)", self.f_gst_rate, required=True)
        add_field(g3, r3, 2, "IGST Rate",             self.f_igst_rate)
        r3 += 1
        add_field(g3, r3, 0, "Tax Type",  self.f_tax_type)
        add_field(g3, r3, 2, "Cess %",    self.f_cess_pct, hint="Tobacco, luxury items")
        r3 += 1
        g3.addWidget(self.f_tcs, r3, 0, 1, 4); r3 += 1
        add_field(g3, r3, 0, "GST Exemption Reason", self.f_gst_ex,
                  hint="Required on invoice when GST = 0%", span=2)
        r3 += 1
        # separator line
        sep_frame = QFrame(); sep_frame.setFrameShape(QFrame.HLine)
        sep_frame.setStyleSheet("background:#e2e8f0; border:none; max-height:1px;")
        g3.addWidget(sep_frame, r3, 0, 1, 4); r3 += 1
        g3.addWidget(self.f_tax_inclusive, r3, 0, 1, 4)

        lay.addWidget(sec3)

        # ── Live GST breakdown panel ──────────────────────
        self._gst_panel = QFrame()
        self._gst_panel.setStyleSheet(
            "QFrame { background:#f0f9ff; border:1.5px solid #bae6fd; "
            "border-radius:10px; }"
        )
        gp_lay = QVBoxLayout(self._gst_panel)
        gp_lay.setContentsMargins(16, 12, 16, 12)
        gp_lay.setSpacing(6)

        gp_title = QLabel("📊  Live GST Breakdown")
        gp_title.setStyleSheet(
            "font-size:12px; font-weight:700; color:#0369a1; background:transparent;"
        )
        gp_lay.addWidget(gp_title)

        def _gst_row(label):
            row = QHBoxLayout(); row.setSpacing(0)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size:12px; color:#475569; background:transparent;")
            val = QLabel("—")
            val.setStyleSheet(
                "font-size:12px; font-weight:700; color:#1e293b; background:transparent;"
            )
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl); row.addStretch(); row.addWidget(val)
            return row, val

        row_sp, self._gst_lbl_sp      = _gst_row("Selling Price entered")
        row_gp, self._gst_lbl_pct     = _gst_row("GST Rate applied")
        row_bp, self._gst_lbl_base    = _gst_row("Base Price (excl. GST)")
        row_ga, self._gst_lbl_amt     = _gst_row("GST Amount")
        row_cp, self._gst_lbl_cust    = _gst_row("Customer pays")
        row_msg, self._gst_lbl_msg    = _gst_row("")

        for row in [row_sp, row_gp, row_bp, row_ga, row_cp]:
            gp_lay.addLayout(row)

        # message row full-width
        self._gst_msg_lbl = QLabel("")
        self._gst_msg_lbl.setWordWrap(True)
        self._gst_msg_lbl.setStyleSheet(
            "font-size:11px; color:#0369a1; background:transparent; "
            "padding-top:4px;"
        )
        gp_lay.addWidget(self._gst_msg_lbl)
        lay.addWidget(self._gst_panel)

        lay.addStretch()
        self.tabs.addTab(page, "💰  Pricing & Tax")

        # ── Wire all live signals ─────────────────────────
        self.f_selling_price.valueChanged.connect(self._update_gst_panel)
        self.f_gst_rate.currentTextChanged.connect(self._update_gst_panel)
        self.f_tax_inclusive.stateChanged.connect(self._update_gst_panel)
        self._update_gst_panel()   # initial state

    # ── Live margin ───────────────────────────────────────

    def _update_margin(self):
        pp = self.f_purchase_price.value()
        sp = self.f_selling_price.value()
        if pp > 0:
            margin = (sp - pp) / pp * 100
            markup = (sp - pp) / sp * 100 if sp > 0 else 0
            c = SUCCESS if margin >= 0 else DANGER
            self.lbl_margin.setText(f"{margin:.1f}%")
            self.lbl_margin.setStyleSheet(
                f"background:#f8fafc; border:1px solid #e2e8f0; border-radius:7px;"
                f"padding:5px 10px; font-size:13px; font-weight:700; "
                f"color:{c}; min-height:32px;"
            )
            self.lbl_markup.setText(f"{markup:.1f}%")
        else:
            self.lbl_margin.setText("—")
            self.lbl_markup.setText("—")

    # ── Live GST breakdown ────────────────────────────────

    def _update_gst_panel(self):
        sp          = self.f_selling_price.value()
        gst_str     = self.f_gst_rate.currentText()   # e.g. "18%"
        inclusive   = self.f_tax_inclusive.isChecked()

        # parse GST %
        try:
            gst_pct = float(gst_str.replace("%","").strip())
        except Exception:
            gst_pct = 0.0

        # ── No GST selected (0%) ──────────────────────────
        if gst_pct == 0:
            self._gst_panel.setStyleSheet(
                "QFrame { background:#f8fafc; border:1.5px solid #e2e8f0; "
                "border-radius:10px; }"
            )
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}")
            self._gst_lbl_pct.setText("0%  — No GST")
            self._gst_lbl_base.setText(f"₹ {sp:.2f}")
            self._gst_lbl_amt.setText("₹ 0.00")
            self._gst_lbl_cust.setText(f"₹ {sp:.2f}")
            self._gst_msg_lbl.setText(
                "ℹ️  GST rate is 0% — no tax will be added to this product."
            )
            self._gst_msg_lbl.setStyleSheet(
                "font-size:11px; color:#64748b; background:transparent; padding-top:4px;"
            )
            return

        # ── GST selected, price IS inclusive ─────────────
        if inclusive:
            # Base = SP ÷ (1 + GST/100)
            base    = round(sp / (1 + gst_pct / 100), 2)
            gst_amt = round(sp - base, 2)

            self._gst_panel.setStyleSheet(
                "QFrame { background:#f0fdf4; border:1.5px solid #86efac; "
                "border-radius:10px; }"
            )
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}  (GST included)")
            self._gst_lbl_pct.setText(f"{gst_str}")
            self._gst_lbl_base.setText(f"₹ {base:.2f}")
            self._gst_lbl_amt.setText(f"₹ {gst_amt:.2f}")
            self._gst_lbl_cust.setText(f"₹ {sp:.2f}  ✅ (no extra charge)")
            self._gst_msg_lbl.setStyleSheet(
                "font-size:11px; color:#16a34a; background:transparent; padding-top:4px;"
            )
            self._gst_msg_lbl.setText(
                f"✅  GST is included in ₹ {sp:.2f}.  "
                f"On invoice: Base ₹ {base:.2f}  +  GST ({gst_str}) ₹ {gst_amt:.2f}  "
                f"=  Total ₹ {sp:.2f}.  Customer is NOT charged extra."
            )

        # ── GST selected, price is EXCLUSIVE (added on top) ──
        else:
            gst_amt  = round(sp * gst_pct / 100, 2)
            cust_pays = round(sp + gst_amt, 2)

            self._gst_panel.setStyleSheet(
                "QFrame { background:#fff7ed; border:1.5px solid #fdba74; "
                "border-radius:10px; }"
            )
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}  (base price)")
            self._gst_lbl_pct.setText(f"{gst_str}")
            self._gst_lbl_base.setText(f"₹ {sp:.2f}")
            self._gst_lbl_amt.setText(f"₹ {gst_amt:.2f}")
            self._gst_lbl_cust.setText(f"₹ {cust_pays:.2f}  ⚠️ (GST added on top)")
            self._gst_msg_lbl.setStyleSheet(
                "font-size:11px; color:#c2410c; background:transparent; padding-top:4px;"
            )
            self._gst_msg_lbl.setText(
                f"⚠️  GST will be added on top at billing.  "
                f"Selling price ₹ {sp:.2f}  +  GST ({gst_str}) ₹ {gst_amt:.2f}  "
                f"=  Customer pays ₹ {cust_pays:.2f}."
            )

    # ── TAB 3: INVENTORY ─────────────────────────────────

    def _build_tab_inventory(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)

        sec, g = make_section("Stock Levels", "📦")
        self.f_opening_stock = QSpinBox(); self.f_opening_stock.setRange(0,9999999)
        self.f_reorder_level = QSpinBox(); self.f_reorder_level.setRange(0,9999999)
        self.f_safety_stock  = QSpinBox(); self.f_safety_stock.setRange(0,9999999)
        self.f_reorder_qty   = QSpinBox(); self.f_reorder_qty.setRange(0,9999999)
        self.f_min_order_qty = QSpinBox(); self.f_min_order_qty.setRange(1,999999); self.f_min_order_qty.setValue(1)
        self.f_max_stock     = QSpinBox(); self.f_max_stock.setRange(0,9999999)
        self.lbl_available   = ro_label("—")
        self.lbl_stock_val   = ro_label("—")
        self.lbl_days_left   = ro_label("—")
        self.f_auto_reorder  = QCheckBox("Auto-generate PO when stock hits reorder level")
        self.f_allow_neg     = QCheckBox("Allow negative stock")
        self.f_returnable    = QCheckBox("Product is returnable"); self.f_returnable.setChecked(True)
        self.f_opening_stock.valueChanged.connect(self._update_stock_calcs)

        r = 0
        add_field(g, r, 0, "Opening Stock",   self.f_opening_stock, required=True)
        add_field(g, r, 2, "Reorder Level",   self.f_reorder_level, hint="Alert below this")
        r += 1
        add_field(g, r, 0, "Safety Stock",    self.f_safety_stock, hint="Never go below this buffer")
        add_field(g, r, 2, "Reorder Qty",     self.f_reorder_qty, hint="Suggested PO quantity")
        r += 1
        add_field(g, r, 0, "Min Order Qty",   self.f_min_order_qty)
        add_field(g, r, 2, "Max Stock",       self.f_max_stock)
        r += 1
        add_field(g, r, 0, "Available Stock", self.lbl_available, hint="Stock − Reserved − Damaged")
        add_field(g, r, 2, "Stock Value",     self.lbl_stock_val, hint="Stock × Purchase Price")
        r += 1
        add_field(g, r, 0, "Days of Stock",   self.lbl_days_left, hint="Based on 30-day avg sales")
        r += 1
        g.addWidget(self.f_auto_reorder, r, 0, 1, 4); r += 1
        g.addWidget(self.f_allow_neg,    r, 0, 1, 2)
        g.addWidget(self.f_returnable,   r, 2, 1, 2)
        lay.addWidget(sec)

        sec2, g2 = make_section("Storage Location", "🏬")
        self.f_warehouse = QComboBox(); self.f_warehouse.setEditable(True)
        self.f_warehouse.addItems(["Main Store","Warehouse A","Warehouse B","Cold Storage","Pharmacy Store"])
        self.f_rack = QLineEdit(); self.f_rack.setPlaceholderText("e.g. A3-R2")
        self.f_bin  = QLineEdit(); self.f_bin.setPlaceholderText("e.g. Bin-04")
        r2 = 0
        add_field(g2, r2, 0, "Warehouse",     self.f_warehouse)
        add_field(g2, r2, 2, "Rack / Shelf",  self.f_rack)
        r2 += 1
        add_field(g2, r2, 0, "Bin Location",  self.f_bin, hint="Exact bin for pick list")
        lay.addWidget(sec2)

        sec3, g3 = make_section("Batch & Expiry Tracking", "📅")
        self.f_track_batch  = QCheckBox("Track batch numbers (FIFO)")
        self.f_track_expiry = QCheckBox("Track expiry dates")
        self.f_track_serial = QCheckBox("Track serial numbers (electronics)")
        self.f_mfg_date     = QDateEdit(); self.f_mfg_date.setCalendarPopup(True)
        self.f_mfg_date.setDate(QDate.currentDate()); self.f_mfg_date.setDisplayFormat("dd-MM-yyyy")
        self.f_expiry_date  = QDateEdit(); self.f_expiry_date.setCalendarPopup(True)
        self.f_expiry_date.setDate(QDate.currentDate().addYears(1)); self.f_expiry_date.setDisplayFormat("dd-MM-yyyy")
        self.f_expiry_alert = QSpinBox(); self.f_expiry_alert.setRange(1,365)
        self.f_expiry_alert.setValue(30); self.f_expiry_alert.setSuffix(" days before")
        self.lbl_shelf_calc = ro_label("—")
        self.f_mfg_date.dateChanged.connect(self._calc_shelf); self.f_expiry_date.dateChanged.connect(self._calc_shelf)

        r3 = 0
        g3.addWidget(self.f_track_batch,  r3, 0, 1, 2)
        g3.addWidget(self.f_track_expiry, r3, 2, 1, 2); r3 += 1
        g3.addWidget(self.f_track_serial, r3, 0, 1, 4); r3 += 1
        add_field(g3, r3, 0, "Mfg Date",     self.f_mfg_date)
        add_field(g3, r3, 2, "Expiry Date",  self.f_expiry_date); r3 += 1
        add_field(g3, r3, 0, "Alert Before", self.f_expiry_alert)
        add_field(g3, r3, 2, "Shelf Life",   self.lbl_shelf_calc, hint="Auto from mfg→expiry")
        lay.addWidget(sec3)

        # batch records sub-table
        self.batch_frame = QFrame(); self.batch_frame.setObjectName("section")
        self.batch_frame.setStyleSheet(SEC_STYLE)
        bf_lay = QVBoxLayout(self.batch_frame); bf_lay.setContentsMargins(18,14,18,14); bf_lay.setSpacing(8)
        bh = QHBoxLayout()
        bh.addWidget(QLabel("📦  Batch Records", styleSheet="font-size:13px;font-weight:700;color:#1e3a5f;"))
        bh.addStretch()
        add_b = QPushButton("＋ Add Batch"); add_b.setFixedHeight(30); add_b.setStyleSheet(_btn(SUCCESS))
        add_b.clicked.connect(self._add_batch); bh.addWidget(add_b)
        bf_lay.addLayout(bh)
        self.batch_table = mini_table(["Batch No","Qty","Mfg Date","Expiry","Price","Supplier"])
        bf_lay.addWidget(self.batch_table)
        self.batch_frame.setVisible(False)
        lay.addWidget(self.batch_frame)

        # stock adjustment history
        self.adj_frame = QFrame(); self.adj_frame.setObjectName("section")
        self.adj_frame.setStyleSheet(SEC_STYLE)
        af_lay = QVBoxLayout(self.adj_frame); af_lay.setContentsMargins(18,14,18,14); af_lay.setSpacing(8)
        ah = QHBoxLayout()
        ah.addWidget(QLabel("🔄  Stock Adjustment Log", styleSheet="font-size:13px;font-weight:700;color:#1e3a5f;"))
        ah.addStretch()
        adj_b = QPushButton("＋ Adjust Stock"); adj_b.setFixedHeight(30); adj_b.setStyleSheet(_btn(WARNING))
        adj_b.clicked.connect(self._do_adj); ah.addWidget(adj_b)
        af_lay.addLayout(ah)
        self.adj_table = mini_table(["Type","Qty","Reason","Date","By"])
        af_lay.addWidget(self.adj_table)
        self.adj_frame.setVisible(False)
        lay.addWidget(self.adj_frame)

        lay.addStretch()
        self.tabs.addTab(page, "📦  Inventory")

    def _calc_shelf(self):
        days = self.f_mfg_date.date().daysTo(self.f_expiry_date.date())
        self.lbl_shelf_calc.setText(f"{days} days" if days > 0 else "—")

    def _update_stock_calcs(self):
        s = self.f_opening_stock.value()
        self.lbl_available.setText(str(s))

    def _add_batch(self):
        if not self.edit_code:
            QMessageBox.information(self,"Info","Save the product first before adding batches."); return
        dlg = BatchAddDialog(self.db_name, self.edit_code, self.current_user, self)
        if dlg.exec_() == QDialog.Accepted: self._load_batches()

    def _do_adj(self):
        if not self.edit_code:
            QMessageBox.information(self,"Info","Save the product first."); return
        p = get_product_full(self.db_name, self.edit_code)
        dlg = StockAdjDialog(self.db_name, self.edit_code,
                             self.f_name.text() or self.edit_code,
                             p.get("stock",0) if p else 0, self.current_user, self)
        if dlg.exec_() == QDialog.Accepted: self._load_adj()

    def _load_batches(self):
        rows = get_batches(self.db_name, self.edit_code)
        self.batch_table.setRowCount(0)
        today = date.today()
        for bn, qty, mfg, exp, price, sup, rec in rows:
            r = self.batch_table.rowCount(); self.batch_table.insertRow(r)
            for col, val in enumerate([bn, qty, mfg, exp, f"₹{price:.2f}", sup or ""]):
                item = QTableWidgetItem(str(val or "")); item.setTextAlignment(Qt.AlignCenter)
                if col == 3 and exp:
                    try:
                        diff = (datetime.strptime(exp,"%Y-%m-%d").date() - today).days
                        if diff < 0:
                            item.setBackground(QBrush(QColor("#fee2e2"))); item.setForeground(QBrush(QColor(DANGER)))
                        elif diff <= 30:
                            item.setBackground(QBrush(QColor("#fef3c7"))); item.setForeground(QBrush(QColor(WARNING)))
                    except: pass
                self.batch_table.setItem(r, col, item)

    def _load_adj(self):
        rows = get_stock_adjustments(self.db_name, self.edit_code)
        self.adj_table.setRowCount(0)
        for adj_type, qty, reason, adj_date, by, note in rows:
            r = self.adj_table.rowCount(); self.adj_table.insertRow(r)
            for col, val in enumerate([f"{'▲' if adj_type=='IN' else '▼'} {adj_type}", qty, reason, adj_date, by]):
                item = QTableWidgetItem(str(val or "")); item.setTextAlignment(Qt.AlignCenter)
                if col == 0: item.setForeground(QBrush(QColor(SUCCESS if adj_type=="IN" else DANGER)))
                self.adj_table.setItem(r, col, item)

    # ── TAB 4: SUPPLIER ──────────────────────────────────

    def _build_tab_supplier(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)

        sec, g = make_section("Primary Supplier", "🚚")
        sup_names = get_all_supplier_names(self.db_name)
        self.f_supplier_name  = QComboBox(); self.f_supplier_name.setEditable(True)
        self.f_supplier_name.addItems([""] + sup_names)
        self.f_supplier_code  = QLineEdit(); self.f_supplier_code.setPlaceholderText("Supplier's SKU")
        self.f_supplier_phone = QLineEdit(); self.f_supplier_phone.setPlaceholderText("+91 98765 43210")
        self.f_supplier_email = QLineEdit(); self.f_supplier_email.setPlaceholderText("supplier@example.com")
        self.f_supplier_gstin = QLineEdit(); self.f_supplier_gstin.setPlaceholderText("29AAAAA0000A1Z5")
        self.f_lead_time      = QSpinBox(); self.f_lead_time.setRange(0,365); self.f_lead_time.setSuffix(" days")
        self.f_last_purchase  = price_spin()
        self.f_is_primary     = QCheckBox("Primary supplier — use for auto-PO"); self.f_is_primary.setChecked(True)

        r = 0
        add_field(g, r, 0, "Supplier Name",    self.f_supplier_name)
        add_field(g, r, 2, "Supplier SKU",     self.f_supplier_code)
        r += 1
        add_field(g, r, 0, "Phone",            self.f_supplier_phone)
        add_field(g, r, 2, "Email",            self.f_supplier_email)
        r += 1
        add_field(g, r, 0, "GSTIN",            self.f_supplier_gstin, hint="For GSTR-2A reconciliation")
        add_field(g, r, 2, "Lead Time",        self.f_lead_time, hint="Days to restock")
        r += 1
        add_field(g, r, 0, "Last Purchase ₹",  self.f_last_purchase)
        r += 1
        g.addWidget(self.f_is_primary, r, 0, 1, 4)
        lay.addWidget(sec)

        sec2, g2 = make_section("Physical Dimensions & Variants", "📐")
        def dspin(s): w=QDoubleSpinBox(); w.setRange(0,9999); w.setDecimals(3); w.setSuffix(s); return w
        self.f_weight = dspin(" kg"); self.f_length = dspin(" cm")
        self.f_width  = dspin(" cm"); self.f_height = dspin(" cm")
        self.f_has_variants = QCheckBox("Has variants (size / colour / weight…)")
        self.f_variant_type = QComboBox(); self.f_variant_type.setEditable(True)
        self.f_variant_type.addItems(["Size","Weight","Colour","Flavour","Custom"])
        r2 = 0
        add_field(g2,r2,0,"Weight",self.f_weight); add_field(g2,r2,2,"Length",self.f_length); r2+=1
        add_field(g2,r2,0,"Width", self.f_width);  add_field(g2,r2,2,"Height",self.f_height); r2+=1
        g2.addWidget(self.f_has_variants,r2,0,1,4); r2+=1
        add_field(g2,r2,0,"Variant Type",self.f_variant_type)
        lay.addWidget(sec2)
        lay.addStretch()
        self.tabs.addTab(page, "🚚  Supplier")

    # ── TAB 5: COMPLIANCE ────────────────────────────────

    def _build_tab_compliance(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)

        sec, g = make_section("Food & Drug Compliance", "⚖️")
        self.f_fssai     = QLineEdit(); self.f_fssai.setPlaceholderText("14-digit FSSAI number")
        self.f_drug_lic  = QLineEdit(); self.f_drug_lic.setPlaceholderText("Drug licence number")
        self.f_is_sched  = QCheckBox("Scheduled Drug — requires prescription")
        self.f_sched_type= QComboBox()
        self.f_sched_type.addItems(["","OTC","Schedule H","Schedule H1","Schedule X"])
        r = 0
        add_field(g,r,0,"FSSAI Number",   self.f_fssai, hint="For food products — mandatory on label")
        add_field(g,r,2,"Drug Licence No",self.f_drug_lic); r+=1
        g.addWidget(self.f_is_sched,r,0,1,2)
        add_field(g,r,2,"Schedule Type",  self.f_sched_type)
        lay.addWidget(sec)

        sec2, g2 = make_section("e-Invoice & e-Way Bill", "🖨️")
        self.f_einvoice  = QCheckBox("e-Invoice applicable (B2B > ₹5 Cr turnover)")
        self.f_eway      = QCheckBox("e-Way Bill applicable (goods > ₹50,000 in movement)")
        self.f_print_mrp = QCheckBox("Print MRP on invoice"); self.f_print_mrp.setChecked(True)
        self.f_print_hsn = QCheckBox("Print HSN on invoice"); self.f_print_hsn.setChecked(True)
        self.f_label_fmt = QComboBox()
        self.f_label_fmt.addItems(["40×25 mm","58×40 mm","100×70 mm","A4 sheet"])
        r2 = 0
        g2.addWidget(self.f_einvoice,  r2,0,1,4); r2+=1
        g2.addWidget(self.f_eway,      r2,0,1,4); r2+=1
        g2.addWidget(self.f_print_mrp, r2,0,1,2)
        g2.addWidget(self.f_print_hsn, r2,2,1,2); r2+=1
        add_field(g2,r2,0,"Label Format",self.f_label_fmt)
        lay.addWidget(sec2)
        lay.addStretch()
        self.tabs.addTab(page, "⚖️  Compliance")

    # ── TAB 6: SALES HISTORY ─────────────────────────────

    def _build_tab_history(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)

        # KPI row
        kpi_row = QHBoxLayout(); kpi_row.setSpacing(12)
        def kpi(lbl_text, attr):
            card = QFrame()
            card.setStyleSheet(f"background:{WHITE};border:1px solid {BORDER};border-radius:10px;")
            cl = QVBoxLayout(card); cl.setContentsMargins(14,12,14,12); cl.setSpacing(4)
            t = QLabel(lbl_text); t.setStyleSheet(f"color:{MUTED};font-size:11px;background:transparent;")
            v = QLabel("—"); v.setStyleSheet(f"font-size:18px;font-weight:700;color:{TEXT};background:transparent;")
            cl.addWidget(t); cl.addWidget(v)
            setattr(self, attr, v); return card
        kpi_row.addWidget(kpi("Total Units Sold",  "lbl_total_sold"))
        kpi_row.addWidget(kpi("Total Revenue",     "lbl_total_rev"))
        kpi_row.addWidget(kpi("Return Count",      "lbl_returns"))
        kpi_row.addWidget(kpi("Invoice Count",     "lbl_inv_count"))
        lay.addLayout(kpi_row)

        sec, g = make_section("Sales Stats", "📊")
        self.lbl_last_sold = ro_label("—")
        self.lbl_avg_sp    = ro_label("—")
        add_field(g, 0, 0, "Last Sold Date",   self.lbl_last_sold)
        add_field(g, 0, 2, "Avg Selling Price", self.lbl_avg_sp)
        lay.addWidget(sec)

        # Price history table
        ph_frame = QFrame(); ph_frame.setObjectName("section"); ph_frame.setStyleSheet(SEC_STYLE)
        ph_lay = QVBoxLayout(ph_frame); ph_lay.setContentsMargins(18,14,18,14); ph_lay.setSpacing(8)
        ph_lay.addWidget(QLabel("📈  Price History", styleSheet="font-size:13px;font-weight:700;color:#1e3a5f;"))
        self.price_hist_table = mini_table(["Date","Purchase","Selling","MRP","Changed By"], height=160)
        ph_lay.addWidget(self.price_hist_table)
        lay.addWidget(ph_frame)

        hint = QLabel("💡  Sales history populates in Edit mode after product is saved and sold.")
        hint.setStyleSheet(f"color:{MUTED};font-size:12px;padding:8px;")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)
        lay.addStretch()
        self.tabs.addTab(page, "📊  Sales History")

    def _load_history(self):
        if not self.edit_code: return
        p = get_product_full(self.db_name, self.edit_code) or {}
        self.lbl_total_sold.setText(str(p.get("total_qty_sold",0)))
        self.lbl_total_rev.setText(f"₹{float(p.get('total_revenue',0)):,.0f}")
        self.lbl_returns.setText(str(p.get("return_count",0)))
        self.lbl_inv_count.setText(str(p.get("sale_count",0)))
        self.lbl_last_sold.setText(p.get("last_sold_date","—") or "—")
        self.lbl_avg_sp.setText(f"₹{float(p.get('selling_price',0)):,.2f}")
        rows = get_price_history(self.db_name, self.edit_code)
        self.price_hist_table.setRowCount(0)
        for pur, sell, mrp, ch_at, ch_by, note in rows:
            r = self.price_hist_table.rowCount(); self.price_hist_table.insertRow(r)
            for col, val in enumerate([ch_at, f"₹{pur:.2f}", f"₹{sell:.2f}", f"₹{mrp:.2f}", ch_by]):
                item = QTableWidgetItem(str(val or "")); item.setTextAlignment(Qt.AlignCenter)
                self.price_hist_table.setItem(r, col, item)

    # ── TAB 7: AUDIT ─────────────────────────────────────

    def _build_tab_audit(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)
        sec, g = make_section("Audit Trail", "🗃️")
        self.lbl_created_at = ro_label("—"); self.lbl_created_by = ro_label("—")
        self.lbl_updated_at = ro_label("—"); self.lbl_updated_by = ro_label("—")
        self.lbl_is_deleted = ro_label("No ✅"); self.lbl_deleted_at = ro_label("—")
        add_field(g, 0, 0, "Created At",   self.lbl_created_at)
        add_field(g, 0, 2, "Created By",   self.lbl_created_by)
        add_field(g, 1, 0, "Last Updated", self.lbl_updated_at)
        add_field(g, 1, 2, "Updated By",   self.lbl_updated_by)
        add_field(g, 2, 0, "Soft Deleted", self.lbl_is_deleted)
        add_field(g, 2, 2, "Deleted At",   self.lbl_deleted_at)
        lay.addWidget(sec)
        hint = QLabel("🔒  Read-only. All changes are recorded automatically.")
        hint.setStyleSheet(f"color:{MUTED};font-size:12px;padding:8px;")
        hint.setAlignment(Qt.AlignCenter); lay.addWidget(hint)
        lay.addStretch()
        self.tabs.addTab(page, "🗃️  Audit")

    def _load_audit(self):
        if not self.edit_code: return
        p = self.prod
        self.lbl_created_at.setText(p.get("created_at","—") or "—")
        self.lbl_created_by.setText(p.get("created_by","—") or "—")
        self.lbl_updated_at.setText(p.get("updated_at","—") or "—")
        self.lbl_updated_by.setText(p.get("updated_by","—") or "—")
        self.lbl_is_deleted.setText("Yes ⚠️" if p.get("is_deleted") else "No ✅")
        self.lbl_deleted_at.setText(p.get("deleted_at","—") or "—")

    # ── IMAGE ────────────────────────────────────────────

    def _upload_image(self):
        path, _ = QFileDialog.getOpenFileName(self,"Select Image","","Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            with open(path,"rb") as f: self._image_blob = f.read()
            px = QPixmap(path)
            if not px.isNull():
                self.img_label.setPixmap(px.scaled(100,100,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                self.img_label.setText("")

    def _clear_image(self):
        self._image_blob = b""; self.img_label.clear(); self.img_label.setText("No Image")

    # ── LOAD / RESET / POPULATE ──────────────────────────

    def load_for_add(self):
        self.edit_code = None; self.prod = {}
        self.title_lbl.setText("Add Product"); self.btn_save.setText("💾  Save Product")
        self._reset_fields()
        self.f_item_code.setReadOnly(False); self.f_auto_code.setVisible(True); self.f_auto_code.setChecked(False)
        self.batch_frame.setVisible(False); self.adj_frame.setVisible(False)
        self.tabs.setCurrentIndex(0)

    def load_for_edit(self, item_code):
        self.edit_code = item_code; self.prod = get_product_full(self.db_name, item_code) or {}
        self.title_lbl.setText(f"Edit — {item_code}"); self.btn_save.setText("💾  Update Product")
        self._reset_fields(); self._populate()
        self.f_item_code.setReadOnly(True); self.f_auto_code.setVisible(False)
        self.batch_frame.setVisible(True); self.adj_frame.setVisible(True)
        self._load_batches(); self._load_adj(); self._load_history(); self._load_audit()
        self.tabs.setCurrentIndex(0)

    def _toggle_code(self, state):
        if state:
            self.f_item_code.setText(get_next_item_code(self.db_name)); self.f_item_code.setReadOnly(True)
        else:
            self.f_item_code.clear(); self.f_item_code.setReadOnly(False)

    def _reset_fields(self):
        self._image_blob = b""; self.img_label.clear(); self.img_label.setText("No Image")
        for w in self.findChildren(QLineEdit):
            if not w.isReadOnly(): w.clear()
        for w in self.findChildren(QTextEdit):   w.clear()
        for w in self.findChildren(QSpinBox):    w.setValue(w.minimum())
        for w in self.findChildren(QDoubleSpinBox): w.setValue(0)
        for w in self.findChildren(QComboBox):   w.setCurrentIndex(0)
        for w in self.findChildren(QCheckBox):   w.setChecked(False)
        self.f_pack_size.setValue(1); self.f_min_order_qty.setValue(1)
        self.f_expiry_alert.setValue(30); self.f_returnable.setChecked(True)
        self.f_print_mrp.setChecked(True); self.f_print_hsn.setChecked(True)
        self.f_is_primary.setChecked(True)
        self.f_mfg_date.setDate(QDate.currentDate())
        self.f_expiry_date.setDate(QDate.currentDate().addYears(1))
        self.lbl_margin.setText("—"); self.lbl_markup.setText("—")

    def _populate(self):
        p = self.prod
        def sv(w, key, default=""):
            val = p.get(key, default)
            if val is None: val = default
            if isinstance(w, QLineEdit):               w.setText(str(val))
            elif isinstance(w, QComboBox):
                idx = w.findText(str(val))
                if idx >= 0: w.setCurrentIndex(idx)
                else:        w.setEditText(str(val))
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                try: w.setValue(float(val))
                except: pass
            elif isinstance(w, QCheckBox):             w.setChecked(bool(val))
            elif isinstance(w, QTextEdit):             w.setPlainText(str(val))
            elif isinstance(w, QDateEdit):
                d = QDate.fromString(str(val), "yyyy-MM-dd")
                if d.isValid(): w.setDate(d)
            elif isinstance(w, QLabel):                w.setText(str(val) if val else "—")

        # Basic
        sv(self.f_item_code,"item_code");    sv(self.f_sku,"sku")
        sv(self.f_name,"name");              sv(self.f_alias,"alias_names")
        sv(self.f_barcode,"barcode");        sv(self.f_hsn,"hsn_code")
        sv(self.f_prod_type,"product_type"); sv(self.f_tax_cat,"tax_category")
        sv(self.f_product_group,"product_group"); sv(self.f_category,"category")
        sv(self.f_sub_cat,"sub_category");   sv(self.f_brand,"brand")
        sv(self.f_manufacturer,"manufacturer"); sv(self.f_country,"country_of_origin")
        sv(self.f_unit,"unit");              sv(self.f_pack_size,"pack_size",1)
        sv(self.f_meter,"meter");            sv(self.f_shelf_life,"shelf_life_days")
        sv(self.f_storage,"storage_condition"); sv(self.f_tags,"tags")
        sv(self.f_desc,"description");       sv(self.f_notes,"internal_notes")
        sv(self.f_status,"status")
        img = p.get("image")
        if isinstance(img,(bytes,bytearray)) and img:
            self._image_blob = img; px = QPixmap(); px.loadFromData(img)
            if not px.isNull():
                self.img_label.setPixmap(px.scaled(100,100,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                self.img_label.setText("")
        # Pricing
        sv(self.f_mrp,"mrp");                    sv(self.f_purchase_price,"purchase_price")
        sv(self.f_selling_price,"selling_price"); sv(self.f_retail_price,"retail_price")
        sv(self.f_wholesale_price,"wholesale_price"); sv(self.f_dealer_price,"dealer_price")
        sv(self.f_min_selling_price,"min_selling_price"); sv(self.f_special_price,"special_price")
        sv(self.f_sp_from,"special_price_from"); sv(self.f_sp_to,"special_price_to")
        sv(self.f_discount_pct,"discount_pct"); sv(self.f_tax_inclusive,"tax_inclusive")
        sv(self.f_gst_rate,"gst_rate");        sv(self.f_igst_rate,"igst_rate")
        sv(self.f_tax_type,"tax_type");        sv(self.f_cess_pct,"cess_pct")
        sv(self.f_tcs,"tcs_applicable");       sv(self.f_gst_ex,"gst_exemption_reason")
        self._update_margin()
        # Inventory
        sv(self.f_opening_stock,"opening_stock"); sv(self.f_reorder_level,"reorder_level")
        sv(self.f_safety_stock,"safety_stock");   sv(self.f_reorder_qty,"reorder_qty")
        sv(self.f_min_order_qty,"min_order_qty",1); sv(self.f_max_stock,"max_stock")
        sv(self.f_auto_reorder,"auto_reorder"); sv(self.f_allow_neg,"allow_neg_stock")
        sv(self.f_returnable,"is_returnable"); sv(self.f_warehouse,"warehouse")
        sv(self.f_rack,"rack_location");       sv(self.f_bin,"bin_location")
        sv(self.f_track_batch,"track_batch"); sv(self.f_track_expiry,"track_expiry")
        sv(self.f_track_serial,"track_serial"); sv(self.f_mfg_date,"mfg_date")
        sv(self.f_expiry_date,"expiry_date"); sv(self.f_expiry_alert,"expiry_alert_days",30)
        self._calc_shelf()
        cur = p.get("stock",0); res = p.get("reserved_stock",0); dam = p.get("damaged_stock",0)
        self.lbl_available.setText(str(max(0, cur-res-dam)))
        pp = p.get("purchase_price",0)
        self.lbl_stock_val.setText(f"₹{cur*pp:,.2f}" if pp else "—")
        sold = p.get("total_qty_sold",0)
        if sold > 0:
            daily = sold/30; days = int(cur/daily) if daily > 0 else 0
            c = DANGER if days < 7 else (WARNING if days < 15 else SUCCESS)
            self.lbl_days_left.setText(f"{days} days")
            self.lbl_days_left.setStyleSheet(
                f"background:#f8fafc;border:1px solid #e2e8f0;border-radius:7px;"
                f"padding:5px 10px;font-size:13px;font-weight:700;color:{c};min-height:32px;")
        # Supplier
        sv(self.f_supplier_name,"supplier_name"); sv(self.f_supplier_code,"supplier_code")
        sv(self.f_supplier_phone,"supplier_phone"); sv(self.f_supplier_email,"supplier_email")
        sv(self.f_supplier_gstin,"supplier_gstin"); sv(self.f_lead_time,"lead_time_days")
        sv(self.f_last_purchase,"last_purchase_price")
        sv(self.f_weight,"weight_kg"); sv(self.f_length,"length_cm")
        sv(self.f_width,"width_cm");  sv(self.f_height,"height_cm")
        sv(self.f_has_variants,"has_variants"); sv(self.f_variant_type,"variant_type")
        # Compliance
        sv(self.f_fssai,"fssai_number");    sv(self.f_drug_lic,"drug_license_no")
        sv(self.f_is_sched,"is_scheduled_drug"); sv(self.f_sched_type,"schedule_type")
        sv(self.f_einvoice,"e_invoice_applicable"); sv(self.f_eway,"e_way_bill_applicable")
        sv(self.f_print_mrp,"print_mrp_on_invoice"); sv(self.f_print_hsn,"print_hsn_on_invoice")
        sv(self.f_label_fmt,"label_format")

    def _collect(self):
        gst  = self.f_gst_rate.currentText().split("—")[0].strip().split(" ")[0]
        igst = self.f_igst_rate.currentText().split("—")[0].strip().split(" ")[0]
        return {
            "item_code":             self.f_item_code.text().strip(),
            "sku":                   self.f_sku.text().strip(),
            "name":                  self.f_name.text().strip(),
            "alias_names":           self.f_alias.text().strip(),
            "description":           self.f_desc.toPlainText().strip(),
            "product_type":          self.f_prod_type.currentText(),
            "tax_category":          self.f_tax_cat.currentText(),
            "product_group":         self.f_product_group.text().strip(),
            "category":              self.f_category.currentText().strip(),
            "sub_category":          self.f_sub_cat.text().strip(),
            "brand":                 self.f_brand.text().strip(),
            "manufacturer":          self.f_manufacturer.text().strip(),
            "country_of_origin":     self.f_country.text().strip() or "India",
            "hsn_code":              self.f_hsn.text().strip(),
            "barcode":               self.f_barcode.text().strip(),
            "tags":                  self.f_tags.text().strip(),
            "unit":                  self.f_unit.currentText().strip(),
            "pack_size":             self.f_pack_size.value(),
            "meter":                 self.f_meter.text().strip(),
            "shelf_life_days":       self.f_shelf_life.value(),
            "storage_condition":     self.f_storage.currentText(),
            "image":                 self._image_blob or None,
            "mrp":                   self.f_mrp.value(),
            "purchase_price":        self.f_purchase_price.value(),
            "selling_price":         self.f_selling_price.value(),
            "retail_price":          self.f_retail_price.value(),
            "wholesale_price":       self.f_wholesale_price.value(),
            "dealer_price":          self.f_dealer_price.value(),
            "min_selling_price":     self.f_min_selling_price.value(),
            "special_price":         self.f_special_price.value(),
            "special_price_from":    self.f_sp_from.date().toString("yyyy-MM-dd"),
            "special_price_to":      self.f_sp_to.date().toString("yyyy-MM-dd"),
            "discount_pct":          self.f_discount_pct.value(),
            "tax_inclusive":         int(self.f_tax_inclusive.isChecked()),
            "gst_rate":              gst,
            "igst_rate":             igst,
            "tax_type":              self.f_tax_type.currentText(),
            "cess_pct":              self.f_cess_pct.value(),
            "tcs_applicable":        int(self.f_tcs.isChecked()),
            "gst_exemption_reason":  self.f_gst_ex.text().strip(),
            "opening_stock":         self.f_opening_stock.value(),
            "stock":                 self.f_opening_stock.value() if not self.edit_code
                                     else self.prod.get("stock", self.f_opening_stock.value()),
            "reorder_level":         self.f_reorder_level.value(),
            "safety_stock":          self.f_safety_stock.value(),
            "reorder_qty":           self.f_reorder_qty.value(),
            "min_order_qty":         self.f_min_order_qty.value(),
            "max_stock":             self.f_max_stock.value(),
            "auto_reorder":          int(self.f_auto_reorder.isChecked()),
            "allow_neg_stock":       int(self.f_allow_neg.isChecked()),
            "is_returnable":         int(self.f_returnable.isChecked()),
            "warehouse":             self.f_warehouse.currentText().strip(),
            "rack_location":         self.f_rack.text().strip(),
            "bin_location":          self.f_bin.text().strip(),
            "track_batch":           int(self.f_track_batch.isChecked()),
            "track_expiry":          int(self.f_track_expiry.isChecked()),
            "track_serial":          int(self.f_track_serial.isChecked()),
            "mfg_date":              self.f_mfg_date.date().toString("yyyy-MM-dd"),
            "expiry_date":           self.f_expiry_date.date().toString("yyyy-MM-dd"),
            "expiry_alert_days":     self.f_expiry_alert.value(),
            "supplier_name":         self.f_supplier_name.currentText().strip(),
            "supplier_code":         self.f_supplier_code.text().strip(),
            "supplier_phone":        self.f_supplier_phone.text().strip(),
            "supplier_email":        self.f_supplier_email.text().strip(),
            "supplier_gstin":        self.f_supplier_gstin.text().strip(),
            "lead_time_days":        self.f_lead_time.value(),
            "last_purchase_price":   self.f_last_purchase.value(),
            "weight_kg":             self.f_weight.value(),
            "length_cm":             self.f_length.value(),
            "width_cm":              self.f_width.value(),
            "height_cm":             self.f_height.value(),
            "has_variants":          int(self.f_has_variants.isChecked()),
            "variant_type":          self.f_variant_type.currentText().strip(),
            "fssai_number":          self.f_fssai.text().strip(),
            "drug_license_no":       self.f_drug_lic.text().strip(),
            "is_scheduled_drug":     int(self.f_is_sched.isChecked()),
            "schedule_type":         self.f_sched_type.currentText(),
            "e_invoice_applicable":  int(self.f_einvoice.isChecked()),
            "e_way_bill_applicable": int(self.f_eway.isChecked()),
            "print_mrp_on_invoice":  int(self.f_print_mrp.isChecked()),
            "print_hsn_on_invoice":  int(self.f_print_hsn.isChecked()),
            "label_format":          self.f_label_fmt.currentText(),
            "internal_notes":        self.f_notes.toPlainText().strip(),
            "status":                self.f_status.currentText(),
        }

    def _cancel(self): self.on_cancel()

    def _save(self):
        data = self._collect()
        if not data["name"]:
            QMessageBox.warning(self,"Validation","Product name is required.")
            self.tabs.setCurrentIndex(0); self.f_name.setFocus(); return
        if not data["item_code"]:
            QMessageBox.warning(self,"Validation","Item code is required.")
            self.tabs.setCurrentIndex(0); self.f_item_code.setFocus(); return
        if data["selling_price"] <= 0:
            QMessageBox.warning(self,"Validation","Selling price must be > 0.")
            self.tabs.setCurrentIndex(1); self.f_selling_price.setFocus(); return
        if data["mrp"] > 0 and data["selling_price"] > data["mrp"]:
            if QMessageBox.question(self,"Warning",
                f"Selling price ₹{data['selling_price']:.2f} exceeds MRP ₹{data['mrp']:.2f}.\nContinue?",
                QMessageBox.Yes|QMessageBox.No) == QMessageBox.No:
                return
        if self.edit_code:
            d = dict(data); d.pop("item_code",None); d.pop("opening_stock",None)
            update_product(self.db_name, self.edit_code, d, self.current_user)
            self.on_saved(self.edit_code)
        else:
            if not save_product(self.db_name, data, self.current_user):
                QMessageBox.critical(self,"Error","Could not save.\nItem code may already exist."); return
            self.on_saved(data["item_code"])


# ─────────────────────────────────────────────────────────
#  PRODUCT LIST WIDGET
# ─────────────────────────────────────────────────────────

class ProductListWidget(QWidget):
    def __init__(self, db_name, company_name, on_back, on_add, on_edit,
                 current_user="Admin", embedded=False, parent=None):
        """
        embedded=True  → called from Dashboard; skip the inner top bar
                          (Dashboard already has TopBar + sidebar).
        embedded=False → standalone mode; show the compact top bar.
        """
        super().__init__(parent)
        self.db_name      = db_name
        self._on_edit     = on_edit
        self._filters     = {}
        self.current_user = current_user

        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)

        # ── top bar (only in standalone / non-embedded mode) ──
        if not embedded:
            top = QFrame(); top.setFixedHeight(62)
            top.setStyleSheet(f"background:{WHITE}; border-bottom:1px solid {BORDER};")
            tl = QHBoxLayout(top); tl.setContentsMargins(16,0,16,0)
            back_btn = QPushButton("←  Back")
            back_btn.setFixedSize(90,34)
            back_btn.setStyleSheet(_btn("#eef5ff", PRIMARY))
            back_btn.clicked.connect(lambda: on_back() if on_back else None)
            center = QLabel(company_name); center.setAlignment(Qt.AlignCenter)
            center.setFont(QFont(FONT, 14, QFont.Bold))
            center.setStyleSheet(f"color:{TEXT};")
            add_btn = QPushButton("＋  Add Product")
            add_btn.setFixedSize(150,34); add_btn.setStyleSheet(_btn(PRIMARY))
            add_btn.clicked.connect(on_add)
            tl.addWidget(back_btn); tl.addStretch()
            tl.addWidget(center); tl.addStretch()
            tl.addWidget(add_btn)
            layout.addWidget(top)

        # content area
        content = QWidget(); content.setStyleSheet(f"background:{BG_LIGHT};")
        cl = QVBoxLayout(content); cl.setContentsMargins(24,16,24,16); cl.setSpacing(10)

        # ── title row + Add button (shown in embedded mode instead of top bar) ──
        tr = QHBoxLayout()
        title = QLabel("Products")
        title.setFont(QFont(FONT, 16, QFont.Bold))
        title.setStyleSheet(f"color:{TEXT};")
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{MUTED};font-size:12px;")
        tr.addWidget(title); tr.addWidget(self.count_lbl); tr.addStretch()
        if embedded:
            add_btn2 = QPushButton("＋  Add Product")
            add_btn2.setFixedSize(150,36); add_btn2.setStyleSheet(_btn(PRIMARY))
            add_btn2.clicked.connect(on_add)
            tr.addWidget(add_btn2)
        cl.addLayout(tr)

        # filter bar
        ff = QFrame()
        ff.setStyleSheet(f"background:{WHITE};border:1px solid {BORDER};border-radius:10px;")
        fl = QHBoxLayout(ff); fl.setContentsMargins(12,8,12,8); fl.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search code / name / alias / barcode…")
        self.search_input.setFixedHeight(34)
        self.search_input.setStyleSheet(
            f"border:1px solid {BORDER};border-radius:6px;padding:5px 10px;"
            f"font-size:13px;color:{TEXT};background:{BG_LIGHT};"
        )
        self.search_input.textChanged.connect(self._on_filter)

        self.flt_status = QComboBox()
        self.flt_status.setFixedHeight(34); self.flt_status.setFixedWidth(130)
        self.flt_status.addItems(["All Status","Active","Draft","Inactive","Discontinued"])
        self.flt_status.setStyleSheet(FIELD_STYLE)
        self.flt_status.currentTextChanged.connect(self._on_filter)

        self.flt_cat = QComboBox()
        self.flt_cat.setFixedHeight(34); self.flt_cat.setFixedWidth(140)
        self.flt_cat.setStyleSheet(FIELD_STYLE)
        self.flt_cat.currentTextChanged.connect(self._on_filter)

        self.flt_stock = QComboBox()
        self.flt_stock.setFixedHeight(34); self.flt_stock.setFixedWidth(130)
        self.flt_stock.addItems(["All Stock","Low Stock","Out of Stock"])
        self.flt_stock.setStyleSheet(FIELD_STYLE)
        self.flt_stock.currentTextChanged.connect(self._on_filter)

        clr = QPushButton("✕ Clear")
        clr.setFixedSize(72,34); clr.setStyleSheet(_btn("#f1f5f9", MUTED))
        clr.clicked.connect(self._clear_filters)

        fl.addWidget(self.search_input, 1)
        fl.addWidget(self.flt_status)
        fl.addWidget(self.flt_cat)
        fl.addWidget(self.flt_stock)
        fl.addWidget(clr)
        cl.addWidget(ff)

        # product table — 12 columns
        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "Item Code","Product Name","Category","Unit",
            "MRP ₹","Sell ₹","Margin","Stock","Reorder","Expiry","Status","Actions"
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        for col, w in enumerate([90,0,100,58,90,90,70,65,70,100,85,120]):
            if w: self.table.setColumnWidth(col, w)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget{{background:white;border:1px solid {BORDER};
                border-radius:10px;gridline-color:#f0f4f8;font-size:13px;}}
            QHeaderView::section{{background:#f8fafc;font-weight:700;padding:8px;
                border:none;border-bottom:2px solid {BORDER};color:#475569;}}
            QTableWidget::item{{padding:6px 8px;color:{TEXT};}}
            QTableWidget::item:selected{{background:#eef5ff;color:#111;}}
            QTableWidget::item:alternate{{background:#fafbfc;}}
        """)
        # Single click handler — dispatches Edit / Stock / Delete by sub-column text
        self.table.cellClicked.connect(self._on_cell_clicked)
        self._row_codes: list = []          # parallel list: row index → item_code
        self._row_stocks: list = []         # parallel list: row index → current stock
        cl.addWidget(self.table)
        layout.addWidget(content)

        self._reload_cats()
        self._load_table()

        # Fix black dropdown on Windows for all filter combos
        for combo in self.findChildren(QComboBox):
            fix_combo(combo)

    def _reload_cats(self):
        self.flt_cat.blockSignals(True); self.flt_cat.clear()
        self.flt_cat.addItems(get_categories(self.db_name))
        self.flt_cat.blockSignals(False)

    def _on_filter(self):
        st  = self.flt_status.currentText()
        cat = self.flt_cat.currentText()
        stk = self.flt_stock.currentText()
        self._filters = {
            "search":       self.search_input.text().strip(),
            "status":       st  if st  != "All Status" else "All",
            "category":     cat if cat not in ("All","") else "All",
            "stock_filter": stk if stk != "All Stock"  else "All",
        }
        self._load_table()

    def _clear_filters(self):
        # block signals so each clear() doesn't trigger 3 separate reloads
        self.search_input.blockSignals(True)
        self.flt_status.blockSignals(True)
        self.flt_cat.blockSignals(True)
        self.flt_stock.blockSignals(True)
        self.search_input.clear()
        self.flt_status.setCurrentIndex(0)
        self.flt_cat.setCurrentIndex(0)
        self.flt_stock.setCurrentIndex(0)
        self.search_input.blockSignals(False)
        self.flt_status.blockSignals(False)
        self.flt_cat.blockSignals(False)
        self.flt_stock.blockSignals(False)
        self._filters = {}
        self._load_table()           # ← was missing: table never refreshed after clear

    def _load_table(self, rows=None):
        if rows is None:
            rows = get_all_products(self.db_name, self._filters)

        today = date.today()
        tbl   = self.table

        # ── Freeze rendering while populating ─────────────────
        tbl.setUpdatesEnabled(False)
        tbl.setSortingEnabled(False)
        tbl.setRowCount(0)
        self._row_codes  = []
        self._row_stocks = []

        for rd in rows:
            code, name, cat, unit, sell, mrp, stock, reorder, \
                status, gst, expiry, last_sold, purchase, brand = rd

            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setRowHeight(r, 40)
            self._row_codes.append(code)
            self._row_stocks.append(int(stock or 0))

            def _item(txt, align=Qt.AlignLeft | Qt.AlignVCenter):
                it = QTableWidgetItem(str(txt))
                it.setTextAlignment(align)
                return it

            tbl.setItem(r, 0, _item(code or ""))
            tbl.setItem(r, 1, _item(name or ""))
            tbl.setItem(r, 2, _item(cat  or ""))
            tbl.setItem(r, 3, _item(unit or "", Qt.AlignCenter))

            # MRP
            mrp_v = float(mrp or 0)
            tbl.setItem(r, 4, _item(f"₹{mrp_v:,.2f}" if mrp_v else "—",
                                    Qt.AlignRight | Qt.AlignVCenter))
            # Sell
            sp_v = float(sell or 0)
            tbl.setItem(r, 5, _item(f"₹{sp_v:,.2f}",
                                    Qt.AlignRight | Qt.AlignVCenter))
            # Margin
            pp_v = float(purchase or 0)
            if pp_v > 0:
                margin = (sp_v - pp_v) / pp_v * 100
                mg = _item(f"{margin:.1f}%", Qt.AlignCenter)
                mg.setForeground(QBrush(QColor(SUCCESS if margin >= 0 else DANGER)))
            else:
                mg = _item("—", Qt.AlignCenter)
            tbl.setItem(r, 6, mg)

            # Stock
            stk_v = int(stock or 0)
            rod_v = int(reorder or 0)
            si = _item(str(stk_v), Qt.AlignCenter)
            if stk_v == 0:
                si.setForeground(QBrush(QColor(DANGER)))
                si.setBackground(QBrush(QColor("#fee2e2")))
            elif rod_v and stk_v <= rod_v:
                si.setForeground(QBrush(QColor(WARNING)))
                si.setBackground(QBrush(QColor("#fef3c7")))
            tbl.setItem(r, 7, si)

            # Reorder
            tbl.setItem(r, 8, _item(str(rod_v) if rod_v else "—", Qt.AlignCenter))

            # Expiry
            exp_txt   = "—"
            exp_color = None
            if expiry:
                try:
                    diff = (datetime.strptime(expiry, "%Y-%m-%d").date() - today).days
                    exp_txt = expiry
                    if diff < 0:     exp_color = DANGER
                    elif diff <= 30: exp_color = WARNING
                except Exception:
                    pass
            ei = _item(exp_txt, Qt.AlignCenter)
            if exp_color:
                ei.setForeground(QBrush(QColor(exp_color)))
                ei.setBackground(QBrush(QColor(
                    "#fee2e2" if exp_color == DANGER else "#fef3c7"
                )))
            tbl.setItem(r, 9, ei)

            # Status badge
            sc = {
                "Active":       ("#eef5ff", "#1a7fe8"),
                "Draft":        ("#fef3c7", "#d97706"),
                "Inactive":     ("#f1f5f9", "#64748b"),
                "Discontinued": ("#fee2e2", "#ef4444"),
            }.get(status, ("#f1f5f9", "#64748b"))
            sti = _item(str(status or ""), Qt.AlignCenter)
            sti.setBackground(QBrush(QColor(sc[0])))
            sti.setForeground(QBrush(QColor(sc[1])))
            tbl.setItem(r, 10, sti)

            # Actions — plain text labels; clicks handled by _on_cell_clicked
            act = _item("✏️  ±  🗑", Qt.AlignCenter)
            act.setToolTip("Click to Edit | Adjust Stock | Delete")
            act.setForeground(QBrush(QColor(MUTED)))
            tbl.setItem(r, 11, act)

        # ── Unfreeze ───────────────────────────────────────────
        tbl.setUpdatesEnabled(True)
        self.count_lbl.setText(
            f"  {tbl.rowCount()} product{'s' if tbl.rowCount() != 1 else ''}"
        )

    def _on_cell_clicked(self, row: int, col: int):
        """Dispatch Edit / Stock-adjust / Delete from the actions column."""
        if col != 11:
            return
        if row >= len(self._row_codes):
            return
        code  = self._row_codes[row]
        stock = self._row_stocks[row]
        # Ask what the user wants to do
        name_item = self.table.item(row, 1)
        name = name_item.text() if name_item else code

        msg = QMessageBox(self)
        msg.setWindowTitle(f"Actions — {name}")
        msg.setText(f"<b>{name}</b>  ({code})\nChoose an action:")
        edit_btn  = msg.addButton("✏️  Edit",         QMessageBox.ActionRole)
        adj_btn   = msg.addButton("±  Adjust Stock",  QMessageBox.ActionRole)
        del_btn   = msg.addButton("🗑  Delete",        QMessageBox.DestructiveRole)
        msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked == edit_btn:
            self._on_edit(code)
        elif clicked == adj_btn:
            self._stock_adj(code, name, stock)
        elif clicked == del_btn:
            self._confirm_delete(code)

    def _stock_adj(self, code, name, stock):
        dlg = StockAdjDialog(
            self.db_name, code, name, stock,
            user=self.current_user, parent=self
        )
        if dlg.exec_() == QDialog.Accepted:
            self._load_table()

    def _confirm_delete(self, item_code):
        reply = QMessageBox.question(
            self, "Delete Product",
            f"Soft-delete '{item_code}'?\n"
            "It will be hidden but kept in DB (safe for old invoices).",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            soft_delete_product(self.db_name, item_code, self.current_user)
            self._load_table()

    def refresh(self):
        self._reload_cats()
        self._load_table()


# ─────────────────────────────────────────────────────────
#  PRODUCT PAGE  (stacked: list ↔ form)
# ─────────────────────────────────────────────────────────

class ProductPage(QWidget):
    """
    Two-phase construction to eliminate UI freeze on first click:

    Phase 1 (instant — runs synchronously on click):
        • DB migration runs (guarded by _initialized_dbs, near-instant on 2nd+)
        • ProductListWidget is built (lightweight — just a table + filter bar)
        • Widget is shown immediately, user sees product list at once

    Phase 2 (deferred — QTimer.singleShot(0) after first paint):
        • ProductFormWidget (7 tabs, 200+ widgets) is built in next event-loop tick
        • If user clicks Add/Edit before Phase 2 finishes, a retry timer waits 50 ms
    """

    def __init__(self, db_name, company_name="", on_back=None,
                 current_user="Admin", embedded=True):
        super().__init__()
        self.db_name       = db_name
        self.current_user  = current_user
        self._form_ready   = False

        # DB migration — guarded so only runs once per session
        init_product_table(db_name, current_user)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # ── Index 0: product list (built immediately — lightweight) ──
        self.list_widget = ProductListWidget(
            db_name      = db_name,
            company_name = company_name,
            on_back      = on_back,
            on_add       = self._show_add,
            on_edit      = self._show_edit,
            current_user = current_user,
            embedded     = embedded,
        )
        self.stack.addWidget(self.list_widget)   # index 0

        # ── Index 1: loading placeholder shown while form builds ──
        self._loading_page = QWidget()
        self._loading_page.setStyleSheet(f"background:{BG_LIGHT};")
        _ll = QVBoxLayout(self._loading_page)
        _ll.setAlignment(Qt.AlignCenter)
        _lbl = QLabel("⏳  Loading product form…")
        _lbl.setAlignment(Qt.AlignCenter)
        _lbl.setStyleSheet(f"font-size:16px; color:{MUTED}; background:transparent;")
        _ll.addWidget(_lbl)
        self.stack.addWidget(self._loading_page) # index 1

        self.form_widget = None
        self.stack.setCurrentIndex(0)

        # Defer heavy form build until after this widget is first painted
        QTimer.singleShot(0, self._build_form_deferred)

    # ── Phase 2: deferred heavy construction ─────────────────

    def _build_form_deferred(self):
        """Runs after Qt has painted the list page — no visible freeze."""
        self.form_widget = ProductFormWidget(
            db_name      = self.db_name,
            on_saved     = self._on_saved,
            on_cancel    = self._show_list,
            current_user = self.current_user,
        )
        # Insert at index 1, pushing the loading page to index 2 (never shown again)
        self.stack.insertWidget(1, self.form_widget)
        self._form_ready = True

    # ── Navigation ────────────────────────────────────────────

    def _show_list(self):
        self.stack.setCurrentIndex(0)

    def _show_add(self):
        if not self._form_ready:
            # Form still building — show loader and retry in 50 ms
            self.stack.setCurrentIndex(2)
            QTimer.singleShot(50, self._show_add)
            return
        self.form_widget.load_for_add()
        self.stack.setCurrentWidget(self.form_widget)

    def _show_edit(self, code):
        if not self._form_ready:
            self.stack.setCurrentIndex(2)
            QTimer.singleShot(50, lambda: self._show_edit(code))
            return
        self.form_widget.load_for_edit(code)
        self.stack.setCurrentWidget(self.form_widget)

    def _on_saved(self, _):
        self.list_widget.refresh()
        self._show_list()


# ─────────────────────────────────────────────────────────
#  STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Find the real project DB (same logic as new_claude.py) ──
    db_files = glob.glob("*.db")
    if db_files:
        DB = db_files[0]
    else:
        DB = "evo_aura.db"   # fallback — will be created fresh

    # ── Load company name from new_claude if available ──────────
    company_name = "Evo Aura"
    try:
        from new_claude import load_company_info, init_db
        init_db(DB)
        info = load_company_info(DB)
        if info.get("company_name"):
            company_name = info["company_name"]
    except Exception:
        pass   # running without new_claude.py is fine — uses fallback name

    win = ProductPage(
        DB,
        company_name = company_name,
        current_user = "Admin",
        embedded     = False,   # standalone: show inner top-bar with Back button
    )
    win.setWindowTitle(f"Product Manager — {company_name}")
    win.resize(1280, 800)
    win.show()
    sys.exit(app.exec_())