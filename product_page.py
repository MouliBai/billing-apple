"""
product_page.py  —  Evo Aura  •  Advanced Product Manager
==========================================================
PyQt6  |  SQLite  |  Apple / EvoAura design system

7-tab form: Basic · Pricing · Inventory · Supplier · Compliance · Sales History · Audit
Supporting tables: batches, stock_adjustments, price_history, suppliers, product_suppliers
List page: filter bar, expiry badges, MRP/margin columns, inline stock-adjust button
Soft-delete, audit trail, image upload, live margin %, days-of-stock-left

Architecture:
  ProductPage (QWidget)
    ├── ProductListWidget  — searchable / filterable table
    └── ProductFormWidget  — 7-tab form (stacked, deferred build)

The Add/Edit overlay fades in as a full-size page over the product list.
A semi-transparent scrim dims the list behind it.
"""

import sys
import glob
import sqlite3
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QGridLayout, QComboBox,
    QAbstractItemView, QListWidget, QListWidgetItem,
    QCheckBox, QRadioButton, QButtonGroup, QTabWidget, QScrollArea, QDateEdit, QDoubleSpinBox,
    QSpinBox, QTextEdit, QApplication, QSizePolicy,
    QGraphicsOpacityEffect, QStyledItemDelegate, QStyle,
    QStackedWidget, QDialog, QVBoxLayout, QFileDialog, QToolButton,
)
from PyQt6.QtGui  import (
    QFont, QColor, QBrush, QPainter, QLinearGradient,
    QPixmap, QPalette,
)
from PyQt6.QtCore import (
    Qt, QDate, QRect, QObject, QEvent,
    QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve,
)


class _NoWheelValueFilter(QObject):
    """Prevent page scrolling from changing field values."""
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel:
            return True
        return super().eventFilter(watched, event)


# ─────────────────────────────────────────────────────────────
#  COMBOBOX ITEM DELEGATE  — forces black text on every item
# ─────────────────────────────────────────────────────────────
class _ComboDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        opt = option.__class__(option)
        is_selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        is_hover    = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        if is_selected or is_hover:
            painter.fillRect(opt.rect, QColor("#1A73E8" if is_selected else "#FA2D48"))
            opt.palette.setColor(QPalette.ColorRole.Text,
                                  QColor("#FFFFFF"))
        else:
            painter.fillRect(opt.rect, QColor("#FFFFFF"))
            opt.palette.setColor(QPalette.ColorRole.Text, QColor("#000000"))
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        super().paint(painter, opt, index)
        painter.restore()


def _apply_combo_delegate(cb):
    cb.setItemDelegate(_ComboDelegate(cb))
    v = cb.view()
    pal = v.palette()
    pal.setColor(QPalette.ColorRole.Base,            QColor("#FFFFFF"))
    pal.setColor(QPalette.ColorRole.Text,            QColor("#000000"))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor("#F5F5F7"))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor("#1A73E8"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    v.setPalette(pal)


# ─────────────────────────────────────────────────────────────
#  DESIGN TOKENS  —  Apple / EvoAura
# ─────────────────────────────────────────────────────────────
C = dict(
    bg_white      = "#FFFFFF",
    bg_light      = "#F5F5F7",
    bg_panel      = "#F2F2F7",
    bg_card       = "#FAFAFA",

    accent        = "#FA2D48",
    accent_dark   = "#C81F36",
    accent_tint   = "rgba(250,45,72,0.08)",
    accent_tint2  = "rgba(250,45,72,0.10)",
    accent_border = "rgba(250,45,72,0.22)",

    success       = "#27ae60",
    success_dark  = "#1e8449",
    success_tint  = "#edfbf4",
    warning       = "#e67e22",
    warning_tint  = "#fff8ee",
    danger_tint   = "#fff0f0",

    text          = "#000000",
    text2         = "#6E6E73",
    text3         = "#A1A1A6",

    input_bg      = "#FFFFFF",
    border        = "#D2D2D7",
    hover_bg      = "#E5E5EA",

    section_hdr   = "#1D1D1F",
    section_icon  = "#FA2D48",

    blue          = "#1A73E8",
    blue_tint     = "#EEF5FF",
    blue_dark     = "#1558B0",
)

# ─────────────────────────────────────────────────────────────
#  GLOBAL FIELD STYLESHEET
# ─────────────────────────────────────────────────────────────
FIELD_SS = f"""
    QLabel {{
        border     : none;
        background : transparent;
    }}

    QLineEdit, QTextEdit {{
        border        : 1.5px solid {C['border']};
        border-radius : 8px;
        padding       : 6px 10px;
        font-size     : 13px;
        background    : #FFFFFF;
        color         : #000000;
        min-height    : 34px;
        selection-background-color : {C['accent']};
        selection-color            : white;
    }}
    QLineEdit:hover, QTextEdit:hover {{
        border     : 1.5px solid {C['blue']};
        background : #FFFFFF;
        color      : #000000;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border     : 2px solid {C['accent']};
        background : #FFF8F9;
        color      : #000000;
    }}
    QLineEdit:read-only {{
        background : {C['bg_light']};
        color      : {C['text3']};
        border     : 1.5px solid {C['border']};
    }}

    QSpinBox, QDoubleSpinBox {{
        border        : 1.5px solid {C['border']};
        border-radius : 8px;
        padding       : 6px 10px 6px 10px;
        padding-right : 2px;
        font-size     : 13px;
        background    : #FFFFFF;
        color         : #000000;
        min-height    : 34px;
    }}
    QSpinBox:hover, QDoubleSpinBox:hover {{ border : 1.5px solid {C['blue']}; }}
    QSpinBox:focus, QDoubleSpinBox:focus {{ border : 2px solid {C['accent']}; background:#FFF8F9; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        width:0; height:0; subcontrol-position:top right;
        border:none; background:transparent; image:none;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width:0; height:0; subcontrol-position:bottom right;
        border:none; background:transparent; image:none;
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        width:0; height:0; image:none; border:none;
    }}

    QComboBox {{
        border        : 1.5px solid {C['border']};
        border-radius : 8px;
        padding       : 6px 10px;
        font-size     : 13px;
        background    : #FFFFFF;
        color         : #000000;
        min-height    : 34px;
    }}
    QComboBox:hover {{ border : 1.5px solid {C['blue']}; background:#FFFFFF; color:#000000; }}
    QComboBox:focus {{ border : 2px solid {C['accent']}; background:#FFF8F9; color:#000000; }}
    QComboBox::drop-down {{ border:none; width:24px; }}
    QComboBox::down-arrow {{
        image:none;
        border-left:5px solid transparent;
        border-right:5px solid transparent;
        border-top:6px solid {C['text3']};
        margin-right:6px;
    }}
    QComboBox QAbstractItemView {{
        background:#FFFFFF; color:#000000;
        selection-background-color:{C['blue']};
        selection-color:#FFFFFF;
        border:1px solid {C['border']};
        border-radius:8px; padding:4px; outline:none;
        show-decoration-selected:1;
    }}
    QComboBox QAbstractItemView::item {{
        color:#000000; background:#FFFFFF;
        min-height:32px; padding:4px 10px; border:none;
    }}
    QComboBox QAbstractItemView::item:hover    {{ background:{C['accent']}; color:#FFFFFF; }}
    QComboBox QAbstractItemView::item:selected {{ background:{C['blue']}; color:#FFFFFF; }}

    QDateEdit {{
        border:1.5px solid {C['border']}; border-radius:8px;
        padding:6px 10px; font-size:13px; background:#FFFFFF;
        color:#000000; min-height:34px;
    }}
    QDateEdit:hover {{ border:1.5px solid {C['blue']}; }}
    QDateEdit:focus {{ border:2px solid {C['accent']}; background:#FFF8F9; }}
    QDateEdit::drop-down {{ border:none; width:24px; }}
    QDateEdit::down-arrow {{
        image:none;
        border-left:5px solid transparent;
        border-right:5px solid transparent;
        border-top:6px solid {C['text3']};
        margin-right:6px;
    }}

    QCheckBox {{
        font-size:13px; color:#000000;
        background:transparent;
        spacing:8px;
    }}
    QCheckBox:hover {{ color:{C['blue']}; }}
    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width:20px; height:20px; border-radius:5px;
        border:2.5px solid #111111;
        background:#FFFFFF;
        margin-left:0px; margin-right:6px;
    }}
    QCheckBox::indicator:unchecked {{
        border:2.5px solid #111111;
        background:#FFFFFF;
    }}
    QCheckBox::indicator:unchecked:hover {{
        border:2.5px solid #000000;
        background:#f5f5f5;
    }}
    QCheckBox::indicator:checked {{
        border:2.5px solid #000000;
        background:#111111;
    }}
    QCheckBox::indicator:checked:hover {{
        border:2.5px solid #000000;
        background:#333333;
    }}



    QCalendarWidget {{
        background:{C['bg_white']}; color:{C['text']};
        border:1.5px solid {C['border']}; border-radius:10px;
    }}
    QCalendarWidget * {{ background:{C['bg_white']}; color:{C['text']}; }}
    QCalendarWidget QWidget {{
        background:{C['bg_white']}; color:{C['text']};
        alternate-background-color:{C['bg_light']};
    }}
    QCalendarWidget QAbstractItemView {{
        background:{C['bg_white']}; color:{C['text']};
        selection-background-color:{C['accent']};
        selection-color:white; outline:none;
    }}
    QCalendarWidget QTableView {{
        background:{C['bg_white']}; color:{C['text']};
        gridline-color:{C['border']};
        selection-background-color:{C['accent']}; selection-color:white;
    }}
    QCalendarWidget QToolButton {{
        background:{C['bg_white']}; color:{C['text']};
        border:none; border-radius:6px; padding:4px 8px;
        font-size:13px; font-weight:600;
    }}
    QCalendarWidget QToolButton:hover {{ background:#E8F0FE; color:{C['blue']}; }}
    QCalendarWidget QToolButton::menu-indicator {{ image:none; }}
    QCalendarWidget #qt_calendar_navigationbar {{
        background:{C['bg_white']}; color:{C['text']};
        border-bottom:1px solid {C['border']}; padding:4px;
    }}
"""

TAB_SS = f"""
    QTabWidget::pane {{
        border: none;
        background: #ffffff;
        border-radius: 12px;
    }}
    QTabBar {{
        alignment: left;
    }}
    QTabBar::tab {{
        background: #ffffff;
        color: {C['text2']};
        padding: 9px 0px;
        min-width: 118px; max-width: 138px;
        border-radius: 8px;
        margin-right: 4px;
        font-size: 12px; font-weight: 600;
        border: 1px solid {C['border']};
    }}
    QTabBar::tab:selected {{
        background: {C['accent']};
        color: white;
        font-weight: 700;
        border: 1px solid {C['accent_dark']};
    }}
    QTabBar::tab:hover:!selected {{
        background: {C['hover_bg']};
        color: {C['text']};
        border: 1px solid #c0c0c5;
    }}
"""

LABEL_SS  = f"color:{C['text2']};background:transparent;font-weight:500;font-size:12px;border:none;"
HINT_SS   = f"color:{C['text3']};background:transparent;font-size:11px;margin-top:1px;border:none;"
SEC_HDR_SS = f"color:{C['section_hdr']};background:transparent;font-size:13px;font-weight:700;border:none;"

_ALL_VARIANT_SIZES = [str(size) for size in range(16, 49, 2)]
AGE_CATEGORIES = ["Generic", "1 - 3 age", "4 - 18 age", "18+ age"]
VARIANT_STORAGE_GROUP = "Size"
COLOR_STORAGE_GROUP = "Color"
CUSTOM_STORAGE_GROUP = "Custom"
COLOR_GROUPS = {
    "Whites & Creams": ["White", "Off White", "Ivory", "Cream", "Pearl White", "Eggshell"],
    "Blacks & Greys": ["Black", "Charcoal Grey", "Ash Grey", "Light Grey", "Steel Grey", "Smoke Grey"],
    "Reds": ["Red", "Maroon", "Burgundy", "Wine", "Crimson", "Cherry Red", "Brick Red", "Ruby Red", "Tomato Red"],
    "Pinks": ["Baby Pink", "Light Pink", "Rose Pink", "Hot Pink", "Rani Pink", "Fuchsia", "Blush Pink", "Peach Pink"],
    "Oranges": ["Orange", "Rust Orange", "Coral", "Peach", "Terracotta", "Burnt Orange"],
    "Yellows": ["Yellow", "Lemon Yellow", "Mustard", "Golden Yellow", "Sunflower Yellow", "Turmeric Yellow"],
    "Greens": ["Green", "Light Green", "Dark Green", "Bottle Green", "Olive Green", "Parrot Green", "Mint Green", "Mehendi Green", "Pistachio Green", "Emerald Green", "Sea Green"],
    "Blues": ["Sky Blue", "Baby Blue", "Aqua Blue", "Turquoise", "Peacock Blue", "Royal Blue", "Sapphire Blue", "Navy Blue", "Ink Blue", "Teal Blue"],
    "Purples": ["Lavender", "Lilac", "Purple", "Violet", "Plum", "Magenta", "Orchid"],
    "Browns": ["Brown", "Coffee Brown", "Chocolate Brown", "Camel", "Tan", "Walnut"],
    "Metallic & Festive Colors": ["Gold", "Antique Gold", "Rose Gold", "Silver", "Copper", "Bronze"],
    "Traditional Saree/Churidar Colors": ["Rani Pink", "Peacock Blue", "Mehendi Green", "Mango Yellow", "Kumkum Red", "Sindoor Red", "Lotus Pink", "Onion Pink", "Rama Green", "Rama Blue", "Sandal", "Vadamalli Purple"],
    "Mixed Variants": ["Multicolor", "Dual Shade", "Ombre", "Printed Mix", "Floral Mix", "Contrast Color"],
}
LEGACY_VARIANT_GROUPS = {
    "Kids": "1 - 3 age",
    "Boys & Girls": "4 - 18 age",
    "Men & Women": "18+ age",
}

# ─────────────────────────────────────────────────────────────
#  SESSION-LEVEL DB INIT GUARD
# ─────────────────────────────────────────────────────────────
_initialized_dbs: set = set()


# ─────────────────────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────────────────────
def init_product_table(db_name, current_user="system"):
    global _initialized_dbs
    if db_name in _initialized_dbs:
        return
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
            track_mfg             INTEGER DEFAULT 0,
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code  TEXT NOT NULL,
            variant_group TEXT DEFAULT '',
            size          TEXT NOT NULL,
            stock         INTEGER DEFAULT 0,
            barcode       TEXT DEFAULT '',
            UNIQUE(product_code, variant_group, size)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS product_purchase_log (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code       TEXT NOT NULL,
            invoice_no         TEXT NOT NULL,
            purchase_date      TEXT NOT NULL,
            stock_qty          INTEGER DEFAULT 0,
            purchase_price     REAL DEFAULT 0,
            purchase_gst       TEXT DEFAULT '0%',
            price_including_gst REAL DEFAULT 0,
            created_at         TEXT DEFAULT '',
            created_by         TEXT DEFAULT ''
        )
    """)

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
        ("description","TEXT DEFAULT ''"), ("sub_category","TEXT DEFAULT ''"),
        ("brand","TEXT DEFAULT ''"), ("manufacturer","TEXT DEFAULT ''"),
        ("hsn_code","TEXT DEFAULT ''"), ("barcode","TEXT DEFAULT ''"),
        ("pack_size","INTEGER DEFAULT 1"), ("purchase_price","REAL DEFAULT 0"),
        ("selling_price","REAL DEFAULT 0"), ("wholesale_price","REAL DEFAULT 0"),
        ("min_selling_price","REAL DEFAULT 0"), ("discount_pct","REAL DEFAULT 0"),
        ("discount_val","REAL DEFAULT 0"), ("margin_pct","REAL DEFAULT 0"),
        ("purchase_gst","TEXT DEFAULT '0%'"),
        ("use_alias_in_billing","INTEGER DEFAULT 0"),
        ("tax_inclusive","INTEGER DEFAULT 0"), ("gst_rate","TEXT DEFAULT '0%'"),
        ("tax_type","TEXT DEFAULT 'CGST+SGST'"), ("cess_pct","REAL DEFAULT 0"),
        ("opening_stock","INTEGER DEFAULT 0"), ("reorder_level","INTEGER DEFAULT 0"),
        ("min_order_qty","INTEGER DEFAULT 1"), ("max_stock","INTEGER DEFAULT 0"),
        ("warehouse","TEXT DEFAULT ''"), ("rack_location","TEXT DEFAULT ''"),
        ("track_batch","INTEGER DEFAULT 0"), ("track_expiry","INTEGER DEFAULT 0"),
        ("track_mfg","INTEGER DEFAULT 0"),
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
    _initialized_dbs.add(db_name)


# ── Query helpers ──────────────────────────────────────────

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
        with sqlite3.connect(db_name) as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM products WHERE category!='' AND is_deleted=0 ORDER BY category"
            ).fetchall()
        return ["All"] + [r[0] for r in rows]
    except Exception:
        return ["All"]


def get_all_supplier_names(db_name):
    try:
        with sqlite3.connect(db_name) as conn:
            rows = conn.execute("SELECT name FROM suppliers ORDER BY name").fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def get_supplier_by_name(db_name, name):
    """Return supplier row dict or None."""
    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.execute("SELECT * FROM suppliers WHERE name=?", (name,))
            row = cur.fetchone()
            if not row: return None
            return dict(zip([d[0] for d in cur.description], row))
    except Exception:
        return None


def create_supplier(db_name, name, phone="", email="", gstin="", address=""):
    """Insert new supplier, return its code."""
    import time
    name = name.strip()
    if not name:
        return None
    now  = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_name) as conn:
            row = conn.execute(
                "SELECT code FROM suppliers WHERE lower(name)=lower(?) LIMIT 1",
                (name,),
            ).fetchone()
            if row:
                return row[0]
            base = "SUP" + str(int(time.time()))[-7:]
            code = base
            n = 1
            while conn.execute("SELECT 1 FROM suppliers WHERE code=? LIMIT 1", (code,)).fetchone():
                code = f"{base}{n}"
                n += 1
            conn.execute(
                "INSERT INTO suppliers(code,name,phone,email,gstin,address,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (code, name, phone.strip(), email.strip(),
                 gstin.strip(), address.strip(), now))
            conn.commit()
        return code
    except Exception:
        return None


def save_product_supplier(db_name, product_code, supplier_code,
                          sup_sku="", unit_price=0.0, moq=1,
                          lead_days=0, is_primary=0, default_qty=1):
    """Upsert product_suppliers row."""
    now = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_name) as conn:
            conn.execute("""
                INSERT INTO product_suppliers
                    (product_code, supplier_code, supplier_product_code,
                     unit_price, moq, lead_time_days, is_primary, pack_size, last_ordered_date)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(product_code, supplier_code) DO UPDATE SET
                    supplier_product_code = excluded.supplier_product_code,
                    unit_price            = excluded.unit_price,
                    moq                   = excluded.moq,
                    lead_time_days        = excluded.lead_time_days,
                    is_primary            = excluded.is_primary,
                    pack_size             = excluded.pack_size
            """, (product_code, supplier_code, sup_sku, unit_price,
                  moq, lead_days, is_primary, default_qty, now))
            if is_primary:
                conn.execute(
                    "UPDATE product_suppliers SET is_primary=0 "
                    "WHERE product_code=? AND supplier_code!=?",
                    (product_code, supplier_code))
            conn.commit()
    except Exception as e:
        print("save_product_supplier error:", e)


def get_product_suppliers(db_name, product_code):
    """Return list of dicts for all suppliers linked to this product."""
    try:
        with sqlite3.connect(db_name) as conn:
            rows = conn.execute("""
                SELECT ps.*, s.name, s.phone, s.email, s.gstin, s.address
                FROM product_suppliers ps
                JOIN suppliers s ON s.code = ps.supplier_code
                WHERE ps.product_code = ?
                ORDER BY ps.is_primary DESC, s.name
            """, (product_code,)).fetchall()
            if not rows: return []
            cur = conn.execute("""
                SELECT ps.*, s.name, s.phone, s.email, s.gstin, s.address
                FROM product_suppliers ps
                JOIN suppliers s ON s.code = ps.supplier_code
                WHERE ps.product_code = ?
                ORDER BY ps.is_primary DESC, s.name
            """, (product_code,))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []


def get_next_item_code(db_name):
    with sqlite3.connect(db_name) as conn:
        rows = conn.execute(
            "SELECT item_code FROM products WHERE item_code LIKE 'P%'"
        ).fetchall()
    max_no = 0
    for (code,) in rows:
        suffix = str(code or "")[1:]
        if suffix.isdigit():
            max_no = max(max_no, int(suffix))
    return f"P{max_no + 1:05d}"


def _ean13_checksum(first_12_digits: str) -> str:
    total = 0
    for i, ch in enumerate(first_12_digits):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return str((10 - (total % 10)) % 10)


def get_next_ean13(db_name):
    """Generate a valid EAN-13 barcode with checksum."""
    with sqlite3.connect(db_name) as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] + 1
        while True:
            first_12 = f"890{count:09d}"[-12:]
            code = first_12 + _ean13_checksum(first_12)
            exists = conn.execute(
                "SELECT 1 FROM products WHERE barcode=? LIMIT 1", (code,)
            ).fetchone()
            if not exists:
                return code
            count += 1


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
        with sqlite3.connect(db_name) as conn:
            return conn.execute(
                "SELECT batch_number, qty, mfg_date, expiry_date, purchase_price, supplier_name, received_date "
                "FROM batches WHERE product_code=? ORDER BY expiry_date",
                (product_code,)
            ).fetchall()
    except Exception:
        return []


def get_price_history(db_name, product_code):
    try:
        with sqlite3.connect(db_name) as conn:
            return conn.execute(
                "SELECT purchase_price, selling_price, mrp, changed_at, changed_by, note "
                "FROM price_history WHERE product_code=? ORDER BY changed_at DESC LIMIT 10",
                (product_code,)
            ).fetchall()
    except Exception:
        return []


def get_stock_adjustments(db_name, product_code):
    try:
        with sqlite3.connect(db_name) as conn:
            return conn.execute(
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
        conn.commit()
        return True
    except Exception as e:
        print("Save error:", e)
        return False
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
    conn.commit()
    conn.close()


def get_product_variants(db_name, product_code, variant_group=VARIANT_STORAGE_GROUP):
    with sqlite3.connect(db_name) as conn:
        rows = conn.execute(
            "SELECT variant_group, size, stock, barcode FROM product_variants WHERE product_code=?",
            (product_code,)
        ).fetchall()
    if variant_group in (COLOR_STORAGE_GROUP, CUSTOM_STORAGE_GROUP):
        return {
            (variant_group, str(name or "")): {
                "stock": int(stock or 0), "barcode": barcode or ""
            }
            for group, name, stock, barcode in rows
            if group == variant_group
        }
    merged = {}
    for group, size, stock, barcode in rows:
        if group in (COLOR_STORAGE_GROUP, CUSTOM_STORAGE_GROUP):
            continue
        key = (VARIANT_STORAGE_GROUP, str(size or ""))
        current = merged.get(key, {"stock": 0, "barcode": ""})
        current["stock"] = max(current["stock"], int(stock or 0))
        if not current["barcode"] and barcode:
            current["barcode"] = barcode
        merged[key] = current
    return merged


def save_product_variants(db_name, product_code, variant_group, rows):
    with sqlite3.connect(db_name) as conn:
        for group, size, stock_delta, barcode in rows:
            group = variant_group
            delta = int(stock_delta or 0)
            if delta <= 0:
                if group == CUSTOM_STORAGE_GROUP:
                    conn.execute(
                        "INSERT OR IGNORE INTO product_variants "
                        "(product_code, variant_group, size, stock, barcode) "
                        "VALUES (?,?,?,?,?)",
                        (product_code, group, str(size), 0, barcode or ""),
                    )
                continue
            old = conn.execute(
                "SELECT stock FROM product_variants WHERE product_code=? AND variant_group=? AND size=?",
                (product_code, group, str(size))
            ).fetchone()
            qty = int(old[0] if old else 0) + delta
            conn.execute("""
                INSERT INTO product_variants (product_code, variant_group, size, stock, barcode)
                VALUES (?,?,?,?,?)
                ON CONFLICT(product_code, variant_group, size)
                DO UPDATE SET stock=excluded.stock, barcode=excluded.barcode
            """, (product_code, group, str(size), qty, barcode or ""))
        total = conn.execute(
            "SELECT COALESCE(SUM(stock), 0) FROM product_variants "
            "WHERE product_code=? AND variant_group=?",
            (product_code, variant_group)
        ).fetchone()[0]
        conn.execute(
            "UPDATE products SET stock=? WHERE item_code=?",
            (int(total or 0), product_code)
        )
    return int(total or 0)


def delete_product_variants(db_name, product_code):
    with sqlite3.connect(db_name) as conn:
        conn.execute("DELETE FROM product_variants WHERE product_code=?", (product_code,))


def delete_other_variant_mode(db_name, product_code, keep_group):
    """Remove stale rows from the mutually-exclusive variant mode."""
    with sqlite3.connect(db_name) as conn:
        if keep_group in (COLOR_STORAGE_GROUP, CUSTOM_STORAGE_GROUP):
            conn.execute(
                "DELETE FROM product_variants WHERE product_code=? AND variant_group<>?",
                (product_code, keep_group),
            )
        else:
            conn.execute(
                "DELETE FROM product_variants WHERE product_code=? "
                "AND variant_group IN (?,?)",
                (product_code, COLOR_STORAGE_GROUP, CUSTOM_STORAGE_GROUP),
            )


def save_purchase_log(db_name, product_code, invoice_no, purchase_date, qty,
                      purchase_price, purchase_gst, user="system"):
    try:
        gst_pct = float(str(purchase_gst).replace("%", "").strip())
    except Exception:
        gst_pct = 0.0
    price_with_gst = round(float(purchase_price or 0) * (1 + gst_pct / 100), 2)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_name) as conn:
        conn.execute("""
            INSERT INTO product_purchase_log
            (product_code, invoice_no, purchase_date, stock_qty, purchase_price,
             purchase_gst, price_including_gst, created_at, created_by)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (product_code, invoice_no, purchase_date, int(qty or 0),
              float(purchase_price or 0), purchase_gst, price_with_gst, now, user))


def get_purchase_log(db_name, product_code):
    if not product_code:
        return []
    with sqlite3.connect(db_name) as conn:
        return conn.execute("""
            SELECT invoice_no, purchase_date, stock_qty, purchase_price,
                   purchase_gst, price_including_gst
            FROM product_purchase_log
            WHERE product_code=?
            ORDER BY purchase_date DESC, id DESC
        """, (product_code,)).fetchall()


def soft_delete_product(db_name, item_code, current_user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_name) as conn:
        conn.execute(
            "UPDATE products SET is_deleted=1, deleted_at=?, deleted_by=?, status='Inactive' WHERE item_code=?",
            (now, current_user, item_code)
        )


def save_stock_adjustment(db_name, product_code, adj_type, qty, reason,
                          batch="", note="", user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_name) as conn:
        conn.execute("""
            INSERT INTO stock_adjustments
            (product_code, adj_type, qty, reason, batch_number, adj_date, created_by, note)
            VALUES (?,?,?,?,?,?,?,?)
        """, (product_code, adj_type, qty, reason, batch, now, user, note))
        if adj_type == "IN":
            conn.execute("UPDATE products SET stock=stock+? WHERE item_code=?", (qty, product_code))
        else:
            conn.execute("UPDATE products SET stock=MAX(0,stock-?) WHERE item_code=?", (qty, product_code))


def save_batch(db_name, product_code, batch_no, qty, mfg, expiry, price, supplier, user="system"):
    now = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(db_name) as conn:
        try:
            conn.execute("""
                INSERT INTO batches
                (product_code, batch_number, qty, mfg_date, expiry_date,
                 purchase_price, supplier_name, received_date, created_by)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (product_code, batch_no, qty, mfg, expiry, price, supplier, now, user))
        except sqlite3.IntegrityError:
            conn.execute("UPDATE batches SET qty=qty+? WHERE product_code=? AND batch_number=?",
                         (qty, product_code, batch_no))
    save_stock_adjustment(db_name, product_code, "IN", qty, f"Batch {batch_no} received", batch_no, user=user)


# ─────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────
def _F(sz=13, bold=False) -> QFont:
    f = QFont("SF Pro Text", sz)
    if bold: f.setWeight(QFont.Weight.Bold)
    return f

def _gap(h: int) -> QWidget:
    w = QWidget(); w.setFixedHeight(h)
    w.setStyleSheet("background:transparent;")
    return w


def make_section(title: str, icon: str = "") -> tuple:
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background:{C['bg_white']};
            border:1px solid {C['border']};
            border-radius:12px;
        }}
    """)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(20, 14, 20, 18)
    outer.setSpacing(10)

    hdr = QHBoxLayout(); hdr.setSpacing(6)
    if icon:
        ico = QLabel(icon)
        ico.setStyleSheet(f"font-size:15px;color:{C['section_icon']};background:transparent;border:none;")
        hdr.addWidget(ico)
    lbl = QLabel(title)
    lbl.setFont(_F(13, bold=True))
    lbl.setStyleSheet(SEC_HDR_SS)
    hdr.addWidget(lbl); hdr.addStretch()
    outer.addLayout(hdr)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"background:{C['border']};border:none;max-height:1px;")
    outer.addWidget(sep)

    grid = QGridLayout()
    grid.setSpacing(8)
    grid.setColumnMinimumWidth(0, 140)
    grid.setColumnMinimumWidth(1, 170)
    grid.setColumnMinimumWidth(2, 140)
    grid.setColumnMinimumWidth(3, 170)
    outer.addLayout(grid)
    return frame, grid


FORM_FIELD_HEIGHT = 38

FORM_INPUT_SS = f"""
    QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 6px 10px;
        font-size: 13px;
        background: #ffffff;
        color: #000000;
        min-height: {FORM_FIELD_HEIGHT}px;
        max-height: {FORM_FIELD_HEIGHT}px;
        height: {FORM_FIELD_HEIGHT}px;
    }}
    QLineEdit:hover, QComboBox:hover, QDateEdit:hover,
    QSpinBox:hover, QDoubleSpinBox:hover {{
        border: 1.5px solid {C['blue']};
        background: #ffffff;
        color: #000000;
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {C['accent']};
        background: #FFF8F9;
        color: #000000;
    }}
    QComboBox::drop-down, QDateEdit::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow, QDateEdit::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {C['text3']};
        margin-right: 6px;
    }}
    QComboBox QLineEdit {{
        border: none;
        border-radius: 0;
        padding: 0;
        background: transparent;
        color: #000000;
        min-height: 0;
        max-height: none;
    }}
    QComboBox QAbstractItemView {{
        background: #ffffff;
        color: #000000;
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 4px;
        outline: none;
        selection-background-color: {C['blue']};
        selection-color: #ffffff;
        show-decoration-selected: 1;
    }}
    QComboBox QAbstractItemView::item {{
        min-height: {FORM_FIELD_HEIGHT}px;
        padding: 6px 10px;
        color: #000000;
        background: #ffffff;
        border: none;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {C['accent']};
        color: #ffffff;
    }}
    QComboBox QAbstractItemView::item:selected {{
        background: {C['blue']};
        color: #ffffff;
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 0;
        height: 0;
        border: none;
        background: transparent;
        image: none;
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        width: 0;
        height: 0;
        image: none;
        border: none;
    }}
"""

COMBO_POPUP_SS = f"""
    QListView, QAbstractItemView {{
        background: #ffffff;
        color: #000000;
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 4px;
        outline: none;
        selection-background-color: {C['blue']};
        selection-color: #ffffff;
        show-decoration-selected: 1;
    }}
    QListView::item, QAbstractItemView::item {{
        min-height: {FORM_FIELD_HEIGHT}px;
        padding: 6px 10px;
        color: #000000;
        background: #ffffff;
        border: none;
    }}
    QListView::item:hover, QAbstractItemView::item:hover {{
        background: {C['accent']};
        color: #ffffff;
    }}
    QListView::item:selected, QAbstractItemView::item:selected {{
        background: {C['blue']};
        color: #ffffff;
    }}
"""

CALENDAR_POPUP_SS = f"""
    QCalendarWidget {{
        background: {C['bg_white']};
        color: {C['text']};
        border: 1.5px solid {C['border']};
        border-radius: 10px;
    }}
    QCalendarWidget QWidget {{
        background: {C['bg_white']};
        color: {C['text']};
        alternate-background-color: {C['bg_light']};
    }}
    QCalendarWidget #qt_calendar_navigationbar {{
        background: {C['bg_white']};
        color: {C['text']};
        border-bottom: 1px solid {C['border']};
        padding: 4px;
    }}
    QCalendarWidget QToolButton {{
        background: {C['bg_white']};
        color: {C['text']};
        border: none;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 13px;
        font-weight: 600;
    }}
    QCalendarWidget QToolButton:hover {{
        background: #E8F0FE;
        color: {C['blue']};
    }}
    QCalendarWidget QToolButton::menu-indicator {{
        image: none;
    }}
    QCalendarWidget QMenu {{
        background: #ffffff;
        color: #000000;
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 4px;
    }}
    QCalendarWidget QMenu::item {{
        background: #ffffff;
        color: #000000;
        padding: 6px 18px;
        min-height: 24px;
    }}
    QCalendarWidget QMenu::item:selected,
    QCalendarWidget QMenu::item:hover {{
        background: #E8F0FE;
        color: #000000;
    }}
    QCalendarWidget QSpinBox {{
        background: #ffffff;
        color: #000000;
        border: 1px solid {C['border']};
        border-radius: 6px;
        padding: 2px 6px;
        min-height: 24px;
    }}
    QCalendarWidget QAbstractItemView {{
        background: #ffffff;
        color: #000000;
        selection-background-color: {C['accent']};
        selection-color: #ffffff;
        outline: none;
    }}
    QCalendarWidget QTableView {{
        background: #ffffff;
        color: #000000;
        gridline-color: {C['border']};
        selection-background-color: {C['accent']};
        selection-color: #ffffff;
    }}
"""

CALENDAR_MENU_SS = f"""
    QMenu {{
        background: #ffffff;
        color: #000000;
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        background: #ffffff;
        color: #000000;
        padding: 6px 18px;
        min-height: 24px;
    }}
    QMenu::item:selected,
    QMenu::item:hover {{
        background: #E8F0FE;
        color: #000000;
    }}
"""


def _apply_calendar_theme(date_edit):
    cal = date_edit.calendarWidget()
    if not cal:
        return
    cal.setStyleSheet(CALENDAR_POPUP_SS)
    pal = cal.palette()
    for role in (
        QPalette.ColorRole.Window,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.AlternateBase,
    ):
        pal.setColor(role, QColor("#FFFFFF" if role != QPalette.ColorRole.AlternateBase else C['bg_light']))
    pal.setColor(QPalette.ColorRole.Text, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(C['accent']))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    cal.setPalette(pal)
    for btn in cal.findChildren(QToolButton):
        menu = btn.menu()
        if menu:
            menu.setStyleSheet(CALENDAR_MENU_SS)


def _normalize_field_widget(widget):
    if isinstance(widget, (QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox)):
        widget.setFixedHeight(FORM_FIELD_HEIGHT)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setStyleSheet(FORM_INPUT_SS)
        if isinstance(widget, QComboBox):
            _apply_combo_delegate(widget)
            widget.view().setMouseTracking(True)
            widget.view().viewport().setMouseTracking(True)
            widget.view().setStyleSheet(COMBO_POPUP_SS)
            if widget.isEditable() and widget.lineEdit():
                widget.lineEdit().setStyleSheet(
                    "border:none;background:transparent;padding:0;color:#000000;"
                )
        elif isinstance(widget, QDateEdit):
            widget.setCalendarPopup(True)
            _apply_calendar_theme(widget)


def add_field(grid, row, col, label, widget, required=False, hint="", span=1):
    _normalize_field_widget(widget)
    lbl = QLabel(label)
    lbl.setFont(_F(12))
    lbl.setStyleSheet(LABEL_SS)
    if required:
        lbl.setText(label + "  <span style='color:" + C['accent'] + "'>*</span>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
    grid.addWidget(lbl, row, col)
    col_span = 1 + (span - 1) * 2
    if hint:
        container = QWidget(); container.setStyleSheet("background:transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0); vbox.setSpacing(2)
        vbox.addWidget(widget)
        h_lbl = QLabel(hint); h_lbl.setStyleSheet(HINT_SS)
        h_lbl.setWordWrap(True)
        vbox.addWidget(h_lbl)
        grid.addWidget(container, row, col + 1, 1, col_span)
    else:
        grid.addWidget(widget, row, col + 1, 1, col_span)


def ro_label(text="—"):
    l = QLabel(text)
    l.setStyleSheet(
        f"background:{C['bg_light']};border:1px solid {C['border']};border-radius:8px;"
        f"padding:6px 10px;font-size:13px;color:{C['text2']};min-height:34px;"
    )
    return l


# ── CHK_SS kept for legacy compatibility (no longer used) ────────────────────
CHK_SS = ""   # replaced by ToggleSwitch widget

# ── Toggle Switch Widget ──────────────────────────────────────────────────────
class ToggleSwitch(QCheckBox):
    """A smooth iOS/Material-style toggle switch that replaces QCheckBox.
    Visually matches the CSS checkbox-wrapper-3 design:
      OFF → gray track + white knob
      ON  → purple track + purple knob slides right
    The widget emits the same stateChanged signal as QCheckBox.
    """
    _TRACK_W  = 40
    _TRACK_H  = 20
    _KNOB_D   = 18          # knob diameter
    _PADDING  = 1           # knob inset from track edge

    # colours
    _OFF_TRACK  = QColor("#9A9999")
    _ON_TRACK   = QColor("#f28090")  # light red track
    _OFF_KNOB   = QColor("#FFFFFF")
    _ON_KNOB    = QColor("#FA2D48")  # accent red knob
    _LABEL_COL  = QColor("#111111")

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._anim_val = 0.0        # 0.0 = off, 1.0 = on
        self._timer = None
        self._direction = 0

        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QCheckBox{spacing:10px;font-size:13px;color:#111111;"
            "background:transparent;border:none;}"
            "QCheckBox::indicator{width:0px;height:0px;}"   # hide native indicator
        )

        self.stateChanged.connect(self._on_state)

    # ── animation timer ───────────────────────────────────
    def _on_state(self, state):
        target = 1.0 if self.isChecked() else 0.0
        self._direction = 1 if target > self._anim_val else -1
        if self._timer is None:
            from PyQt6.QtCore import QTimer
            self._timer = QTimer(self)
            self._timer.setInterval(12)
            self._timer.timeout.connect(self._step)
        self._timer.start()

    def _step(self):
        step = 0.08
        if self._direction > 0:
            self._anim_val = min(1.0, self._anim_val + step)
        else:
            self._anim_val = max(0.0, self._anim_val - step)
        self.update()
        target = 1.0 if self.isChecked() else 0.0
        if abs(self._anim_val - target) < 0.01:
            self._anim_val = target
            self._timer.stop()

    # ── size hint ─────────────────────────────────────────
    def sizeHint(self):
        from PyQt6.QtCore import QSize
        fm = self.fontMetrics()
        txt_w = fm.horizontalAdvance(self.text()) if self.text() else 0
        spacing = 10 if self.text() else 0
        return QSize(
            self._TRACK_W + spacing + txt_w + 4,
            max(self._TRACK_H + 4, fm.height() + 4)
        )

    # ── paint ─────────────────────────────────────────────
    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont as GFont
        from PyQt6.QtCore import QRectF, Qt as Qt2

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        tw = self._TRACK_W
        th = self._TRACK_H
        kd = self._KNOB_D
        pad = self._PADDING
        t   = self._anim_val

        # vertical centre
        cy = self.height() / 2

        # ── track ─────────────────────────────────────────
        track_r = QRectF(0, cy - th/2, tw, th)
        track_col = QColor(
            int(self._OFF_TRACK.red()   + t*(self._ON_TRACK.red()   - self._OFF_TRACK.red())),
            int(self._OFF_TRACK.green() + t*(self._ON_TRACK.green() - self._OFF_TRACK.green())),
            int(self._OFF_TRACK.blue()  + t*(self._ON_TRACK.blue()  - self._OFF_TRACK.blue())),
        )
        p.setPen(Qt2.PenStyle.NoPen)
        p.setBrush(QBrush(track_col))
        p.drawRoundedRect(track_r, th/2, th/2)

        # ── knob ──────────────────────────────────────────
        travel  = tw - kd - pad*2
        knob_x  = pad + t * travel
        knob_y  = cy - kd/2
        knob_r  = QRectF(knob_x, knob_y, kd, kd)

        knob_col = QColor(
            int(self._OFF_KNOB.red()   + t*(self._ON_KNOB.red()   - self._OFF_KNOB.red())),
            int(self._OFF_KNOB.green() + t*(self._ON_KNOB.green() - self._OFF_KNOB.green())),
            int(self._OFF_KNOB.blue()  + t*(self._ON_KNOB.blue()  - self._OFF_KNOB.blue())),
        )
        # shadow
        p.setPen(Qt2.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 30)))
        p.drawEllipse(knob_r.adjusted(1, 2, 1, 2))
        # knob face
        p.setBrush(QBrush(knob_col))
        p.drawEllipse(knob_r)

        # ── label text ────────────────────────────────────
        if self.text():
            p.setPen(QPen(self._LABEL_COL))
            fnt = GFont(); fnt.setPointSize(10)
            p.setFont(fnt)
            text_x = tw + 10
            p.drawText(
                QRectF(text_x, 0, self.width() - text_x, self.height()),
                Qt2.AlignmentFlag.AlignVCenter | Qt2.AlignmentFlag.AlignLeft,
                self.text()
            )

        p.end()

_NO_ARROW = (
    "QDoubleSpinBox,QSpinBox{"
    "border:1.5px solid #d2d2d7;border-radius:8px;"
    "border:1.5px solid #d2d2d7;border-radius:8px;"
    "padding:6px 10px;font-size:13px;background:#ffffff;"
    "color:#000000;min-height:38px;max-height:38px;height:38px;}"
    "QDoubleSpinBox:hover,QSpinBox:hover{border:1.5px solid #1a73e8;}"
    "QDoubleSpinBox:focus,QSpinBox:focus{border:2px solid #FA2D48;background:#FFF8F9;}"
    "QDoubleSpinBox::up-button,QDoubleSpinBox::down-button,"
    "QSpinBox::up-button,QSpinBox::down-button{"
    "width:0;height:0;border:none;background:transparent;image:none;}"
    "QDoubleSpinBox::up-arrow,QDoubleSpinBox::down-arrow,"
    "QSpinBox::up-arrow,QSpinBox::down-arrow{width:0;height:0;image:none;}"
)

def price_spin():
    s = QDoubleSpinBox()
    s.setRange(0, 9999999); s.setDecimals(2); s.setPrefix("\u20b9 ")
    s.setFixedHeight(FORM_FIELD_HEIGHT)
    s.setStyleSheet(_NO_ARROW)
    return s

def _spin(min_v=0, max_v=9999999, val=0, suffix=""):
    s = QSpinBox()
    s.setRange(min_v, max_v); s.setValue(val)
    if suffix: s.setSuffix(suffix)
    s.setFixedHeight(FORM_FIELD_HEIGHT)
    s.setStyleSheet(_NO_ARROW)
    return s

def _dspin(min_v=0.0, max_v=9999999.0, val=0.0, dec=2, suffix="", prefix=""):
    s = QDoubleSpinBox()
    s.setRange(min_v, max_v); s.setValue(val); s.setDecimals(dec)
    if suffix: s.setSuffix(suffix)
    if prefix: s.setPrefix(prefix)
    s.setFixedHeight(FORM_FIELD_HEIGHT)
    s.setStyleSheet(_NO_ARROW)
    return s


def mini_table(cols, height=130):
    t = QTableWidget()
    t.setColumnCount(len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setVisible(False)
    t.setFixedHeight(height)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setStyleSheet(f"""
        QTableWidget{{background:{C['bg_white']};border:1px solid {C['border']};
            border-radius:8px;font-size:12px;}}
        QHeaderView::section{{background:{C['bg_light']};font-weight:700;padding:7px;
            border:none;border-bottom:1px solid {C['border']};color:{C['text2']};font-size:11px;}}
        QTableWidget::item{{padding:5px 8px;color:{C['text']};}}
        QTableWidget::item:selected{{background:{C['accent_tint2']};color:{C['text']};}}
    """)
    return t


# ─────────────────────────────────────────────────────────────
#  GRADIENT BUTTON
# ─────────────────────────────────────────────────────────────
class _GBtn(QPushButton):
    _G = {
        "primary": (C["accent"],   C["accent_dark"]),
        "ghost":   ("transparent", "transparent"),
        "success": (C["success"],  C["success_dark"]),
        "warning": ("#e67e22",     "#ca6f1e"),
        "blue":    (C["blue"],     C["blue_dark"]),
        "danger":  ("#ef4444",     "#dc2626"),
    }

    def __init__(self, text, v="primary", parent=None):
        super().__init__(text, parent)
        c1, c2 = self._G.get(v, self._G["primary"])
        if v == "ghost":
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{C['text2']};
                    border:1.5px solid {C['border']}; border-radius:10px;
                    font-size:13px; font-weight:600; padding:9px 20px;
                }}
                QPushButton:hover {{ background:{C['hover_bg']}; color:{C['text']}; }}
                QPushButton:pressed {{ opacity:0.8; }}
            """)
        elif v == "blue_ghost":
            self.setStyleSheet(f"""
                QPushButton {{
                    background:{C['blue_tint']}; color:{C['blue']};
                    border:1.5px solid {C['blue']}; border-radius:8px;
                    font-size:12px; font-weight:600; padding:6px 14px;
                }}
                QPushButton:hover {{ background:{C['blue']}; color:white; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c1},stop:1 {c2});
                    border:none; border-radius:10px; color:white;
                    font-size:13px; font-weight:700; padding:9px 22px;
                    letter-spacing:0.3px;
                }}
                QPushButton:hover {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c2},stop:1 {c1});
                }}
                QPushButton:pressed {{ opacity:0.8; }}
                QPushButton:disabled {{ background:{C['border']}; color:{C['text3']}; }}
            """)
        self.setFont(_F(13, bold=True))
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# ─────────────────────────────────────────────────────────────
#  STOCK ADJUSTMENT DIALOG
# ─────────────────────────────────────────────────────────────
class StockAdjDialog(QDialog):
    def __init__(self, db_name, product_code, product_name, current_stock, user="Admin",
                 parent=None, track_batch=False, track_expiry=False, track_mfg=False):
        super().__init__(parent)
        self.db_name = db_name; self.product_code = product_code; self.user = user
        self.product_name = product_name; self.current_stock = current_stock
        self.track_batch = bool(track_batch)
        self.track_expiry = bool(track_expiry)
        self.track_mfg = bool(track_mfg)
        self.setWindowTitle(f"Stock Adjustment — {product_name}")
        self.setMinimumWidth(480)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(
            f"QDialog{{background:#ffffff;border-radius:14px;}}" + FIELD_SS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────
        top = QFrame()
        top.setStyleSheet("background:#f5f5f7;border-bottom:1px solid #e0e0e5;border-radius:0px;")
        top_lay = QHBoxLayout(top); top_lay.setContentsMargins(20, 14, 20, 14)
        icon_lbl = QLabel("📦"); icon_lbl.setStyleSheet("font-size:22px;background:transparent;border:none;")
        title_lbl = QLabel("Stock Adjustment")
        title_lbl.setFont(_F(15, bold=True))
        title_lbl.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
        top_lay.addWidget(icon_lbl); top_lay.addWidget(title_lbl); top_lay.addStretch()
        root.addWidget(top)

        # ── Body ──────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet("background:#ffffff;")
        lay = QVBoxLayout(body); lay.setContentsMargins(24, 18, 24, 18); lay.setSpacing(14)

        # Current stock pill
        stock_pill = QLabel(f"  Current Stock: <b>{current_stock} units</b> — {product_name}  ")
        stock_pill.setTextFormat(Qt.TextFormat.RichText)
        stock_pill.setStyleSheet(
            f"font-size:12px;color:{C['text2']};background:{C['bg_light']};"
            f"border:1px solid {C['border']};border-radius:8px;padding:6px 10px;")
        lay.addWidget(stock_pill)

        # Adjustment type
        _lbl = QLabel("Adjustment Type"); _lbl.setStyleSheet(LABEL_SS)
        lay.addWidget(_lbl)
        self.adj_type = QComboBox()
        self.adj_type.addItems([
            "IN — Stock Received",
            "OUT — Damaged / Expired",
            "OUT — Return to Supplier",
            "OUT — Lost / Theft",
            "IN — Manual Correction",
            "OUT — Manual Correction",
        ])
        self.adj_type.setFixedHeight(38)
        _apply_combo_delegate(self.adj_type)
        lay.addWidget(self.adj_type)

        # Qty + Reason side by side
        row1 = QHBoxLayout(); row1.setSpacing(12)
        qty_col = QVBoxLayout(); qty_col.setSpacing(4)
        qty_col.addWidget(QLabel("Quantity", styleSheet=LABEL_SS))
        self.qty_spin = QSpinBox(); self.qty_spin.setRange(1, 999999)
        self.qty_spin.setFixedHeight(38); self.qty_spin.setStyleSheet(_NO_ARROW)
        qty_col.addWidget(self.qty_spin)
        reason_col = QVBoxLayout(); reason_col.setSpacing(4)
        reason_col.addWidget(QLabel("Reason", styleSheet=LABEL_SS))
        self.reason = QLineEdit(); self.reason.setPlaceholderText("e.g. Supplier delivery, breakage…")
        self.reason.setFixedHeight(38)
        reason_col.addWidget(self.reason)
        row1.addLayout(qty_col); row1.addLayout(reason_col, 2)
        lay.addLayout(row1)

        # ── Batch section (shown only for IN — Stock Received) ──
        self._batch_frame = QFrame()
        self._batch_frame.setStyleSheet(
            f"QFrame{{background:{C['bg_light']};border:1px solid {C['border']};"
            f"border-radius:10px;}}")
        bf_lay = QVBoxLayout(self._batch_frame)
        bf_lay.setContentsMargins(14, 12, 14, 12); bf_lay.setSpacing(10)

        batch_title = QLabel("🏷️  New Batch Details")
        batch_title.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{C['section_hdr']};"
            f"background:transparent;border:none;")
        bf_lay.addWidget(batch_title)

        batch_note = QLabel(
            "Existing stock keeps its original batch & expiry. "
            "New stock will be tracked under this batch separately.")
        batch_note.setWordWrap(True)
        batch_note.setStyleSheet(
            f"font-size:11px;color:{C['text3']};background:transparent;border:none;")
        bf_lay.addWidget(batch_note)

        b_row1 = QHBoxLayout(); b_row1.setSpacing(12)
        bn_col = QVBoxLayout(); bn_col.setSpacing(4)
        bn_col.addWidget(QLabel("Batch Number", styleSheet=LABEL_SS))
        self.batch = QLineEdit(); self.batch.setPlaceholderText("e.g. B2024-001")
        self.batch.setFixedHeight(38)
        self.batch.setEnabled(self.track_batch)
        if not self.track_batch:
            self.batch.setPlaceholderText("Enable batch tracking on product to use this")
        bn_col.addWidget(self.batch)
        exp_col = QVBoxLayout(); exp_col.setSpacing(4)
        exp_col.addWidget(QLabel("Expiry Date", styleSheet=LABEL_SS))
        self.f_exp = QDateEdit(); self.f_exp.setCalendarPopup(True)
        self.f_exp.setDate(QDate.currentDate().addYears(1))
        self.f_exp.setDisplayFormat("dd-MM-yyyy"); self.f_exp.setFixedHeight(38)
        self.f_exp.setEnabled(self.track_expiry)
        exp_col.addWidget(self.f_exp)
        b_row1.addLayout(bn_col); b_row1.addLayout(exp_col)
        bf_lay.addLayout(b_row1)

        b_row2 = QHBoxLayout(); b_row2.setSpacing(12)
        mfg_col = QVBoxLayout(); mfg_col.setSpacing(4)
        mfg_col.addWidget(QLabel("Mfg Date", styleSheet=LABEL_SS))
        self.f_mfg = QDateEdit(); self.f_mfg.setCalendarPopup(True)
        self.f_mfg.setDate(QDate.currentDate())
        self.f_mfg.setDisplayFormat("dd-MM-yyyy"); self.f_mfg.setFixedHeight(38)
        self.f_mfg.setEnabled(self.track_mfg)
        mfg_col.addWidget(self.f_mfg)
        pp_col = QVBoxLayout(); pp_col.setSpacing(4)
        pp_col.addWidget(QLabel("Purchase Price", styleSheet=LABEL_SS))
        self.f_pp = QDoubleSpinBox(); self.f_pp.setRange(0, 9999999)
        self.f_pp.setPrefix("₹ "); self.f_pp.setFixedHeight(38)
        self.f_pp.setStyleSheet(_NO_ARROW)
        pp_col.addWidget(self.f_pp)
        b_row2.addLayout(mfg_col); b_row2.addLayout(pp_col)
        bf_lay.addLayout(b_row2)
        lay.addWidget(self._batch_frame)

        # Notes
        notes_lbl = QLabel("Notes (optional)"); notes_lbl.setStyleSheet(LABEL_SS)
        lay.addWidget(notes_lbl)
        self.note = QLineEdit(); self.note.setPlaceholderText("Additional notes…")
        self.note.setFixedHeight(38)
        lay.addWidget(self.note)

        # ── Buttons ───────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C['border']};border:none;max-height:1px;margin-top:4px;")
        lay.addWidget(sep)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self._ok_btn = QPushButton("✅  Apply Adjustment")
        self._ok_btn.setFixedHeight(42)
        self._ok_btn.setStyleSheet(f"""
            QPushButton{{background:{C['success']};color:white;border:none;
            border-radius:10px;font-size:13px;font-weight:700;}}
            QPushButton:hover{{background:#1e8a3c;}}
        """)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(42)
        cancel.setStyleSheet(f"""
            QPushButton{{background:{C['bg_light']};color:{C['text']};
            border:1px solid {C['border']};border-radius:10px;font-size:13px;font-weight:600;}}
            QPushButton:hover{{background:#e8e8ed;}}
        """)
        btn_row.addWidget(self._ok_btn, 2); btn_row.addWidget(cancel, 1)
        lay.addLayout(btn_row)

        root.addWidget(body)

        # Wire type change → show/hide batch frame
        self.adj_type.currentTextChanged.connect(self._on_type_changed)
        self._ok_btn.clicked.connect(self._apply)
        cancel.clicked.connect(self.reject)
        self._on_type_changed(self.adj_type.currentText())
        self.adjustSize()

    def _on_type_changed(self, text):
        is_in_received = text == "IN — Stock Received"
        self._batch_frame.setVisible(
            is_in_received and (self.track_batch or self.track_expiry or self.track_mfg)
        )
        self._ok_btn.setText(
            "✅  Receive Stock" if is_in_received else "✅  Apply Adjustment")
        self.adjustSize()

    def _apply(self):
        adj_raw  = self.adj_type.currentText()
        adj_type = "IN" if adj_raw.startswith("IN") else "OUT"
        qty      = self.qty_spin.value()
        reason   = self.reason.text().strip() or adj_raw
        notes    = self.note.text().strip()

        if adj_raw == "IN — Stock Received":
            # Save as a proper new batch — does NOT touch existing batches
            bn = self.batch.text().strip()
            if self.track_batch and not bn:
                QMessageBox.warning(self, "Batch Required",
                    "Please enter a Batch Number for new stock being received.")
                return
            if not (self.track_batch or self.track_expiry or self.track_mfg):
                save_stock_adjustment(
                    self.db_name, self.product_code, "IN", qty,
                    reason, "", notes, self.user)
                QMessageBox.information(self, "Stock Received",
                    f"âœ…  {qty} units received.",
                    QMessageBox.StandardButton.Ok)
                self.accept()
                return
            if not bn:
                bn = f"RCV{datetime.now().strftime('%Y%m%d%H%M%S')}"
            save_batch(
                self.db_name, self.product_code, bn, qty,
                self.f_mfg.date().toString("yyyy-MM-dd") if self.track_mfg else "",
                self.f_exp.date().toString("yyyy-MM-dd") if self.track_expiry else "",
                self.f_pp.value(),
                "",   # supplier (can extend later)
                self.user
            )
            QMessageBox.information(self, "Stock Received",
                f"✅  {qty} units received under Batch <b>{bn}</b>.<br>"
                f"Existing stock batches are unchanged.",
                QMessageBox.StandardButton.Ok)
        else:
            save_stock_adjustment(
                self.db_name, self.product_code, adj_type, qty,
                reason, "", notes, self.user)
            QMessageBox.information(self, "Done",
                f"Stock {'increased' if adj_type == 'IN' else 'reduced'} by {qty} units.")
        self.accept()


# ─────────────────────────────────────────────────────────────
#  BATCH ADD DIALOG
# ─────────────────────────────────────────────────────────────
class BatchAddDialog(QDialog):
    def __init__(self, db_name, product_code, user="Admin", parent=None):
        super().__init__(parent)
        self.db_name = db_name; self.product_code = product_code; self.user = user
        self.setWindowTitle("Add / Receive Batch")
        self.setFixedSize(460, 360)
        self.setStyleSheet(f"QDialog{{background:{C['bg_light']};border-radius:12px;}}" + FIELD_SS)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(12)

        hdr = QLabel("📦  Add / Receive Batch")
        hdr.setFont(_F(15, bold=True))
        hdr.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
        lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C['border']};border:none;max-height:1px;")
        lay.addWidget(sep)

        grid = QGridLayout(); grid.setSpacing(8)
        self.f_batch = QLineEdit(); self.f_batch.setPlaceholderText("e.g. B2024-001")
        self.f_qty   = QSpinBox(); self.f_qty.setRange(1, 999999)
        self.f_qty.setFixedHeight(38)
        self.f_qty.setStyleSheet(_NO_ARROW)
        self.f_mfg   = QDateEdit(); self.f_mfg.setCalendarPopup(True)
        self.f_mfg.setDate(QDate.currentDate()); self.f_mfg.setDisplayFormat("dd-MM-yyyy")
        self.f_exp   = QDateEdit(); self.f_exp.setCalendarPopup(True)
        self.f_exp.setDate(QDate.currentDate().addYears(1)); self.f_exp.setDisplayFormat("dd-MM-yyyy")
        self.f_price = QDoubleSpinBox(); self.f_price.setRange(0, 999999); self.f_price.setPrefix("₹ ")
        self.f_price.setFixedHeight(38)
        self.f_price.setStyleSheet(_NO_ARROW)
        self.f_sup   = QLineEdit(); self.f_sup.setPlaceholderText("Supplier name")

        add_field(grid, 0, 0, "Batch No",       self.f_batch, required=True)
        add_field(grid, 0, 2, "Qty Received",   self.f_qty)
        add_field(grid, 1, 0, "Mfg Date",       self.f_mfg)
        add_field(grid, 1, 2, "Expiry Date",    self.f_exp)
        add_field(grid, 2, 0, "Purchase Price", self.f_price)
        add_field(grid, 2, 2, "Supplier",       self.f_sup)
        lay.addLayout(grid)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        ok = _GBtn("💾  Save Batch", "success")
        ok.setFixedHeight(38); ok.clicked.connect(self._save)
        cancel = _GBtn("Cancel", "ghost")
        cancel.setFixedHeight(38); cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        lay.addLayout(btn_row)

    def _save(self):
        bn = self.f_batch.text().strip()
        if not bn:
            QMessageBox.warning(self, "Error", "Batch number is required.")
            return
        save_batch(self.db_name, self.product_code, bn,
                   self.f_qty.value(),
                   self.f_mfg.date().toString("yyyy-MM-dd"),
                   self.f_exp.date().toString("yyyy-MM-dd"),
                   self.f_price.value(), self.f_sup.text().strip(), self.user)
        QMessageBox.information(self, "Done", f"Batch {bn} saved and stock updated.")
        self.accept()


# ─────────────────────────────────────────────────────────────
#  OVERLAY PANEL  (full-size, fades in over the list with scrim)
# ─────────────────────────────────────────────────────────────
class _SlidePanel(QWidget):
    closed = pyqtSignal()
    _DURATION = 220

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._open = False

        self._scrim = QWidget(parent)
        self._scrim.setStyleSheet("background:rgba(0,0,0,160);")
        self._scrim.hide()

        self.setStyleSheet(f"background:{C['bg_light']};")
        self.hide()
        self.resize_to_parent()

    def resize_to_parent(self):
        p = self.parent()
        if not p: return
        self.setGeometry(0, 0, p.width(), p.height())
        self._scrim.setGeometry(0, 0, p.width(), p.height())

    def slide_in(self):
        if self._open: return
        self._open = True
        self.resize_to_parent()

        self._scrim.show(); self._scrim.raise_()
        self.show(); self.raise_()

        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setStartValue(0.0); anim.setEndValue(1.0)
        anim.setDuration(self._DURATION)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        seff = QGraphicsOpacityEffect(self._scrim)
        self._scrim.setGraphicsEffect(seff)
        sanim = QPropertyAnimation(seff, b"opacity", self)
        sanim.setStartValue(0.0); sanim.setEndValue(1.0)
        sanim.setDuration(self._DURATION)
        sanim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def slide_out(self):
        if not self._open: return
        self._open = False

        eff = self.graphicsEffect()
        if not isinstance(eff, QGraphicsOpacityEffect):
            eff = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(eff)

        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setStartValue(1.0); anim.setEndValue(0.0)
        anim.setDuration(self._DURATION)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self._on_closed)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        seff = self._scrim.graphicsEffect()
        if isinstance(seff, QGraphicsOpacityEffect):
            sa = QPropertyAnimation(seff, b"opacity", self)
            sa.setStartValue(1.0); sa.setEndValue(0.0)
            sa.setDuration(self._DURATION)
            sa.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_closed(self):
        self.hide(); self._scrim.hide()
        self.closed.emit()

    def is_open(self): return self._open


# ─────────────────────────────────────────────────────────────
#  PRODUCT FORM WIDGET  (7 tabs)
# ─────────────────────────────────────────────────────────────
class ProductFormWidget(QWidget):

    saved  = pyqtSignal(str)
    cancel = pyqtSignal()

    _CB_VIEW_SS = (
        "QListView, QAbstractItemView { background:#FFFFFF; color:#000000; }"
        "QListView::item, QAbstractItemView::item { background:#FFFFFF; color:#000000;"
        "  min-height:32px; padding:4px 10px; border:none; }"
        "QListView::item:hover, QAbstractItemView::item:hover { background:#FA2D48; color:#FFFFFF; }"
        "QListView::item:selected, QAbstractItemView::item:selected { background:#1A73E8; color:#FFFFFF; }"
    )

    def __init__(self, db_name, current_user="Admin", parent=None):
        super().__init__(parent)
        self.db_name      = db_name
        self.current_user = current_user
        self.edit_code    = None
        self.prod         = {}
        self._image_blob  = b""

        self.setStyleSheet(f"background:{C['bg_light']};" + FIELD_SS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── Top bar ────────────────────────────────────────
        top = QFrame(); top.setFixedHeight(58)
        top.setStyleSheet(
            "background:#f5f5f7;"
            "border-bottom:1px solid #d2d2d7;"
        )
        tl = QHBoxLayout(top); tl.setContentsMargins(20, 0, 20, 0); tl.setSpacing(12)

        self._btn_back = _GBtn("← Back", "ghost")
        self._btn_back.setFixedSize(90, 36)
        self._btn_back.clicked.connect(self.cancel.emit)

        self._title_lbl = QLabel("Add Product")
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(_F(15, bold=True))
        self._title_lbl.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")

        self._btn_save = _GBtn("💾  Save Product")
        self._btn_save.setFixedHeight(36); self._btn_save.setMinimumWidth(150)
        self._btn_save.clicked.connect(self._save)

        tl.addWidget(self._btn_back); tl.addStretch()
        tl.addWidget(self._title_lbl); tl.addStretch()
        tl.addWidget(self._btn_save)
        root.addWidget(top)

        # ── Tabs ───────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_SS)
        self.tabs.tabBar().setExpanding(True)

        self._build_tab_basic()
        self._build_tab_pricing()
        self._build_tab_inventory()
        self._build_tab_supplier()
        self._build_tab_compliance()
        self._build_tab_history()
        self._build_tab_audit()

        self._no_wheel_filter = _NoWheelValueFilter(self)
        for field_type in (QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit):
            for field in self.findChildren(field_type):
                field.installEventFilter(self._no_wheel_filter)

        # Fix combo delegate for all combos in form
        for cb in self.findChildren(QComboBox):
            _apply_combo_delegate(cb)
            cb.view().setStyleSheet(self._CB_VIEW_SS)

        # Enforce checkbox styling on every QCheckBox — runs after all tabs built
        # so any per-widget setStyleSheet() that bypassed the global rules is overwritten
        self._apply_chk_ss()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:#f5f5f7;")
        wrap = QWidget(); wrap.setStyleSheet("background:#f5f5f7;")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(20, 20, 20, 20); wl.setSpacing(0)
        wl.addWidget(self.tabs)
        scroll.setWidget(wrap)
        root.addWidget(scroll, 1)

    # ── Checkbox stylesheet enforcer ──────────────────────

    def _apply_chk_ss(self):
        """Sync _anim_val on any ToggleSwitch that was pre-checked at build time."""
        for tog in self.findChildren(ToggleSwitch):
            if tog.isChecked():
                tog._anim_val = 1.0
            tog.update()

    # ── TAB 1: BASIC INFO ─────────────────────────────────

    def _build_tab_basic(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

        sec, g = make_section("Basic Detail", "🔖")

        # widgets
        self.f_item_code = QLineEdit(); self.f_item_code.setPlaceholderText("Auto-generated product no")
        self.f_item_code.setReadOnly(True)
        self.f_sku     = QLineEdit(); self.f_sku.setPlaceholderText("Internal SKU")
        self.f_barcode = QLineEdit(); self.f_barcode.setPlaceholderText("13-digit EAN barcode")
        self.f_auto_barcode = ToggleSwitch("Auto-generate EAN-13")
        self.f_auto_barcode.stateChanged.connect(self._toggle_barcode)
        self.f_name    = QLineEdit(); self.f_name.setPlaceholderText("Full product name")
        self.f_alias   = QLineEdit(); self.f_alias.setPlaceholderText("Alt names, comma-separated")
        self.f_use_alias_bill = ToggleSwitch("Use this name in billing")
        self.f_use_alias_bill.setToolTip("When checked, the first alias is used as the product name on invoices")
        self.f_prod_type = QComboBox()
        self.f_prod_type.addItems(["Goods", "Service", "Digital", "Composite"])

        # layout
        r = 0
        add_field(g, r, 0, "Product No", self.f_item_code, required=True)
        r += 1
        add_field(g, r, 0, "SKU", self.f_sku)
        add_field(g, r, 2, "Barcode / EAN", self.f_barcode, required=True)
        r += 1
        g.addWidget(self.f_auto_barcode, r, 3, 1, 1,
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        r += 1
        add_field(g, r, 0, "Product Name", self.f_name, required=True, span=2)
        r += 1
        add_field(g, r, 0, "Alias Names", self.f_alias,
                  hint="Comma-separated · used in billing search", span=2)
        r += 1
        g.addWidget(self.f_use_alias_bill, r, 1, 1, 3,
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        r += 1
        add_field(g, r, 0, "Product Type", self.f_prod_type)
        lay.addWidget(sec)

        # Image
        sec_img, g_img = make_section("Product Image", "🖼️")
        img_row = QHBoxLayout()
        self.img_label = QLabel("No Image")
        self.img_label.setFixedSize(100, 100); self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet(
            f"border:2px dashed {C['border']};border-radius:10px;color:{C['text3']};font-size:12px;")
        img_row.addWidget(self.img_label)
        img_btns = QVBoxLayout(); img_btns.setSpacing(6)
        btn_up = _GBtn("📁  Upload Image", "blue")
        btn_up.setFixedHeight(32); btn_up.clicked.connect(self._upload_image)
        btn_rm = _GBtn("🗑  Remove", "danger")
        btn_rm.setFixedHeight(32); btn_rm.clicked.connect(self._clear_image)
        img_btns.addWidget(btn_up); img_btns.addWidget(btn_rm); img_btns.addStretch()
        img_row.addLayout(img_btns); img_row.addStretch()
        g_img.addLayout(img_row, 0, 0, 1, 4)
        lay.addWidget(sec_img)

        # Classification
        sec2, g2 = make_section("Classification & Properties", "🗂️")

        self.f_product_group = QLineEdit()
        self.f_product_group.setPlaceholderText("e.g. Menswear")

        self.f_category = QComboBox(); self.f_category.setEditable(True)
        self.f_category.addItems([
            "",
            "Shirts", "T-Shirts", "Formal Shirts", "Casual Shirts", "Ethnic Shirts",
            "Trousers", "Formal Trousers", "Casual Trousers", "Jeans", "Cargos",
            "Suits & Blazers", "Kurta & Pyjama", "Sherwanis", "Dhoti & Veshti",
            "Innerwear & Socks", "Sportswear & Track Suits",
            "Fabric & Cloth Pieces", "Accessories & Belts",
        ])

        self.f_sub_cat = QLineEdit(); self.f_sub_cat.setPlaceholderText("e.g. Slim Fit")
        self.f_brand   = QLineEdit(); self.f_brand.setPlaceholderText("e.g. Raymond")

        self.f_manufacturer = QLineEdit()
        self.f_manufacturer.setPlaceholderText("e.g. Raymond Ltd")
        self.f_country = QLineEdit(); self.f_country.setText("India"); self.f_country.hide()

        self.f_unit = QComboBox(); self.f_unit.setEditable(True)
        self.f_unit.addItems([
            "Pcs", "Meter", "Set", "Pair", "Dozen",
            "Box", "Pack", "Nos", "Roll",
        ])

        self.f_pack_size = QSpinBox()
        self.f_pack_size.setFixedHeight(38)
        self.f_pack_size.setStyleSheet(_NO_ARROW)
        self.f_pack_size.setRange(1, 99999); self.f_pack_size.setValue(1)

        # hidden stubs so _collect / _save_fields still work
        self.f_meter      = QLineEdit(); self.f_meter.hide()
        self.f_shelf_life = QSpinBox();  self.f_shelf_life.hide()
        self.f_shelf_life.setFixedHeight(38)
        self.f_shelf_life.setStyleSheet(_NO_ARROW)
        self.f_storage    = QComboBox(); self.f_storage.hide()
        self.f_tags       = QLineEdit(); self.f_tags.hide()

        r2 = 0
        add_field(g2, r2, 0, "Product Group", self.f_product_group)
        add_field(g2, r2, 2, "Category",      self.f_category)
        r2 += 1
        add_field(g2, r2, 0, "Sub-category",  self.f_sub_cat)
        add_field(g2, r2, 2, "Brand",         self.f_brand)
        r2 += 1
        add_field(g2, r2, 0, "Manufacturer",  self.f_manufacturer)
        r2 += 1
        add_field(g2, r2, 0, "Unit",          self.f_unit,
                  hint="Use ‘Meter’ for fabric — billing will calculate by length")
        add_field(g2, r2, 2, "Pack Size",     self.f_pack_size)
        lay.addWidget(sec2)

        # Description (hidden stubs — keep _collect/_save_fields working)
        self.f_desc  = QTextEdit(); self.f_desc.hide()
        self.f_notes = QTextEdit(); self.f_notes.hide()

        # Status only
        sec3, g3 = make_section("Status", "📋")
        self.f_status = QComboBox()
        self.f_status.addItems(["Active", "Draft", "Inactive", "Discontinued"])
        add_field(g3, 0, 0, "Status", self.f_status, required=True)
        lay.addWidget(sec3)
        lay.addStretch()
        self.tabs.addTab(page, "BASIC DETAIL")

    # ── TAB 2: PRICING & TAX ──────────────────────────────

    def _build_tab_pricing(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        outer = QVBoxLayout(page); outer.setContentsMargins(0, 16, 0, 0); outer.setSpacing(0)

        # ── Two-column master layout ──────────────────────────
        cols = QHBoxLayout(); cols.setContentsMargins(0, 0, 0, 0); cols.setSpacing(16)

        # Left column — fields
        left_w = QWidget(); left_w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(left_w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)

        # Right column — live GST breakdown
        right_w = QWidget(); right_w.setFixedWidth(320); right_w.setStyleSheet("background:transparent;")
        right_lay = QVBoxLayout(right_w); right_lay.setContentsMargins(0, 0, 0, 0); right_lay.setSpacing(12)

        cols.addWidget(left_w, 1)
        cols.addWidget(right_w, 0)
        outer.addLayout(cols)

        # ── FIELD WIDGETS ────────────────────────────────────
        self.f_mrp            = price_spin()
        self.f_purchase_price = price_spin()
        self.f_purchase_gst   = QComboBox()
        self.f_purchase_gst.addItems(["0%","5%","12%","18%","28%"])
        self.lbl_purchase_actual = ro_label("₹ 0.00")
        self.f_selling_price  = price_spin()

        self.f_discount_pct = QDoubleSpinBox()
        self.f_discount_pct.setFixedHeight(38)
        self.f_discount_pct.setStyleSheet(_NO_ARROW)
        self.f_discount_pct.setRange(0, 100); self.f_discount_pct.setDecimals(2)
        self.f_discount_pct.setSuffix(" %")
        self.f_discount_val = QDoubleSpinBox()
        self.f_discount_val.setFixedHeight(38)
        self.f_discount_val.setStyleSheet(_NO_ARROW)
        self.f_discount_val.setRange(0, 999999); self.f_discount_val.setDecimals(2)
        self.f_discount_val.setPrefix("₹ ")

        self.f_margin = QDoubleSpinBox()
        self.f_margin.setRange(-999, 9999); self.f_margin.setDecimals(1)
        self.f_margin.setSuffix(" %"); self.f_margin.setValue(0.0)
        self.f_margin.setFixedHeight(38)
        self.f_margin.setStyleSheet(_NO_ARROW)
        self.lbl_margin = self.f_margin   # alias so old refs still work
        self.f_profit = QDoubleSpinBox()
        self.f_profit.setRange(-9999999, 9999999); self.f_profit.setDecimals(2)
        self.f_profit.setPrefix("₹ "); self.f_profit.setValue(0.0)
        self.f_profit.setFixedHeight(38)
        self.f_profit.setStyleSheet(_NO_ARROW)
        self.lbl_profit = self.f_profit   # alias so old setText refs still resolve

        # Hidden stubs
        self.f_wholesale_price   = price_spin(); self.f_wholesale_price.hide()
        self.f_dealer_price      = price_spin(); self.f_dealer_price.hide()
        self.f_min_selling_price = price_spin(); self.f_min_selling_price.hide()
        self.lbl_markup          = ro_label("—"); self.lbl_markup.hide()
        self.f_special_price     = price_spin(); self.f_special_price.hide()
        self.f_retail_price      = price_spin(); self.f_retail_price.hide()
        self.f_sp_from = QDateEdit(); self.f_sp_from.hide()
        self.f_sp_to   = QDateEdit(); self.f_sp_to.hide()

        self.f_tax_inclusive = ToggleSwitch("Selling price includes GST  (price already has GST baked in)")
        # f_tax_inclusive is ToggleSwitch — no stylesheet needed

        # GST fields
        self.f_tax_cat = QComboBox()
        self.f_tax_cat.addItems(["Standard", "Nil Rated", "Exempt", "Zero Rated", "Non-GST"])
        self.f_hsn = QLineEdit(); self.f_hsn.setPlaceholderText("e.g. 2202")
        self.f_gst_rate = QComboBox()
        self.f_gst_rate.addItems(["0%","5%","12%","18%","28%"])
        self.f_igst_rate = QComboBox(); self.f_igst_rate.addItems(["0%","5%","12%","18%","28%"]); self.f_igst_rate.hide()
        self.f_tax_type  = QComboBox(); self.f_tax_type.addItems(["CGST + SGST (local)","IGST (interstate)"]); self.f_tax_type.hide()
        self.f_cess_pct  = QDoubleSpinBox(); self.f_cess_pct.hide()
        self.f_cess_pct.setFixedHeight(38)
        self.f_cess_pct.setStyleSheet(_NO_ARROW)
        self.f_tcs       = ToggleSwitch(); self.f_tcs.hide()
        self.f_gst_ex    = QLineEdit(); self.f_gst_ex.hide()
        self.lbl_cgst_rate = ro_label("—")
        self.lbl_sgst_rate = ro_label("—")

        # helper: uniform field height
        FIELD_H = 36
        for w in (self.f_mrp, self.f_purchase_price, self.f_selling_price,
                  self.f_retail_price, self.f_discount_pct, self.f_discount_val,
                  self.lbl_purchase_actual,
                  self.f_purchase_gst, self.f_tax_cat, self.f_hsn,
                  self.f_gst_rate, self.lbl_cgst_rate, self.lbl_sgst_rate):
            w.setFixedHeight(FIELD_H)

        # ── LEFT: Price Tiers section ─────────────────────────
        sec, g = make_section("Price Tiers", "💰")
        g.setHorizontalSpacing(12); g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)
        g.setColumnMinimumWidth(0, 160); g.setColumnMinimumWidth(2, 160)

        r = 0
        add_field(g, r, 0, "MRP",           self.f_mrp,           required=True)
        add_field(g, r, 2, "Purchase Price", self.f_purchase_price, required=True)
        r += 1
        add_field(g, r, 0, "Purchase GST",  self.f_purchase_gst,  hint="GST paid on purchase")
        add_field(g, r, 2, "Actual Cost (incl. GST)", self.lbl_purchase_actual, hint="Auto-calculated")
        r += 1
        add_field(g, r, 0, "Selling Price", self.f_selling_price, required=True)
        add_field(g, r, 2, "GST Rate (CGST+SGST)", self.f_gst_rate, required=True)
        r += 1
        g.addWidget(self.f_tax_inclusive, r, 0, 1, 4,
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        r += 1
        add_field(g, r, 0, "Discount %",     self.f_discount_pct, hint="Enter % → selling price updates")
        add_field(g, r, 2, "Discount Value", self.f_discount_val, hint="Enter ₹ → % updates")
        r += 1
        add_field(g, r, 0, "Margin %",  self.f_margin,
                  hint="Type % → selling price syncs automatically")
        add_field(g, r, 2, "Profit ₹", self.f_profit, hint="Enter ₹ profit → sell price syncs")
        lay.addWidget(sec)

        # ── LEFT: GST & Tax section ───────────────────────────
        sec3, g3 = make_section("GST & Tax", "🧾")
        g3.setHorizontalSpacing(12); g3.setVerticalSpacing(10)
        g3.setColumnStretch(1, 1); g3.setColumnStretch(3, 1)
        g3.setColumnMinimumWidth(0, 160); g3.setColumnMinimumWidth(2, 160)

        r3 = 0
        add_field(g3, r3, 0, "HSN Code", self.f_hsn,
                  hint="Mandatory for GST", required=True)
        add_field(g3, r3, 2, "Tax Category", self.f_tax_cat, required=True)
        r3 += 1
        add_field(g3, r3, 0, "CGST", self.lbl_cgst_rate, hint="Half of GST rate")
        add_field(g3, r3, 2, "SGST", self.lbl_sgst_rate, hint="Half of GST rate")
        r3 += 1
        lay.addWidget(sec3)

        lay.addStretch()

        # ── RIGHT: Live GST Breakdown panel ──────────────────
        self._gst_panel = QFrame()
        self._gst_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._gst_panel.setStyleSheet(
            f"QFrame{{background:{C['blue_tint']};border:1.5px solid #BAE6FD;"
            f"border-radius:12px;}}")
        gp_lay = QVBoxLayout(self._gst_panel)
        gp_lay.setContentsMargins(18, 16, 18, 16); gp_lay.setSpacing(0)

        gp_title = QLabel("📊  Live GST Breakdown")
        gp_title.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['blue']};"
            f"background:transparent;border:none;padding-bottom:10px;")
        gp_lay.addWidget(gp_title)

        # separator
        _sep = QFrame(); _sep.setFrameShape(QFrame.Shape.HLine)
        _sep.setStyleSheet("background:#BAE6FD;border:none;max-height:1px;margin-bottom:10px;")
        gp_lay.addWidget(_sep)

        def _gst_row(label, indent=False):
            row = QHBoxLayout(); row.setContentsMargins(0, 4, 0, 4); row.setSpacing(0)
            prefix = "    " if indent else ""
            lbl = QLabel(prefix + label)
            lbl.setStyleSheet(
                f"font-size:12px;color:{C['text2'] if not indent else C['text3']};"
                f"background:transparent;border:none;")
            val = QLabel("—")
            val.setStyleSheet(
                f"font-size:12px;font-weight:700;color:{C['text']};"
                f"background:transparent;border:none;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl); row.addStretch(); row.addWidget(val)
            return row, val

        row_sp,  self._gst_lbl_sp   = _gst_row("Selling Price")
        row_gp,  self._gst_lbl_pct  = _gst_row("GST Rate")
        row_bp,  self._gst_lbl_base = _gst_row("Base Price (excl. GST)")
        row_cg,  self._gst_lbl_cgst = _gst_row("CGST", indent=True)
        row_sg,  self._gst_lbl_sgst = _gst_row("SGST", indent=True)
        row_ga,  self._gst_lbl_amt  = _gst_row("Total GST")
        row_cp,  self._gst_lbl_cust = _gst_row("Customer Pays")
        for row in [row_sp, row_gp, row_bp, row_cg, row_sg, row_ga, row_cp]:
            gp_lay.addLayout(row)

        # bottom separator + summary message
        _sep2 = QFrame(); _sep2.setFrameShape(QFrame.Shape.HLine)
        _sep2.setStyleSheet("background:#BAE6FD;border:none;max-height:1px;margin-top:8px;")
        gp_lay.addWidget(_sep2)

        self._gst_msg_lbl = QLabel("")
        self._gst_msg_lbl.setWordWrap(True)
        self._gst_msg_lbl.setStyleSheet(
            f"font-size:11px;color:{C['blue']};background:transparent;"
            f"padding-top:8px;border:none;")
        gp_lay.addWidget(self._gst_msg_lbl)
        gp_lay.addStretch()

        right_lay.addWidget(self._gst_panel)
        right_lay.addStretch()

        outer.addStretch()
        self.tabs.addTab(page, "💰  Pricing & Tax")

        # ── Signal wiring ─────────────────────────────────────
        self._du = False   # guard prevents recursive signal loops

        def _actual_cost():
            pp = self.f_purchase_price.value()
            try:
                g = float(self.f_purchase_gst.currentText().replace("%","").strip())
            except Exception:
                g = 0.0
            return round(pp * (1 + g / 100), 2)

        def _sync_profit_margin(sell, actual_pp):
            """Update margin spinner + profit spinner. Always uses purchase+GST as cost."""
            if actual_pp > 0 and sell > 0:
                margin = round((sell - actual_pp) / actual_pp * 100, 1)
                profit = round(sell - actual_pp, 2)
                col_m  = C["success"] if margin >= 0 else C["accent"]
                col_p  = C["success"] if profit >= 0 else C["accent"]
                self.f_margin.blockSignals(True)
                self.f_margin.setValue(margin)
                self.f_margin.setStyleSheet(
                    _NO_ARROW + f"QDoubleSpinBox{{color:{col_m};font-weight:700;}}")
                self.f_margin.blockSignals(False)
                self.lbl_markup.setText(f"{margin:.1f}%")
                self.f_profit.blockSignals(True)
                self.f_profit.setValue(profit)
                self.f_profit.setStyleSheet(
                    _NO_ARROW + f"QDoubleSpinBox{{color:{col_p};font-weight:700;}}")
                self.f_profit.blockSignals(False)
            else:
                self.f_margin.blockSignals(True)
                self.f_margin.setValue(0.0)
                self.f_margin.setStyleSheet(_NO_ARROW)
                self.f_margin.blockSignals(False)
                self.lbl_markup.setText("\u2014")
                self.f_profit.blockSignals(True)
                self.f_profit.setValue(0.0)
                self.f_profit.setStyleSheet(_NO_ARROW)
                self.f_profit.blockSignals(False)

        def on_purchase_changed():
            """Purchase price or GST changed → update actual cost + profit + margin."""
            actual = _actual_cost()
            self.lbl_purchase_actual.setText(f"\u20b9 {actual:.2f}")
            self.lbl_purchase_actual.setStyleSheet(
                f"background:{C['bg_light']};border:1px solid {C['border']};"
                f"border-radius:8px;padding:6px 10px;font-size:13px;"
                f"font-weight:700;color:{C['text']};min-height:38px;")
            _sync_profit_margin(self.f_selling_price.value(), actual)
            self._update_gst_panel()

        def on_mrp_changed():
            """MRP typed → keep discount %, recalc value + sell."""
            if self._du: return
            mrp = self.f_mrp.value()
            if mrp <= 0: return
            self._du = True
            pct = self.f_discount_pct.value()
            val = round(mrp * pct / 100, 2)
            self.f_discount_val.setValue(val)
            self.f_selling_price.setValue(round(mrp - val, 2))
            self._du = False
            _sync_profit_margin(self.f_selling_price.value(), _actual_cost())

        def on_sell_changed():
            """Sell price typed → sync discount%/₹ from MRP; profit/margin from cost."""
            if self._du: return
            mrp = self.f_mrp.value()
            sp  = self.f_selling_price.value()
            self._du = True
            if mrp > 0:
                disc_val = round(max(mrp - sp, 0), 2)
                disc_pct = round(disc_val / mrp * 100, 2)
                self.f_discount_val.setValue(disc_val)
                self.f_discount_pct.setValue(disc_pct)
            self._du = False
            _sync_profit_margin(sp, _actual_cost())
            self._update_gst_panel()

        def on_disc_pct_changed():
            """Discount % typed → sync ₹ value + sell price."""
            if self._du: return
            mrp = self.f_mrp.value()
            if mrp <= 0: return
            self._du = True
            pct = self.f_discount_pct.value()
            val = round(mrp * pct / 100, 2)
            self.f_discount_val.setValue(val)
            self.f_selling_price.setValue(round(mrp - val, 2))
            self._du = False
            _sync_profit_margin(self.f_selling_price.value(), _actual_cost())
            self._update_gst_panel()

        def on_disc_val_changed():
            """Discount ₹ typed → sync % + sell price."""
            if self._du: return
            mrp = self.f_mrp.value()
            if mrp <= 0: return
            self._du = True
            val = self.f_discount_val.value()
            pct = round(val / mrp * 100, 2)
            self.f_discount_pct.setValue(pct)
            self.f_selling_price.setValue(round(max(mrp - val, 0), 2))
            self._du = False
            _sync_profit_margin(self.f_selling_price.value(), _actual_cost())
            self._update_gst_panel()

        def on_margin_changed():
            """Margin % typed → recalc sell from actual cost; sync discount from MRP."""
            if self._du: return
            self._du = True
            actual = _actual_cost()
            margin = self.f_margin.value()
            if actual > 0:
                new_sell = round(actual * (1 + margin / 100), 2)
                self.f_selling_price.setValue(new_sell)
                mrp = self.f_mrp.value()
                if mrp > 0:
                    disc_val = round(max(mrp - new_sell, 0), 2)
                    disc_pct = round(disc_val / mrp * 100, 2)
                    self.f_discount_val.setValue(disc_val)
                    self.f_discount_pct.setValue(disc_pct)
                profit = round(new_sell - actual, 2)
                col_p  = C["success"] if profit >= 0 else C["accent"]
                self.f_profit.blockSignals(True)
                self.f_profit.setValue(profit)
                self.f_profit.setStyleSheet(
                    _NO_ARROW + f"QDoubleSpinBox{{color:{col_p};font-weight:700;}}")
                self.f_profit.blockSignals(False)
            self._du = False
            self._update_gst_panel()

        self.f_purchase_price.valueChanged.connect(on_purchase_changed)
        self.f_purchase_gst.currentTextChanged.connect(on_purchase_changed)
        self.f_mrp.valueChanged.connect(on_mrp_changed)
        self.f_selling_price.valueChanged.connect(on_sell_changed)
        self.f_discount_pct.valueChanged.connect(on_disc_pct_changed)
        self.f_discount_val.valueChanged.connect(on_disc_val_changed)
        def on_profit_changed():
            """Profit ₹ typed → recalc sell = actual_cost + profit; sync discount/margin."""
            if self._du: return
            self._du = True
            actual = _actual_cost()
            profit = self.f_profit.value()
            new_sell = round(actual + profit, 2)
            self.f_selling_price.setValue(new_sell)
            # sync discount from MRP
            mrp = self.f_mrp.value()
            if mrp > 0:
                disc_val = round(max(mrp - new_sell, 0), 2)
                disc_pct = round(disc_val / mrp * 100, 2)
                self.f_discount_val.setValue(disc_val)
                self.f_discount_pct.setValue(disc_pct)
            # sync margin spinner
            if actual > 0:
                margin = round(profit / actual * 100, 1)
                col_m  = C["success"] if margin >= 0 else C["accent"]
                self.f_margin.blockSignals(True)
                self.f_margin.setValue(margin)
                self.f_margin.setStyleSheet(
                    _NO_ARROW + f"QDoubleSpinBox{{color:{col_m};font-weight:700;}}")
                self.f_margin.blockSignals(False)
            self._du = False
            self._update_gst_panel()

        self.f_margin.valueChanged.connect(on_margin_changed)
        self.f_profit.valueChanged.connect(on_profit_changed)
        self.f_gst_rate.currentTextChanged.connect(self._update_gst_panel)
        self.f_tax_inclusive.stateChanged.connect(self._update_gst_panel)
        on_purchase_changed()
        self._update_gst_panel()

    def _update_purchase_actual(self):
        """Kept for _save_fields / _populate compatibility."""
        pp = self.f_purchase_price.value()
        try:
            g = float(self.f_purchase_gst.currentText().replace("%","").strip())
        except Exception:
            g = 0.0
        actual = round(pp * (1 + g / 100), 2)
        self.lbl_purchase_actual.setText(f"\u20b9 {actual:.2f}")
        self.lbl_purchase_actual.setStyleSheet(
            f"background:{C['bg_light']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:6px 10px;font-size:13px;"
            f"font-weight:700;color:{C['text']};min-height:38px;")

    def _update_discount_from_sell(self):
        pass   # logic now inline in on_sell_changed

    def _update_margin(self):
        pass   # logic now in _sync_profit_margin closure

    def _update_gst_panel(self):
        sp        = self.f_selling_price.value()
        gst_str   = self.f_gst_rate.currentText()
        inclusive = self.f_tax_inclusive.isChecked()
        try:
            gst_pct = float(gst_str.replace("%", "").strip())
        except Exception:
            gst_pct = 0.0

        half = gst_pct / 2
        # Update CGST / SGST rate labels in the form
        self.lbl_cgst_rate.setText(f"{half:.1f}%")
        self.lbl_sgst_rate.setText(f"{half:.1f}%")

        if gst_pct == 0:
            self._gst_panel.setStyleSheet(
                f"QFrame{{background:{C['bg_light']};border:1.5px solid {C['border']};border-radius:10px;}}")
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}")
            self._gst_lbl_pct.setText("0%  — No GST")
            self._gst_lbl_base.setText(f"₹ {sp:.2f}")
            self._gst_lbl_cgst.setText("₹ 0.00")
            self._gst_lbl_sgst.setText("₹ 0.00")
            self._gst_lbl_amt.setText("₹ 0.00")
            self._gst_lbl_cust.setText(f"₹ {sp:.2f}")
            self._gst_msg_lbl.setText("ℹ️  GST rate is 0% — no tax will be added to this product.")
            self._gst_msg_lbl.setStyleSheet(f"font-size:11px;color:{C['text3']};background:transparent;padding-top:4px;border:none;")
            return

        if inclusive:
            # GST is already in the selling price — extract it
            base    = round(sp / (1 + gst_pct / 100), 2)
            gst_amt = round(sp - base, 2)
            cgst    = round(gst_amt / 2, 2)
            sgst    = round(gst_amt - cgst, 2)
            self._gst_panel.setStyleSheet(
                "QFrame{background:#F0FDF4;border:1.5px solid #86EFAC;border-radius:10px;}")
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}  (GST included)")
            self._gst_lbl_pct.setText(gst_str)
            self._gst_lbl_base.setText(f"₹ {base:.2f}")
            self._gst_lbl_cgst.setText(f"₹ {cgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_sgst.setText(f"₹ {sgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_amt.setText(f"₹ {gst_amt:.2f}")
            self._gst_lbl_cust.setText(f"₹ {sp:.2f}  ✅ (no extra charge)")
            self._gst_msg_lbl.setStyleSheet(f"font-size:11px;color:{C['success']};background:transparent;padding-top:4px;border:none;")
            self._gst_msg_lbl.setText(
                f"✅  GST included in ₹ {sp:.2f}.  "
                f"Base ₹ {base:.2f}  +  CGST ₹ {cgst:.2f}  +  SGST ₹ {sgst:.2f}  =  ₹ {sp:.2f}")
        else:
            # GST added on top of selling price
            gst_amt   = round(sp * gst_pct / 100, 2)
            cgst      = round(gst_amt / 2, 2)
            sgst      = round(gst_amt - cgst, 2)
            cust_pays = round(sp + gst_amt, 2)
            self._gst_panel.setStyleSheet(
                "QFrame{background:#FFF7ED;border:1.5px solid #FDBA74;border-radius:10px;}")
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}  (base / excl. GST)")
            self._gst_lbl_pct.setText(gst_str)
            self._gst_lbl_base.setText(f"₹ {sp:.2f}")
            self._gst_lbl_cgst.setText(f"₹ {cgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_sgst.setText(f"₹ {sgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_amt.setText(f"₹ {gst_amt:.2f}")
            self._gst_lbl_cust.setText(f"₹ {cust_pays:.2f}  ⚠️ (GST added on top)")
            self._gst_msg_lbl.setStyleSheet(f"font-size:11px;color:{C['warning']};background:transparent;padding-top:4px;border:none;")
            self._gst_msg_lbl.setText(
                f"⚠️  GST added at billing.  "
                f"₹ {sp:.2f}  +  CGST ₹ {cgst:.2f}  +  SGST ₹ {sgst:.2f}  =  Customer pays ₹ {cust_pays:.2f}")

    # ── TAB 3: INVENTORY ──────────────────────────────────

    def _build_tab_inventory(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

        sec, g = make_section("Stock Levels", "📦")
        self.f_opening_stock = QSpinBox(); self.f_opening_stock.setRange(0, 9999999)
        self.f_opening_stock.setFixedHeight(38)
        self.f_opening_stock.setStyleSheet(_NO_ARROW)
        self.f_reorder_level = QSpinBox(); self.f_reorder_level.setRange(0, 9999999)
        self.f_reorder_level.setFixedHeight(38)
        self.f_reorder_level.setStyleSheet(_NO_ARROW)
        self.f_safety_stock  = QSpinBox(); self.f_safety_stock.setRange(0, 9999999)
        self.f_safety_stock.setFixedHeight(38)
        self.f_safety_stock.setStyleSheet(_NO_ARROW)
        self.f_reorder_qty   = QSpinBox(); self.f_reorder_qty.setRange(0, 9999999)
        self.f_reorder_qty.setFixedHeight(38)
        self.f_reorder_qty.setStyleSheet(_NO_ARROW)
        self.f_min_order_qty = QSpinBox(); self.f_min_order_qty.setRange(1, 999999); self.f_min_order_qty.setValue(1)
        self.f_min_order_qty.setFixedHeight(38)
        self.f_min_order_qty.setStyleSheet(_NO_ARROW)
        self.f_max_stock     = QSpinBox(); self.f_max_stock.setRange(0, 9999999)
        self.f_max_stock.setFixedHeight(38)
        self.f_max_stock.setStyleSheet(_NO_ARROW)
        self.lbl_available   = ro_label("—")
        self.lbl_stock_val   = ro_label("—")
        self.lbl_days_left   = ro_label("—")
        self.f_auto_reorder  = ToggleSwitch("Auto-generate PO when stock hits reorder level")
        self.f_allow_neg     = ToggleSwitch("Allow negative stock")
        self.f_returnable    = ToggleSwitch("Product is returnable"); self.f_returnable.setChecked(True)
        self.f_purchase_invoice = QLineEdit()
        self.f_purchase_invoice.setPlaceholderText("Purchase invoice number")
        self.f_purchase_date = QDateEdit()
        self.f_purchase_date.setCalendarPopup(True)
        self.f_purchase_date.setDisplayFormat("dd-MM-yyyy")
        self.f_purchase_date.setDate(QDate.currentDate())
        self.f_purchase_date.lineEdit().setPlaceholderText("Select purchase date")
        self.f_purchase_date.clear()
        _normalize_field_widget(self.f_purchase_invoice)
        _normalize_field_widget(self.f_purchase_date)
        self.f_opening_stock.valueChanged.connect(self._update_stock_calcs)

        r = 0
        add_field(g, r, 0, "Opening Stock",   self.f_opening_stock, required=True)
        add_field(g, r, 2, "Reorder Level",   self.f_reorder_level, hint="Alert below this")
        r += 1
        add_field(g, r, 0, "Safety Stock",    self.f_safety_stock, hint="Never go below this buffer")
        add_field(g, r, 2, "Reorder Qty",     self.f_reorder_qty,  hint="Suggested PO quantity")
        r += 1
        add_field(g, r, 0, "Min Order Qty",   self.f_min_order_qty)
        add_field(g, r, 2, "Max Stock",       self.f_max_stock)
        r += 1
        add_field(g, r, 0, "Available Stock", self.lbl_available, hint="Stock − Reserved − Damaged")
        add_field(g, r, 2, "Stock Value",     self.lbl_stock_val,  hint="Stock x Purchase Price")
        r += 1
        add_field(g, r, 0, "Purchase Invoice No", self.f_purchase_invoice, required=True)
        add_field(g, r, 2, "Date of Purchase", self.f_purchase_date, required=True)
        r += 1
        add_field(g, r, 0, "Days of Stock",   self.lbl_days_left,  hint="Based on 30-day avg sales")
        r += 1
        g.addWidget(self.f_auto_reorder, r, 0, 1, 4); r += 1
        g.addWidget(self.f_allow_neg,    r, 0, 1, 2)
        g.addWidget(self.f_returnable,   r, 2, 1, 2)
        lay.addWidget(sec)

        # Hidden stubs retained for old save/load fields; storage and batch/expiry UI is removed.
        self.f_warehouse = QComboBox(); self.f_warehouse.setEditable(True); self.f_warehouse.hide()
        self.f_warehouse.addItems([""])
        self.f_rack = QLineEdit(); self.f_rack.hide()
        self.f_bin  = QLineEdit(); self.f_bin.hide()
        self.f_track_batch  = ToggleSwitch("Track batch numbers"); self.f_track_batch.hide()
        self.f_track_expiry = ToggleSwitch("Track expiry dates"); self.f_track_expiry.hide()
        self.f_track_mfg    = ToggleSwitch("Track manufacture dates"); self.f_track_mfg.hide()
        self.f_track_serial = ToggleSwitch("Track serial numbers"); self.f_track_serial.hide()
        self.f_mfg_date     = QDateEdit(); self.f_mfg_date.hide()
        self.f_mfg_date.setDate(QDate.currentDate()); self.f_mfg_date.setDisplayFormat("dd-MM-yyyy")
        self.f_expiry_date  = QDateEdit(); self.f_expiry_date.hide()
        self.f_expiry_date.setDate(QDate.currentDate().addYears(1)); self.f_expiry_date.setDisplayFormat("dd-MM-yyyy")
        self.f_expiry_alert = QSpinBox(); self.f_expiry_alert.hide()
        self.f_expiry_alert.setRange(1, 365); self.f_expiry_alert.setValue(30)
        self.lbl_shelf_calc = ro_label("—"); self.lbl_shelf_calc.hide()
        self.batch_frame = QFrame(); self.batch_frame.hide()
        self.batch_table = mini_table(["Batch No", "Qty", "Mfg Date", "Expiry", "Price", "Supplier"])

        self._available_stock_panel = QFrame()
        self._available_stock_panel.setObjectName("availableStockPanel")
        self._available_stock_panel.setStyleSheet(
            f"QFrame#availableStockPanel{{background:{C['bg_light']};"
            f"border:1.5px solid {C['border']};border-radius:10px;}}"
        )
        available_lay = QVBoxLayout(self._available_stock_panel)
        available_lay.setContentsMargins(18, 16, 18, 16); available_lay.setSpacing(8)
        available_title = QLabel("📊  Available Stock")
        available_title.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['blue']};"
            f"background:transparent;border:none;padding-bottom:6px;"
        )
        available_lay.addWidget(available_title)
        available_sep = QFrame(); available_sep.setFrameShape(QFrame.Shape.HLine)
        available_sep.setStyleSheet(
            f"background:{C['border']};border:none;max-height:1px;"
        )
        available_lay.addWidget(available_sep)
        self._variant_summary_wrap = QWidget()
        self._variant_summary_wrap.setStyleSheet("background:transparent;border:none;")
        self._variant_summary_grid = QGridLayout(self._variant_summary_wrap)
        self._variant_summary_grid.setContentsMargins(0, 4, 0, 0)
        self._variant_summary_grid.setHorizontalSpacing(28)
        self._variant_summary_grid.setVerticalSpacing(8)
        available_lay.addWidget(self._variant_summary_wrap)
        self._available_stock_panel.setVisible(False)
        lay.addWidget(self._available_stock_panel)

        sec2, g2 = make_section("Variants", "📏")
        g2.setColumnStretch(1, 1); g2.setColumnStretch(3, 1)
        self._variant_pending = {}
        self._variant_drafts = {}
        self._variant_locked = set()
        self._variant_current_group = VARIANT_STORAGE_GROUP
        self._variant_toggle_guard = False
        self._color_tables = {}
        self._color_headers = {}
        self._open_color_category = None
        self._custom_values = []
        self.f_has_variants = ToggleSwitch("Variant by size")
        self.f_has_color_variants = ToggleSwitch("Variant by color")
        self.f_has_custom_variants = ToggleSwitch("Variant by custom")
        # Hidden compatibility field used by existing save/load code.
        self.f_variant_type = QComboBox()
        self.f_variant_type.addItems(AGE_CATEGORIES)
        self.f_variant_type.hide()
        _apply_combo_delegate(self.f_variant_type)
        toggle_wrap = QWidget()
        toggle_lay = QHBoxLayout(toggle_wrap)
        toggle_lay.setContentsMargins(0, 0, 0, 0)
        toggle_lay.setSpacing(36)
        toggle_lay.addWidget(self.f_has_variants)
        toggle_lay.addWidget(self.f_has_color_variants)
        toggle_lay.addWidget(self.f_has_custom_variants)
        toggle_lay.addStretch()
        g2.addWidget(toggle_wrap, 0, 0, 1, 4)
        self._variant_type_label = QLabel("Age Category *")
        self._variant_type_label.setStyleSheet(LABEL_SS)
        self._variant_type_label.setVisible(False)
        g2.addWidget(self._variant_type_label, 1, 0)
        self._variant_radio_wrap = QWidget()
        radio_lay = QHBoxLayout(self._variant_radio_wrap)
        radio_lay.setContentsMargins(0, 0, 0, 0); radio_lay.setSpacing(24)
        self._variant_radio_group = QButtonGroup(self)
        self._variant_radios = {}
        for group_name in AGE_CATEGORIES:
            radio = QRadioButton(group_name)
            radio.setFixedSize(150, 50)
            radio.setStyleSheet(
                f"QRadioButton{{color:{C['text']};font-size:13px;font-weight:600;"
                f"spacing:15px;padding:0 20px;border:2px solid transparent;"
                f"border-radius:10px;background:transparent;}}"
                f"QRadioButton:hover{{background:#F5F6FA;}}"
                f"QRadioButton:checked{{background:{C['accent_tint2']};"
                f"border-color:{C['accent']};color:{C['accent_dark']};}}"
                f"QRadioButton::indicator{{width:18px;height:18px;border-radius:9px;"
                f"border:1px solid #9F9F9F;background:#D9D9E5;}}"
                f"QRadioButton::indicator:checked{{background:white;"
                f"border:2px solid {C['accent']};border-radius:9px;}}"
            )
            self._variant_radio_group.addButton(radio)
            self._variant_radios[group_name] = radio
            radio_lay.addWidget(radio)
            radio.toggled.connect(
                lambda checked, name=group_name:
                    self._on_variant_radio_changed(name) if checked else None
            )
        radio_lay.addStretch()
        self._variant_radios["Generic"].setChecked(True)
        self._variant_radio_wrap.setVisible(False)
        g2.addWidget(self._variant_radio_wrap, 1, 1, 1, 3)

        self._color_accordion = QWidget()
        self._color_accordion_lay = QVBoxLayout(self._color_accordion)
        self._color_accordion_lay.setContentsMargins(0, 0, 0, 0)
        self._color_accordion_lay.setSpacing(6)
        self._color_accordion.setVisible(False)
        g2.addWidget(self._color_accordion, 1, 0, 1, 4)

        self._custom_panel = QWidget()
        custom_lay = QVBoxLayout(self._custom_panel)
        custom_lay.setContentsMargins(0, 0, 0, 0)
        custom_lay.setSpacing(8)
        custom_entry_row = QHBoxLayout()
        custom_entry_row.setContentsMargins(0, 0, 0, 0)
        custom_entry_row.setSpacing(8)
        self.f_custom_variant = QLineEdit()
        self.f_custom_variant.setPlaceholderText(
            "Enter custom variant (for example: Small, Cotton, Premium)"
        )
        _normalize_field_widget(self.f_custom_variant)
        self._custom_add_btn = _GBtn("+", "blue")
        self._custom_add_btn.setFixedSize(46, 38)
        self._custom_add_btn.setToolTip("Add custom variant")
        custom_entry_row.addWidget(self.f_custom_variant, 1)
        custom_entry_row.addWidget(self._custom_add_btn)
        custom_lay.addLayout(custom_entry_row)

        self.custom_variant_table = QTableWidget(0, 5)
        self.custom_variant_table.setHorizontalHeaderLabels(
            ["Custom Variant", "Available Stock", "Update Stock", "Action", "Barcode"]
        )
        self.custom_variant_table.verticalHeader().setVisible(False)
        self.custom_variant_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.custom_variant_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.custom_variant_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.custom_variant_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.custom_variant_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.custom_variant_table.setVisible(False)
        custom_lay.addWidget(self.custom_variant_table)
        self._custom_panel.setVisible(False)
        g2.addWidget(self._custom_panel, 1, 0, 1, 4)

        self._variant_update_panel = QFrame()
        self._variant_update_panel.setStyleSheet(
            f"QFrame#variantUpdatePanel{{background:rgba(245,247,250,210);"
            f"border:1.5px solid {C['border']};border-radius:10px;}}"
        )
        self._variant_update_panel.setObjectName("variantUpdatePanel")
        update_lay = QVBoxLayout(self._variant_update_panel)
        update_lay.setContentsMargins(16, 14, 16, 16); update_lay.setSpacing(10)

        update_title = QLabel("Stock Update")
        update_title.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['accent_dark']};"
            f"background:transparent;border:none;"
        )
        update_lay.addWidget(update_title)

        self.variant_table = QTableWidget(0, 5)
        self.variant_table.setHorizontalHeaderLabels(
            ["Size", "Available Stock", "Update Stock", "Action", "Barcode"]
        )
        self.variant_table.verticalHeader().setVisible(False)
        self.variant_table.setAlternatingRowColors(True)
        self.variant_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.variant_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.variant_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.variant_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.variant_table.setStyleSheet(f"""
            QTableWidget{{background:{C['bg_white']};border:1px solid {C['border']};
                border-radius:8px;font-size:12px;}}
            QHeaderView::section{{background:{C['bg_light']};font-weight:700;padding:7px;
                border:none;border-bottom:1px solid {C['border']};color:{C['text2']};font-size:11px;}}
            QTableWidget::item{{padding:5px 8px;color:{C['text']};}}
            QTableWidget::item:selected{{background:{C['accent_tint2']};color:{C['text']};}}
        """)
        self.variant_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        update_lay.addWidget(self.variant_table)
        self._variant_update_panel.setVisible(False)
        g2.addWidget(self._variant_update_panel, 2, 0, 1, 4)
        self._build_color_accordion()
        self.custom_variant_table.setStyleSheet(self.variant_table.styleSheet())
        lay.addWidget(sec2)

        self.f_has_variants.stateChanged.connect(self._toggle_variants)
        self.f_has_color_variants.stateChanged.connect(self._toggle_color_variants)
        self.f_has_custom_variants.stateChanged.connect(self._toggle_custom_variants)
        self._custom_add_btn.clicked.connect(self._add_custom_variant)
        self.f_custom_variant.returnPressed.connect(self._add_custom_variant)
        self._toggle_variants(False)

        sec_log, g_log = make_section("Purchase Invoice Log", "🧾")
        for col in range(4):
            g_log.setColumnStretch(col, 1)
        self.purchase_log_table = mini_table(
            ["Invoice No", "Purchase Date", "Stock Update", "Purchase Price", "GST", "Price incl. GST"],
            height=190
        )
        self.purchase_log_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        g_log.addWidget(self.purchase_log_table, 0, 0, 1, 4)
        lay.addWidget(sec_log)

        # Hidden compatibility stubs. Stock is updated directly in the variant table.
        self.adj_frame = QFrame(); self.adj_frame.hide()
        self.adj_table = mini_table(["Type", "Qty", "Reason", "Date", "By"])
        self.adj_table.hide()

        lay.addStretch()
        self.tabs.addTab(page, "📦  Inventory")

    def _update_tracking_fields(self):
        if not all(hasattr(self, name) for name in (
            "f_track_mfg", "f_track_expiry", "f_mfg_date",
            "f_expiry_date", "f_expiry_alert", "lbl_shelf_calc",
        )):
            return
        track_mfg = self.f_track_mfg.isChecked()
        track_exp = self.f_track_expiry.isChecked()
        self.f_mfg_date.setEnabled(track_mfg)
        self.f_expiry_date.setEnabled(track_exp)
        self.f_expiry_alert.setEnabled(track_exp)
        self.lbl_shelf_calc.setEnabled(track_mfg and track_exp)
        if hasattr(self, "batch_frame"):
            self.batch_frame.setVisible(False)
        self._calc_shelf()

    def _calc_shelf(self):
        if not (self.f_track_mfg.isChecked() and self.f_track_expiry.isChecked()):
            self.lbl_shelf_calc.setText("—")
            return
        days = self.f_mfg_date.date().daysTo(self.f_expiry_date.date())
        self.lbl_shelf_calc.setText(f"{days} days" if days > 0 else "—")

    def _update_stock_calcs(self):
        if (
            hasattr(self, "f_has_variants")
            and (
                self.f_has_variants.isChecked()
                or self.f_has_color_variants.isChecked()
                or self.f_has_custom_variants.isChecked()
            )
        ):
            return
        s = self.f_opening_stock.value()
        self.lbl_available.setText(str(s))

    def _build_color_accordion(self):
        for category, colors in COLOR_GROUPS.items():
            header = QToolButton()
            display_category = category.replace("&", "&&")
            header.setText(f"›  {display_category}")
            header.setCheckable(True)
            header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            header.setFixedHeight(42)
            header.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            header.setStyleSheet(
                f"QToolButton{{text-align:left;padding:0 14px;background:{C['bg_light']};"
                f"color:{C['text']};border:1px solid {C['border']};border-radius:8px;"
                f"font-size:12px;font-weight:700;}}"
                f"QToolButton:hover{{border-color:{C['accent']};background:{C['accent_tint2']};}}"
                f"QToolButton:checked{{color:{C['accent_dark']};border-color:{C['accent']};"
                f"background:{C['accent_tint2']};}}"
            )
            table = QTableWidget(0, 5)
            table.setHorizontalHeaderLabels(
                ["Color", "Available Stock", "Update Stock", "Action", "Barcode"]
            )
            table.verticalHeader().setVisible(False)
            table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setStyleSheet(self.variant_table.styleSheet())
            table.setVisible(False)
            self._color_headers[category] = header
            self._color_tables[category] = table
            self._color_accordion_lay.addWidget(header)
            self._color_accordion_lay.addWidget(table)
            header.toggled.connect(
                lambda checked, name=category: self._toggle_color_category(name, checked)
            )
        self._color_accordion_lay.addStretch()

    def _toggle_color_category(self, category, checked):
        if checked:
            for name, header in self._color_headers.items():
                if name != category:
                    header.blockSignals(True)
                    header.setChecked(False)
                    header.blockSignals(False)
                    self._color_tables[name].setVisible(False)
                    header.setText(f"›  {name.replace('&', '&&')}")
            self._open_color_category = category
            self._color_headers[category].setText(
                f"⌄  {category.replace('&', '&&')}"
            )
            self._color_tables[category].setVisible(True)
        else:
            self._color_headers[category].setText(
                f"›  {category.replace('&', '&&')}"
            )
            self._color_tables[category].setVisible(False)
            if self._open_color_category == category:
                self._open_color_category = None

    def _open_color_only(self, category):
        header = self._color_headers.get(category)
        if header:
            if header.isChecked():
                self._toggle_color_category(category, True)
            else:
                header.setChecked(True)

    def _toggle_variants(self, state):
        enabled = bool(state)
        if enabled and self.f_has_color_variants.isChecked():
            self.f_has_color_variants.setChecked(False)
        if enabled and self.f_has_custom_variants.isChecked():
            self.f_has_custom_variants.setChecked(False)
        self._color_accordion.setVisible(False)
        self._custom_panel.setVisible(False)
        self.custom_variant_table.setVisible(False)
        for table in self._color_tables.values():
            table.setVisible(False)
        self._variant_type_label.setVisible(enabled)
        self.f_variant_type.setVisible(False)
        self._variant_radio_wrap.setVisible(enabled)
        self._available_stock_panel.setVisible(enabled)
        self._variant_update_panel.setVisible(enabled)
        self._variant_summary_wrap.setVisible(enabled)
        self.variant_table.setVisible(enabled)
        self.f_opening_stock.setEnabled(
            not enabled
            and not self.f_has_color_variants.isChecked()
            and not self.f_has_custom_variants.isChecked()
        )
        if enabled:
            self._rebuild_variant_table()
        else:
            self._capture_variant_updates()
            self.variant_table.setRowCount(0)
            if not (
                self.f_has_color_variants.isChecked()
                or self.f_has_custom_variants.isChecked()
            ):
                self._available_stock_panel.setVisible(False)
                self._update_stock_calcs()

    def _toggle_color_variants(self, state):
        enabled = bool(state)
        if enabled and self.f_has_variants.isChecked():
            self.f_has_variants.setChecked(False)
        if enabled and self.f_has_custom_variants.isChecked():
            self.f_has_custom_variants.setChecked(False)
        self._variant_type_label.setVisible(False)
        self._variant_radio_wrap.setVisible(False)
        self._variant_update_panel.setVisible(False)
        self.variant_table.setVisible(False)
        self._custom_panel.setVisible(False)
        self.custom_variant_table.setVisible(False)
        self._color_accordion.setVisible(enabled)
        self._available_stock_panel.setVisible(enabled)
        self._variant_summary_wrap.setVisible(enabled)
        self.f_opening_stock.setEnabled(
            not enabled
            and not self.f_has_variants.isChecked()
            and not self.f_has_custom_variants.isChecked()
        )
        if enabled:
            self._variant_current_group = COLOR_STORAGE_GROUP
            self._rebuild_color_tables()
            category = self._open_color_category or next(iter(COLOR_GROUPS))
            self._open_color_only(category)
        else:
            self._capture_color_updates()
            for header in self._color_headers.values():
                header.blockSignals(True)
                header.setChecked(False)
                header.blockSignals(False)
            for table in self._color_tables.values():
                table.setVisible(False)
            self._open_color_category = None
            if not (
                self.f_has_variants.isChecked()
                or self.f_has_custom_variants.isChecked()
            ):
                self._available_stock_panel.setVisible(False)
                self._update_stock_calcs()

    def _toggle_custom_variants(self, state):
        enabled = bool(state)
        if enabled and self.f_has_variants.isChecked():
            self.f_has_variants.setChecked(False)
        if enabled and self.f_has_color_variants.isChecked():
            self.f_has_color_variants.setChecked(False)
        self._variant_type_label.setVisible(False)
        self._variant_radio_wrap.setVisible(False)
        self._variant_update_panel.setVisible(False)
        self.variant_table.setVisible(False)
        self._color_accordion.setVisible(False)
        for table in self._color_tables.values():
            table.setVisible(False)
        self._custom_panel.setVisible(enabled)
        self.custom_variant_table.setVisible(enabled)
        self._available_stock_panel.setVisible(enabled)
        self._variant_summary_wrap.setVisible(enabled)
        self.f_opening_stock.setEnabled(
            not enabled
            and not self.f_has_variants.isChecked()
            and not self.f_has_color_variants.isChecked()
        )
        if enabled:
            self._variant_current_group = CUSTOM_STORAGE_GROUP
            self._load_custom_values()
            self._rebuild_custom_table()
            QTimer.singleShot(0, self.f_custom_variant.setFocus)
        else:
            self._capture_custom_updates()
            if not (
                self.f_has_variants.isChecked()
                or self.f_has_color_variants.isChecked()
            ):
                self._available_stock_panel.setVisible(False)
                self._update_stock_calcs()

    def _load_custom_values(self):
        saved = self._custom_stock_map()
        for group, name in saved:
            if group == CUSTOM_STORAGE_GROUP and name not in self._custom_values:
                self._custom_values.append(name)

    def _add_custom_variant(self):
        name = self.f_custom_variant.text().strip()
        if not name:
            self.f_custom_variant.setFocus()
            return
        if any(existing.casefold() == name.casefold() for existing in self._custom_values):
            QMessageBox.information(
                self, "Custom Variant", f'"{name}" is already in the list.'
            )
            self.f_custom_variant.selectAll()
            return
        self._capture_custom_updates()
        self._custom_values.append(name)
        self.f_custom_variant.clear()
        self._rebuild_custom_table()
        self.f_custom_variant.setFocus()

    def _custom_stock_map(self):
        product_code = self.edit_code or self.f_item_code.text().strip()
        return (
            get_product_variants(self.db_name, product_code, CUSTOM_STORAGE_GROUP)
            if product_code else {}
        )

    def _rebuild_custom_table(self):
        saved = self._custom_stock_map()
        table = self.custom_variant_table
        table.setRowCount(0)
        for name in self._custom_values:
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, 68)

            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, name_item)

            existing = saved.get((CUSTOM_STORAGE_GROUP, name), {}).get("stock", 0)
            available = QTableWidgetItem(str(existing))
            available.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 1, available)

            key = (CUSTOM_STORAGE_GROUP, name)
            qty = QSpinBox()
            qty.setRange(0, 9999999)
            qty.setValue(int(self._variant_drafts.get(
                key, self._variant_pending.get(key, 0)
            ) or 0))
            qty.setFixedHeight(46)
            qty.setStyleSheet(_NO_ARROW)
            qty.setEnabled(key not in self._variant_locked)
            if hasattr(self, "_no_wheel_filter"):
                qty.installEventFilter(self._no_wheel_filter)
            qty.valueChanged.connect(
                lambda value, n=name: self._on_variant_draft_changed(
                    CUSTOM_STORAGE_GROUP, n, value
                )
            )
            table.setCellWidget(row, 2, qty)

            action = _GBtn("EDIT" if key in self._variant_locked else "UPDATE", "success")
            action.setFixedHeight(46)
            action.clicked.connect(
                lambda _checked=False, n=name, r=row:
                    self._toggle_custom_row(n, r)
            )
            table.setCellWidget(row, 3, action)

            barcode = _GBtn("Print Label", "blue")
            barcode.setFixedHeight(46)
            barcode.clicked.connect(
                lambda _checked=False, n=name: self._print_custom_barcode(n)
            )
            table.setCellWidget(row, 4, barcode)

        table.horizontalHeader().setFixedHeight(48)
        table.setFixedHeight(48 + len(self._custom_values) * 68 + 4)
        self._refresh_custom_summary(saved)
        self._sync_variant_total()

    def _capture_custom_updates(self):
        table = self.custom_variant_table
        for row in range(table.rowCount()):
            name_item = table.item(row, 0)
            spin = table.cellWidget(row, 2)
            if name_item and isinstance(spin, QSpinBox):
                self._variant_drafts[
                    (CUSTOM_STORAGE_GROUP, name_item.text())
                ] = spin.value()

    def _toggle_custom_row(self, name, row):
        key = (CUSTOM_STORAGE_GROUP, name)
        spin = self.custom_variant_table.cellWidget(row, 2)
        button = self.custom_variant_table.cellWidget(row, 3)
        if not isinstance(spin, QSpinBox) or not isinstance(button, QPushButton):
            return
        if key in self._variant_locked:
            self._variant_locked.remove(key)
            self._variant_pending.pop(key, None)
            spin.setEnabled(True)
            spin.setStyleSheet(
                _NO_ARROW + f"QSpinBox{{border:2px solid {C['accent']};"
                f"border-radius:8px;background:{C['bg_white']};}}"
            )
            button.setText("UPDATE")
            QTimer.singleShot(0, lambda: (spin.setFocus(), spin.selectAll()))
        else:
            value = spin.value()
            self._variant_drafts[key] = value
            if value > 0:
                self._variant_pending[key] = value
            else:
                self._variant_pending.pop(key, None)
            self._variant_locked.add(key)
            spin.setEnabled(False)
            spin.setStyleSheet(_NO_ARROW)
            button.setText("EDIT")
        self._sync_variant_total()

    def _custom_rows(self):
        self._capture_custom_updates()
        return [
            (
                CUSTOM_STORAGE_GROUP,
                name,
                int(self._variant_pending.get(
                    (CUSTOM_STORAGE_GROUP, name), 0
                ) or 0),
                "",
            )
            for name in self._custom_values
        ]

    def _print_custom_barcode(self, name):
        QMessageBox.information(
            self, "Barcode", f"Barcode label for {name} will be added later."
        )

    def _refresh_custom_summary(self, saved=None):
        if not hasattr(self, "_variant_summary_grid"):
            return
        while self._variant_summary_grid.count():
            item = self._variant_summary_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        saved = saved if saved is not None else self._custom_stock_map()
        available = [
            (name, int(saved.get(
                (CUSTOM_STORAGE_GROUP, name), {}
            ).get("stock", 0) or 0))
            for name in self._custom_values
        ]
        available = [(name, qty) for name, qty in available if qty > 0]
        for index, (name, qty) in enumerate(available):
            row = index // 3
            pair_col = (index % 3) * 2
            name_label = QLabel(name)
            name_label.setStyleSheet(
                f"font-size:12px;color:{C['text2']};background:transparent;border:none;"
            )
            qty_label = QLabel(str(qty))
            qty_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            qty_label.setStyleSheet(
                f"font-size:12px;font-weight:700;color:{C['text']};"
                "background:transparent;border:none;"
            )
            self._variant_summary_grid.addWidget(name_label, row, pair_col)
            self._variant_summary_grid.addWidget(qty_label, row, pair_col + 1)
        total_row = ((len(available) + 2) // 3) + 1 if available else 0
        total_label = QLabel("Total Stock")
        total_label.setStyleSheet(
            f"font-size:12px;color:{C['blue']};font-weight:600;"
            "background:transparent;border:none;"
        )
        total_value = QLabel(str(sum(qty for _name, qty in available)))
        total_value.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['blue']};"
            "background:transparent;border:none;"
        )
        self._variant_summary_grid.addWidget(total_label, total_row, 0)
        self._variant_summary_grid.addWidget(total_value, total_row, 1)

    def _rebuild_color_tables(self):
        saved = self._color_stock_map()
        for category, colors in COLOR_GROUPS.items():
            table = self._color_tables[category]
            table.setRowCount(0)
            for color in colors:
                row = table.rowCount()
                table.insertRow(row)
                table.setRowHeight(row, 68)

                color_item = QTableWidgetItem(color)
                color_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 0, color_item)

                existing = saved.get((COLOR_STORAGE_GROUP, color), {}).get("stock", 0)
                available = QTableWidgetItem(str(existing))
                available.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 1, available)

                key = (COLOR_STORAGE_GROUP, color)
                qty = QSpinBox()
                qty.setRange(0, 9999999)
                qty.setValue(int(self._variant_drafts.get(
                    key, self._variant_pending.get(key, 0)
                ) or 0))
                qty.setFixedHeight(46)
                qty.setStyleSheet(_NO_ARROW)
                qty.setEnabled(key not in self._variant_locked)
                if hasattr(self, "_no_wheel_filter"):
                    qty.installEventFilter(self._no_wheel_filter)
                qty.valueChanged.connect(
                    lambda value, c=color: self._on_variant_draft_changed(
                        COLOR_STORAGE_GROUP, c, value
                    )
                )
                table.setCellWidget(row, 2, qty)

                action = _GBtn("EDIT" if key in self._variant_locked else "UPDATE", "success")
                action.setFixedHeight(46)
                action.clicked.connect(
                    lambda _checked=False, cat=category, c=color, r=row, t=table:
                        self._toggle_color_row(cat, c, r, t)
                )
                table.setCellWidget(row, 3, action)

                barcode = _GBtn("Print Label", "blue")
                barcode.setFixedHeight(46)
                barcode.clicked.connect(
                    lambda _checked=False, c=color: self._print_color_barcode(c)
                )
                table.setCellWidget(row, 4, barcode)

            table.horizontalHeader().setFixedHeight(48)
            table.setFixedHeight(48 + len(colors) * 68 + 4)
        self._refresh_color_summary(saved)
        self._sync_variant_total()

    def _capture_color_updates(self):
        for table in self._color_tables.values():
            for row in range(table.rowCount()):
                color_item = table.item(row, 0)
                spin = table.cellWidget(row, 2)
                if color_item and isinstance(spin, QSpinBox):
                    self._variant_drafts[
                        (COLOR_STORAGE_GROUP, color_item.text())
                    ] = spin.value()

    def _color_stock_map(self):
        product_code = self.edit_code or self.f_item_code.text().strip()
        return (
            get_product_variants(self.db_name, product_code, COLOR_STORAGE_GROUP)
            if product_code else {}
        )

    def _toggle_color_row(self, category, color, row, table):
        self._open_color_only(category)
        key = (COLOR_STORAGE_GROUP, color)
        spin = table.cellWidget(row, 2)
        button = table.cellWidget(row, 3)
        if not isinstance(spin, QSpinBox) or not isinstance(button, QPushButton):
            return
        if key in self._variant_locked:
            self._variant_locked.remove(key)
            self._variant_pending.pop(key, None)
            spin.setEnabled(True)
            spin.setStyleSheet(
                _NO_ARROW + f"QSpinBox{{border:2px solid {C['accent']};"
                f"border-radius:8px;background:{C['bg_white']};}}"
            )
            button.setText("UPDATE")
            QTimer.singleShot(0, lambda: (spin.setFocus(), spin.selectAll()))
        else:
            value = spin.value()
            self._variant_drafts[key] = value
            if value > 0:
                self._variant_pending[key] = value
            else:
                self._variant_pending.pop(key, None)
            self._variant_locked.add(key)
            spin.setEnabled(False)
            spin.setStyleSheet(_NO_ARROW)
            button.setText("EDIT")
        self._sync_variant_total()

    def _color_rows(self):
        self._capture_color_updates()
        rows = []
        for colors in COLOR_GROUPS.values():
            for color in colors:
                qty = int(self._variant_pending.get(
                    (COLOR_STORAGE_GROUP, color), 0
                ) or 0)
                if qty > 0:
                    rows.append((COLOR_STORAGE_GROUP, color, qty, ""))
        return rows

    def _print_color_barcode(self, color):
        QMessageBox.information(
            self, "Barcode", f"Barcode label for {color} will be added later."
        )

    def _refresh_color_summary(self, saved=None):
        if not hasattr(self, "_variant_summary_grid"):
            return
        while self._variant_summary_grid.count():
            item = self._variant_summary_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        saved = saved if saved is not None else self._color_stock_map()
        available = []
        seen = set()
        for colors in COLOR_GROUPS.values():
            for color in colors:
                if color in seen:
                    continue
                seen.add(color)
                qty = int(saved.get(
                    (COLOR_STORAGE_GROUP, color), {}
                ).get("stock", 0) or 0)
                if qty > 0:
                    available.append((color, qty))
        for index, (color, qty) in enumerate(available):
            row = index // 3
            pair_col = (index % 3) * 2
            name = QLabel(color)
            name.setStyleSheet(
                f"font-size:12px;color:{C['text2']};background:transparent;border:none;"
            )
            value = QLabel(str(qty))
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setStyleSheet(
                f"font-size:12px;font-weight:700;color:{C['text']};"
                "background:transparent;border:none;"
            )
            self._variant_summary_grid.addWidget(name, row, pair_col)
            self._variant_summary_grid.addWidget(value, row, pair_col + 1)
        total_row = ((len(available) + 2) // 3) + 1 if available else 0
        total_label = QLabel("Total Stock")
        total_label.setStyleSheet(
            f"font-size:12px;color:{C['blue']};font-weight:600;"
            "background:transparent;border:none;"
        )
        total_value = QLabel(str(sum(qty for _color, qty in available)))
        total_value.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['blue']};"
            "background:transparent;border:none;"
        )
        self._variant_summary_grid.addWidget(total_label, total_row, 0)
        self._variant_summary_grid.addWidget(total_value, total_row, 1)

    def _on_variant_radio_changed(self, group):
        idx = self.f_variant_type.findText(group)
        if idx >= 0:
            self.f_variant_type.setCurrentIndex(idx)

    def _capture_variant_updates(self):
        if not hasattr(self, "variant_table") or not hasattr(self, "_variant_current_group"):
            return
        group = VARIANT_STORAGE_GROUP
        for row in range(self.variant_table.rowCount()):
            size_item = self.variant_table.item(row, 0)
            spin = self.variant_table.cellWidget(row, 2)
            if size_item and isinstance(spin, QSpinBox):
                self._variant_drafts[(group, size_item.text())] = spin.value()

    def _variant_stock_map(self):
        product_code = self.edit_code or self.f_item_code.text().strip()
        return get_product_variants(self.db_name, product_code) if product_code else {}

    def _rebuild_variant_table(self):
        if not hasattr(self, "variant_table") or not self.f_has_variants.isChecked():
            return
        group = VARIANT_STORAGE_GROUP
        self._variant_current_group = group
        sizes = _ALL_VARIANT_SIZES
        saved = self._variant_stock_map()
        self._refresh_variant_summary(saved)
        self.variant_table.setRowCount(0)
        for size in sizes:
            row = self.variant_table.rowCount()
            self.variant_table.insertRow(row)
            self.variant_table.setRowHeight(row, 68)

            size_item = QTableWidgetItem(size)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.variant_table.setItem(row, 0, size_item)

            existing = saved.get((group, size), {}).get("stock", 0)
            avail_item = QTableWidgetItem(str(existing))
            avail_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            avail_item.setFlags(avail_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.variant_table.setItem(row, 1, avail_item)

            qty = QSpinBox()
            qty.setRange(0, 9999999)
            key = (group, size)
            value = self._variant_drafts.get(key, self._variant_pending.get(key, 0))
            qty.setValue(int(value or 0))
            qty.setFixedHeight(46)
            qty.setStyleSheet(_NO_ARROW)
            qty.setEnabled(key not in self._variant_locked)
            if hasattr(self, "_no_wheel_filter"):
                qty.installEventFilter(self._no_wheel_filter)
            qty.valueChanged.connect(
                lambda value, g=group, s=size: self._on_variant_draft_changed(g, s, value)
            )
            self.variant_table.setCellWidget(row, 2, qty)

            action = _GBtn("EDIT" if key in self._variant_locked else "UPDATE", "success")
            action.setFixedHeight(46)
            action.clicked.connect(
                lambda _checked=False, g=group, s=size, r=row: self._toggle_variant_row(g, s, r)
            )
            self.variant_table.setCellWidget(row, 3, action)

            btn = _GBtn("Print Label", "blue")
            btn.setFixedHeight(46)
            btn.clicked.connect(lambda _checked=False, s=size: self._print_variant_barcode(s))
            self.variant_table.setCellWidget(row, 4, btn)

        header_h = 48
        row_h = 68
        self.variant_table.horizontalHeader().setFixedHeight(header_h)
        self.variant_table.setFixedHeight(header_h + (len(sizes) * row_h) + 4)
        self._sync_variant_total()

    def _refresh_variant_summary(self, saved=None):
        if not hasattr(self, "_variant_summary_grid"):
            return
        while self._variant_summary_grid.count():
            item = self._variant_summary_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        saved = saved if saved is not None else self._variant_stock_map()
        available = []
        for size in _ALL_VARIANT_SIZES:
            qty = int(saved.get((VARIANT_STORAGE_GROUP, size), {}).get("stock", 0) or 0)
            if qty > 0:
                available.append((size, qty))

        for index, (size, qty) in enumerate(available):
            row = index // 3
            pair_col = (index % 3) * 2
            size_lbl = QLabel(f"Size {size}")
            size_lbl.setStyleSheet(
                f"font-size:12px;color:{C['text2']};"
                f"background:transparent;border:none;"
            )
            qty_lbl = QLabel(str(qty))
            qty_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            qty_lbl.setStyleSheet(
                f"font-size:12px;font-weight:700;color:{C['text']};"
                f"background:transparent;border:none;"
            )
            self._variant_summary_grid.addWidget(size_lbl, row, pair_col)
            self._variant_summary_grid.addWidget(qty_lbl, row, pair_col + 1)

        total = sum(qty for _size, qty in available)
        total_row = ((len(available) + 2) // 3) + 1 if available else 0
        total_lbl = QLabel("Total Stock")
        total_lbl.setStyleSheet(
            f"font-size:12px;color:{C['blue']};font-weight:600;"
            f"background:transparent;border:none;"
        )
        total_value = QLabel(str(total))
        total_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_value.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['blue']};"
            f"background:transparent;border:none;"
        )
        self._variant_summary_grid.addWidget(total_lbl, total_row, 0)
        self._variant_summary_grid.addWidget(total_value, total_row, 1)

    def _on_variant_draft_changed(self, group, size, value):
        self._variant_drafts[(group, size)] = int(value or 0)

    def _toggle_variant_row(self, group, size, row):
        key = (group, size)
        spin = self.variant_table.cellWidget(row, 2)
        button = self.variant_table.cellWidget(row, 3)
        if not isinstance(spin, QSpinBox) or not isinstance(button, QPushButton):
            return
        if key in self._variant_locked:
            self._variant_locked.remove(key)
            self._variant_pending.pop(key, None)
            spin.setEnabled(True)
            spin.setStyleSheet(
                _NO_ARROW +
                f"QSpinBox{{border:2px solid {C['accent']};"
                f"border-radius:8px;background:{C['bg_white']};}}"
            )
            button.setText("UPDATE")
            QTimer.singleShot(0, lambda: (spin.setFocus(), spin.selectAll()))
        else:
            value = spin.value()
            self._variant_drafts[key] = value
            if value > 0:
                self._variant_pending[key] = value
            else:
                self._variant_pending.pop(key, None)
            self._variant_locked.add(key)
            spin.setEnabled(False)
            spin.setStyleSheet(_NO_ARROW)
            button.setText("EDIT")
        self._sync_variant_total()

    def _variant_rows(self):
        self._capture_variant_updates()
        if not hasattr(self, "variant_table") or not self.f_has_variants.isChecked():
            return []
        rows = []
        for size in _ALL_VARIANT_SIZES:
            qty = int(self._variant_pending.get((VARIANT_STORAGE_GROUP, size), 0) or 0)
            if qty > 0:
                rows.append((VARIANT_STORAGE_GROUP, size, qty, ""))
        return rows

    def _sync_variant_total(self):
        if not hasattr(self, "variant_table"):
            return
        if not (
            self.f_has_variants.isChecked()
            or self.f_has_color_variants.isChecked()
            or self.f_has_custom_variants.isChecked()
        ):
            return
        if self.f_has_custom_variants.isChecked():
            group = CUSTOM_STORAGE_GROUP
        elif self.f_has_color_variants.isChecked():
            group = COLOR_STORAGE_GROUP
        else:
            group = VARIANT_STORAGE_GROUP
        pending_total = sum(
            int(v or 0) for (item_group, _name), v in self._variant_pending.items()
            if item_group == group
        )
        available_total = self._variant_saved_total()
        self.f_opening_stock.blockSignals(True)
        self.f_opening_stock.setValue(pending_total)
        self.f_opening_stock.blockSignals(False)
        self.lbl_available.setText(str(available_total))

    def _print_variant_barcode(self, size):
        QMessageBox.information(self, "Barcode", f"Barcode label for size {size} will be added later.")

    def _variant_saved_total(self):
        product_code = self.edit_code or self.f_item_code.text().strip()
        if not product_code:
            return 0
        if self.f_has_custom_variants.isChecked():
            group = CUSTOM_STORAGE_GROUP
        elif self.f_has_color_variants.isChecked():
            group = COLOR_STORAGE_GROUP
        else:
            group = VARIANT_STORAGE_GROUP
        return sum(
            v.get("stock", 0)
            for v in get_product_variants(self.db_name, product_code, group).values()
        )

    def _variant_pending_total(self):
        if self.f_has_custom_variants.isChecked():
            self._capture_custom_updates()
            group = CUSTOM_STORAGE_GROUP
        elif self.f_has_color_variants.isChecked():
            self._capture_color_updates()
            group = COLOR_STORAGE_GROUP
        else:
            self._capture_variant_updates()
            group = VARIANT_STORAGE_GROUP
        return sum(
            int(v or 0) for (item_group, _name), v in self._variant_pending.items()
            if item_group == group
        )

    def _purchase_price_including_gst(self):
        try:
            gst = float(self.f_purchase_gst.currentText().replace("%", "").strip())
        except Exception:
            gst = 0.0
        return round(self.f_purchase_price.value() * (1 + gst / 100), 2)

    def _stock_update_qty(self):
        if (
            self.f_has_variants.isChecked()
            or self.f_has_color_variants.isChecked()
            or self.f_has_custom_variants.isChecked()
        ):
            return self._variant_pending_total()
        return self.f_opening_stock.value() if not self.edit_code else 0

    def _save_purchase_entry(self, product_code, qty):
        if qty <= 0:
            return
        save_purchase_log(
            self.db_name,
            product_code,
            self.f_purchase_invoice.text().strip(),
            self.f_purchase_date.date().toString("yyyy-MM-dd"),
            qty,
            self.f_purchase_price.value(),
            self.f_purchase_gst.currentText(),
            self.current_user,
        )
        self.f_purchase_invoice.clear()
        self.f_purchase_date.setDate(QDate.currentDate())
        self.f_purchase_date.clear()
        self._load_purchase_log(product_code)

    def _load_purchase_log(self, product_code=None):
        code = product_code or self.edit_code or self.f_item_code.text().strip()
        rows = get_purchase_log(self.db_name, code)
        self.purchase_log_table.setRowCount(0)
        for invoice, purchase_date, qty, price, gst, price_with_gst in rows:
            row = self.purchase_log_table.rowCount()
            self.purchase_log_table.insertRow(row)
            values = [
                invoice, purchase_date, qty,
                f"₹{float(price or 0):,.2f}", gst,
                f"₹{float(price_with_gst or 0):,.2f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.purchase_log_table.setItem(row, col, item)

    def _add_batch(self):
        if not self.edit_code:
            QMessageBox.information(self, "Info", "Save the product first before adding batches.")
            return
        dlg = BatchAddDialog(self.db_name, self.edit_code, self.current_user, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_batches()

    def _do_adj(self):
        if not self.edit_code:
            QMessageBox.information(self, "Info", "Save the product first.")
            return
        p = get_product_full(self.db_name, self.edit_code)
        dlg = StockAdjDialog(self.db_name, self.edit_code,
                             self.f_name.text() or self.edit_code,
                             p.get("stock", 0) if p else 0, self.current_user, self,
                             track_batch=False,
                             track_expiry=False,
                             track_mfg=False)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_adj()

    def _load_batches(self):
        rows = get_batches(self.db_name, self.edit_code)
        self.batch_table.setRowCount(0)
        today = date.today()
        for bn, qty, mfg, exp, price, sup, rec in rows:
            r = self.batch_table.rowCount(); self.batch_table.insertRow(r)
            for col, val in enumerate([bn, qty, mfg, exp, f"₹{price:.2f}", sup or ""]):
                item = QTableWidgetItem(str(val or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3 and exp:
                    try:
                        diff = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
                        if diff < 0:
                            item.setBackground(QBrush(QColor(C["danger_tint"])))
                            item.setForeground(QBrush(QColor(C["accent"])))
                        elif diff <= 30:
                            item.setBackground(QBrush(QColor(C["warning_tint"])))
                            item.setForeground(QBrush(QColor(C["warning"])))
                    except Exception:
                        pass
                self.batch_table.setItem(r, col, item)

    def _load_adj(self):
        rows = get_stock_adjustments(self.db_name, self.edit_code)
        self.adj_table.setRowCount(0)
        for adj_type, qty, reason, adj_date, by, note in rows:
            r = self.adj_table.rowCount(); self.adj_table.insertRow(r)
            for col, val in enumerate([f"{'▲' if adj_type == 'IN' else '▼'} {adj_type}", qty, reason, adj_date, by]):
                item = QTableWidgetItem(str(val or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setForeground(QBrush(QColor(C["success"] if adj_type == "IN" else C["accent"])))
                self.adj_table.setItem(r, col, item)

    # ── TAB 4: SUPPLIER ───────────────────────────────────

    def _build_tab_supplier(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

        # ── Supplier search / select / create section ─────────────────────────
        sec_top, g_top = make_section("Supplier", "\U0001f69a")
        g_top.setColumnStretch(1, 1); g_top.setColumnStretch(3, 1)
        g_top.setHorizontalSpacing(12); g_top.setVerticalSpacing(10)

        # Hybrid search combobox
        self.f_supplier_name = QComboBox(); self.f_supplier_name.setEditable(True)
        self.f_supplier_name.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.f_supplier_name.setFixedHeight(38)
        self.f_supplier_name.setPlaceholderText("Search or type supplier name…")
        self._sup_names_cache = get_all_supplier_names(self.db_name)
        self.f_supplier_name.addItems([""] + self._sup_names_cache)
        _apply_combo_delegate(self.f_supplier_name)

        # Status label (shows: existing / will create new)
        self._sup_status_lbl = QLabel("")
        self._sup_status_lbl.setStyleSheet(
            "font-size:11px;background:transparent;border:none;padding:2px 0;")

        add_field(g_top, 0, 0, "Supplier Name *", self.f_supplier_name, span=2)
        g_top.addWidget(self._sup_status_lbl, 1, 1, 1, 3)

        # ── Inline "Create New Supplier" fields (hidden until needed) ──────────
        self._new_sup_frame = QFrame()
        self._new_sup_frame.setStyleSheet(
            f"QFrame{{background:#f0f9ff;border:1.5px solid #bae6fd;border-radius:10px;}}")
        nsf_lay = QVBoxLayout(self._new_sup_frame)
        nsf_lay.setContentsMargins(14, 12, 14, 12); nsf_lay.setSpacing(10)

        _new_sup_title = QLabel("\u2795  Create New Supplier")
        _new_sup_title.setStyleSheet(
            "font-size:12px;font-weight:700;color:#0369a1;background:transparent;border:none;")
        nsf_lay.addWidget(_new_sup_title)

        nsf_grid = QGridLayout(); nsf_grid.setSpacing(10)
        nsf_grid.setColumnStretch(1, 1); nsf_grid.setColumnStretch(3, 1)

        self.f_new_sup_phone   = QLineEdit(); self.f_new_sup_phone.setPlaceholderText("+91 98765 43210")
        self.f_new_sup_phone.setFixedHeight(38)
        self.f_new_sup_email   = QLineEdit(); self.f_new_sup_email.setPlaceholderText("supplier@example.com")
        self.f_new_sup_email.setFixedHeight(38)
        self.f_new_sup_gstin   = QLineEdit(); self.f_new_sup_gstin.setPlaceholderText("29AAAAA0000A1Z5")
        self.f_new_sup_gstin.setFixedHeight(38)
        self.f_new_sup_address = QLineEdit(); self.f_new_sup_address.setPlaceholderText("Street, City, State")
        self.f_new_sup_address.setFixedHeight(38)

        def _nsf_lbl(txt): return QLabel(txt, styleSheet=LABEL_SS)
        nsf_grid.addWidget(_nsf_lbl("Phone"),   0, 0); nsf_grid.addWidget(self.f_new_sup_phone,   0, 1)
        nsf_grid.addWidget(_nsf_lbl("Email"),   0, 2); nsf_grid.addWidget(self.f_new_sup_email,   0, 3)
        nsf_grid.addWidget(_nsf_lbl("GSTIN"),   1, 0); nsf_grid.addWidget(self.f_new_sup_gstin,   1, 1)
        nsf_grid.addWidget(_nsf_lbl("Address"), 1, 2); nsf_grid.addWidget(self.f_new_sup_address, 1, 3)
        nsf_lay.addLayout(nsf_grid)
        self._new_sup_frame.setVisible(False)
        lay.addWidget(sec_top)
        lay.addWidget(self._new_sup_frame)

        # ── Supplier-Product relationship fields ──────────────────────────────
        sec2, g2 = make_section("Supplier Details for This Product", "\U0001f4cb")
        g2.setColumnStretch(1, 1); g2.setColumnStretch(3, 1)
        g2.setHorizontalSpacing(12); g2.setVerticalSpacing(10)

        # Legacy fields kept for _collect/_save compatibility
        self.f_supplier_phone = QLineEdit(); self.f_supplier_phone.hide()
        self.f_supplier_email = QLineEdit(); self.f_supplier_email.hide()
        self.f_supplier_gstin = QLineEdit(); self.f_supplier_gstin.hide()

        self.f_supplier_code = QLineEdit(); self.f_supplier_code.setPlaceholderText("Supplier's product SKU/code")
        self.f_supplier_code.setFixedHeight(38)
        self.f_last_purchase = price_spin()
        self.f_lead_time     = QSpinBox(); self.f_lead_time.setRange(0, 365)
        self.f_lead_time.setSuffix(" days"); self.f_lead_time.setFixedHeight(38)
        self.f_lead_time.setStyleSheet(_NO_ARROW)

        self.f_sup_moq = QSpinBox(); self.f_sup_moq.setRange(1, 99999)
        self.f_sup_moq.setFixedHeight(38); self.f_sup_moq.setStyleSheet(_NO_ARROW)
        self.f_sup_default_qty = QSpinBox(); self.f_sup_default_qty.setRange(1, 99999)
        self.f_sup_default_qty.setFixedHeight(38); self.f_sup_default_qty.setStyleSheet(_NO_ARROW)

        self.f_is_primary = ToggleSwitch("Preferred supplier  —  use for auto-PO")
        self.f_is_primary.setChecked(True)

        r2 = 0
        add_field(g2, r2, 0, "Supplier SKU",       self.f_supplier_code)
        add_field(g2, r2, 2, "Last Purchase Price", self.f_last_purchase)
        r2 += 1
        add_field(g2, r2, 0, "MOQ",                 self.f_sup_moq,        hint="Min order quantity")
        add_field(g2, r2, 2, "Default Order Qty",   self.f_sup_default_qty)
        r2 += 1
        add_field(g2, r2, 0, "Lead Time",           self.f_lead_time,      hint="Days to restock")
        r2 += 1
        g2.addWidget(self.f_is_primary, r2, 0, 1, 4)
        lay.addWidget(sec2)

        # ── Linked Suppliers list (shows existing links after save) ───────────
        self._sec_linked, g_linked = make_section("Linked Suppliers", "\U0001f517")
        self._linked_list = QWidget(); self._linked_list.setStyleSheet("background:transparent;")
        self._linked_vlay = QVBoxLayout(self._linked_list)
        self._linked_vlay.setContentsMargins(4, 4, 4, 4); self._linked_vlay.setSpacing(6)
        g_linked.addWidget(self._linked_list, 0, 0, 1, 4)
        lay.addWidget(self._sec_linked)

        # ── Dimensions ───────────────────────────────────────────────────────
        sec3, g3 = make_section("Physical Dimensions", "\U0001f4d0")
        def dspin(s):
            w = QDoubleSpinBox(); w.setRange(0, 9999); w.setDecimals(3); w.setSuffix(s)
            w.setFixedHeight(38); w.setStyleSheet(_NO_ARROW)
            return w
        self.f_weight = dspin(" kg"); self.f_length = dspin(" cm")
        self.f_width  = dspin(" cm"); self.f_height = dspin(" cm")
        r3 = 0
        add_field(g3, r3, 0, "Weight", self.f_weight); add_field(g3, r3, 2, "Length", self.f_length); r3 += 1
        add_field(g3, r3, 0, "Width",  self.f_width);  add_field(g3, r3, 2, "Height", self.f_height)
        lay.addWidget(sec3)
        lay.addStretch()
        self.tabs.addTab(page, "\U0001f69a  Supplier")

        # ── Wire supplier search ──────────────────────────────────────────────
        self.f_supplier_name.currentTextChanged.connect(self._on_supplier_typed)
        self._refresh_linked_suppliers()

    def _on_supplier_typed(self, text):
        """Live search — match existing suppliers or offer to create new."""
        text = text.strip()
        if not text:
            self._new_sup_frame.setVisible(False)
            self._sup_status_lbl.setText("")
            return

        names = self._sup_names_cache
        match = next((n for n in names if n.lower() == text.lower()), None)

        if match:
            # Existing supplier found — auto-fill phone/email/gstin from DB
            row = get_supplier_by_name(self.db_name, match)
            if row:
                self.f_supplier_phone.setText(row.get("phone",""))
                self.f_supplier_email.setText(row.get("email",""))
                self.f_supplier_gstin.setText(row.get("gstin",""))
            self._new_sup_frame.setVisible(False)
            self._sup_status_lbl.setText(
                f"\u2705  Existing supplier selected")
            self._sup_status_lbl.setStyleSheet(
                "font-size:11px;color:#16a34a;background:transparent;border:none;")
        else:
            # No match — show create-new panel
            self._new_sup_frame.setVisible(True)
            self._sup_status_lbl.setText(
                "\u2795  New supplier — fill details below to create")
            self._sup_status_lbl.setStyleSheet(
                "font-size:11px;color:#0369a1;background:transparent;border:none;")

    def _refresh_linked_suppliers(self):
        """Populate the Linked Suppliers section from DB."""
        # Clear existing
        while self._linked_vlay.count():
            item = self._linked_vlay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        product_code = getattr(self, '_edit_id', None)
        if not product_code:
            empty = QLabel("Save the product first to see linked suppliers.")
            empty.setStyleSheet(
                f"font-size:12px;color:{C['text3']};background:transparent;border:none;")
            self._linked_vlay.addWidget(empty)
            self._sec_linked.setVisible(False)
            return

        rows = get_product_suppliers(self.db_name, product_code)
        if not rows:
            self._sec_linked.setVisible(False)
            return

        self._sec_linked.setVisible(True)
        for r in rows:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:#ffffff;border:1px solid {C['border']};"
                f"border-radius:8px;}}")
            cl = QHBoxLayout(card); cl.setContentsMargins(12, 10, 12, 10); cl.setSpacing(14)

            left = QVBoxLayout(); left.setSpacing(2)
            name_lbl = QLabel(r.get("name",""))
            name_lbl.setStyleSheet(
                f"font-size:13px;font-weight:700;color:{C['text']};background:transparent;border:none;")
            meta = []
            if r.get("phone"): meta.append(r["phone"])
            if r.get("supplier_product_code"): meta.append(f"SKU: {r['supplier_product_code']}")
            if r.get("lead_time_days"): meta.append(f"Lead: {r['lead_time_days']}d")
            meta_lbl = QLabel("  \u2022  ".join(meta) or "No details")
            meta_lbl.setStyleSheet(
                f"font-size:11px;color:{C['text3']};background:transparent;border:none;")
            left.addWidget(name_lbl); left.addWidget(meta_lbl)
            cl.addLayout(left, 1)

            if r.get("is_primary"):
                prim = QLabel("\u2605  Primary")
                prim.setStyleSheet(
                    "font-size:11px;font-weight:700;color:#16a34a;"
                    "background:#f0fdf4;border:1px solid #bbf7d0;"
                    "border-radius:5px;padding:2px 8px;")
                cl.addWidget(prim)

            price_lbl = QLabel(f"\u20b9 {r.get('unit_price', 0):.2f}")
            price_lbl.setStyleSheet(
                f"font-size:13px;font-weight:700;color:{C['text']};background:transparent;border:none;")
            cl.addWidget(price_lbl)
            self._linked_vlay.addWidget(card)

    def _save_supplier_link(self, product_code):
        """Called after product save — create supplier if new, then link to product."""
        name = self.f_supplier_name.currentText().strip()
        if self.f_supplier_name.isEditable() and self.f_supplier_name.lineEdit():
            name = self.f_supplier_name.lineEdit().text().strip() or name
        if not name:
            return

        # Resolve or create supplier
        row = get_supplier_by_name(self.db_name, name)
        if row:
            sup_code = row["code"]
        else:
            # Create new supplier from inline fields
            sup_code = create_supplier(
                self.db_name, name,
                phone   = self.f_new_sup_phone.text().strip(),
                email   = self.f_new_sup_email.text().strip(),
                gstin   = self.f_new_sup_gstin.text().strip(),
                address = self.f_new_sup_address.text().strip(),
            )
            if not sup_code:
                return
            # Refresh cache
            self._sup_names_cache = get_all_supplier_names(self.db_name)

        # Save product-supplier relationship
        save_product_supplier(
            self.db_name, product_code, sup_code,
            sup_sku     = self.f_supplier_code.text().strip(),
            unit_price  = self.f_last_purchase.value(),
            moq         = self.f_sup_moq.value(),
            lead_days   = self.f_lead_time.value(),
            is_primary  = int(self.f_is_primary.isChecked()),
            default_qty = self.f_sup_default_qty.value(),
        )
        self._refresh_linked_suppliers()


    # ── TAB 5: COMPLIANCE ─────────────────────────────────

    # ── helpers for label designer ───────────────────────
    # ── TAB 5: LABEL PRINT ────────────────────────────────
    def _build_tab_compliance(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(0)

        # ── Hidden stubs (keep _collect/_save working) ────
        self.f_fssai      = QLineEdit();  self.f_fssai.hide()
        self.f_drug_lic   = QLineEdit();  self.f_drug_lic.hide()
        self.f_is_sched   = ToggleSwitch();  self.f_is_sched.hide()
        self.f_sched_type = QComboBox();  self.f_sched_type.hide()
        self.f_einvoice   = ToggleSwitch();  self.f_einvoice.hide()
        self.f_eway       = ToggleSwitch();  self.f_eway.hide()
        self.f_print_mrp  = ToggleSwitch();  self.f_print_mrp.setChecked(True); self.f_print_mrp.hide()
        self.f_print_hsn  = ToggleSwitch();  self.f_print_hsn.setChecked(True); self.f_print_hsn.hide()
        self.f_label_fmt  = QComboBox();  self.f_label_fmt.hide()
        self.f_lbl_paper     = QComboBox(); self.f_lbl_paper.hide()
        self.f_lbl_columns   = QSpinBox();  self.f_lbl_columns.hide()
        self.f_lbl_height    = QDoubleSpinBox(); self.f_lbl_height.hide()
        self.f_lbl_gap       = QDoubleSpinBox(); self.f_lbl_gap.hide()
        self.f_lbl_mar_l     = QDoubleSpinBox(); self.f_lbl_mar_l.hide()
        self.f_lbl_mar_r     = QDoubleSpinBox(); self.f_lbl_mar_r.hide()
        self.f_lbl_dpi       = QComboBox(); self.f_lbl_dpi.hide()
        self.f_lbl_show_name     = ToggleSwitch(); self.f_lbl_show_name.hide()
        self.f_lbl_show_barcode  = ToggleSwitch(); self.f_lbl_show_barcode.hide()
        self.f_lbl_show_mrp      = ToggleSwitch(); self.f_lbl_show_mrp.hide()
        self.f_lbl_show_price    = ToggleSwitch(); self.f_lbl_show_price.hide()
        self.f_lbl_show_mrp_lbl  = ToggleSwitch(); self.f_lbl_show_mrp_lbl.hide()
        self.f_lbl_show_hsn      = ToggleSwitch(); self.f_lbl_show_hsn.hide()
        self.f_lbl_show_alias    = ToggleSwitch(); self.f_lbl_show_alias.hide()
        self.f_lbl_show_itemcode = ToggleSwitch(); self.f_lbl_show_itemcode.hide()
        self.f_lbl_show_gst      = ToggleSwitch(); self.f_lbl_show_gst.hide()
        self.f_lbl_show_brand    = ToggleSwitch(); self.f_lbl_show_brand.hide()
        self.f_lbl_printer       = QComboBox(); self.f_lbl_printer.hide()
        self._lbl_preset         = QComboBox(); self._lbl_preset.hide()
        self._lbl_info           = QLabel(); self._lbl_info.hide()
        self._qz_status          = QLabel(); self._qz_status.hide()

        # ── Coming Soon UI ─────────────────────────────────
        lay.addStretch(1)

        icon_lbl = QLabel("🏷️")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        icon_lbl.setStyleSheet("font-size:52px;background:transparent;border:none;")
        lay.addWidget(icon_lbl)

        lay.addSpacing(12)

        title_lbl = QLabel("Label Print")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title_lbl.setStyleSheet(
            "font-size:22px;font-weight:700;color:#1d1d1f;"
            "background:transparent;border:none;")
        lay.addWidget(title_lbl)

        lay.addSpacing(8)

        sub_lbl = QLabel("Coming Soon")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub_lbl.setStyleSheet(
            "font-size:15px;font-weight:600;color:#FA2D48;"
            "background:transparent;border:none;letter-spacing:1px;")
        lay.addWidget(sub_lbl)

        lay.addSpacing(14)

        desc_lbl = QLabel(
            "A full label designer with barcode printing,\n"
            "custom layouts, and QZ Tray integration\n"
            "will be available in a future update."
        )
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "font-size:13px;color:#6e6e73;"
            "background:transparent;border:none;line-height:1.6;")
        lay.addWidget(desc_lbl)

        lay.addStretch(2)
        self.tabs.addTab(page, "\U0001f3f7\ufe0f  Label Print")


    # ── TAB 6: SALES HISTORY ──────────────────────────────

    def _build_tab_history(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

        kpi_row = QHBoxLayout(); kpi_row.setSpacing(12)
        def kpi(lbl_text, attr):
            card = QFrame()
            card.setStyleSheet(f"QFrame{{background:{C['bg_white']};border:1px solid {C['border']};border-radius:12px;}}")
            cl = QVBoxLayout(card); cl.setContentsMargins(14, 12, 14, 12); cl.setSpacing(4)
            t = QLabel(lbl_text)
            t.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;border:none;")
            v = QLabel("—")
            v.setStyleSheet(f"font-size:18px;font-weight:700;color:{C['text']};background:transparent;border:none;")
            cl.addWidget(t); cl.addWidget(v)
            setattr(self, attr, v)
            return card
        kpi_row.addWidget(kpi("Total Units Sold", "lbl_total_sold"))
        kpi_row.addWidget(kpi("Total Revenue",    "lbl_total_rev"))
        kpi_row.addWidget(kpi("Return Count",     "lbl_returns"))
        kpi_row.addWidget(kpi("Invoice Count",    "lbl_inv_count"))
        lay.addLayout(kpi_row)

        sec, g = make_section("Sales Stats", "📊")
        self.lbl_last_sold = ro_label("—")
        self.lbl_avg_sp    = ro_label("—")
        add_field(g, 0, 0, "Last Sold Date",    self.lbl_last_sold)
        add_field(g, 0, 2, "Avg Selling Price", self.lbl_avg_sp)
        lay.addWidget(sec)

        ph_frame = QFrame()
        ph_frame.setStyleSheet(f"QFrame{{background:{C['bg_white']};border:1px solid {C['border']};border-radius:12px;}}")
        ph_lay = QVBoxLayout(ph_frame); ph_lay.setContentsMargins(18, 14, 18, 14); ph_lay.setSpacing(8)
        ph_hdr = QLabel("📈  Price History"); ph_hdr.setStyleSheet(SEC_HDR_SS)
        ph_lay.addWidget(ph_hdr)
        self.price_hist_table = mini_table(["Date", "Purchase", "Selling", "MRP", "Changed By"], height=160)
        ph_lay.addWidget(self.price_hist_table)
        lay.addWidget(ph_frame)

        hint = QLabel("💡  Sales history populates in Edit mode after product is saved and sold.")
        hint.setStyleSheet(f"color:{C['text3']};font-size:12px;padding:8px;border:none;background:transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        lay.addStretch()
        self.tabs.addTab(page, "📊  Sales History")

    def _load_history(self):
        if not self.edit_code: return
        p = get_product_full(self.db_name, self.edit_code) or {}
        self.lbl_total_sold.setText(str(p.get("total_qty_sold", 0)))
        self.lbl_total_rev.setText(f"₹{float(p.get('total_revenue', 0)):,.0f}")
        self.lbl_returns.setText(str(p.get("return_count", 0)))
        self.lbl_inv_count.setText(str(p.get("sale_count", 0)))
        self.lbl_last_sold.setText(p.get("last_sold_date", "—") or "—")
        self.lbl_avg_sp.setText(f"₹{float(p.get('selling_price', 0)):,.2f}")
        rows = get_price_history(self.db_name, self.edit_code)
        self.price_hist_table.setRowCount(0)
        for pur, sell, mrp, ch_at, ch_by, note in rows:
            r = self.price_hist_table.rowCount(); self.price_hist_table.insertRow(r)
            for col, val in enumerate([ch_at, f"₹{pur:.2f}", f"₹{sell:.2f}", f"₹{mrp:.2f}", ch_by]):
                item = QTableWidgetItem(str(val or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.price_hist_table.setItem(r, col, item)

    # ── TAB 7: AUDIT ──────────────────────────────────────

    def _build_tab_audit(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

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
        hint.setStyleSheet(f"color:{C['text3']};font-size:12px;padding:8px;border:none;background:transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        lay.addStretch()
        self.tabs.addTab(page, "🗃️  Audit")

    def _load_audit(self):
        if not self.edit_code: return
        p = self.prod
        self.lbl_created_at.setText(p.get("created_at", "—") or "—")
        self.lbl_created_by.setText(p.get("created_by", "—") or "—")
        self.lbl_updated_at.setText(p.get("updated_at", "—") or "—")
        self.lbl_updated_by.setText(p.get("updated_by", "—") or "—")
        self.lbl_is_deleted.setText("Yes ⚠️" if p.get("is_deleted") else "No ✅")
        self.lbl_deleted_at.setText(p.get("deleted_at", "—") or "—")

    # ── Image ──────────────────────────────────────────────

    def _upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            with open(path, "rb") as f:
                self._image_blob = f.read()
            px = QPixmap(path)
            if not px.isNull():
                self.img_label.setPixmap(
                    px.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation))
                self.img_label.setText("")

    def _clear_image(self):
        self._image_blob = b""; self.img_label.clear(); self.img_label.setText("No Image")

    # ── Load / Reset / Populate ────────────────────────────

    def load_for_add(self):
        self.edit_code = None; self.prod = {}
        self._title_lbl.setText("Add Product"); self._btn_save.setText("💾  Save Product")
        self._reset_fields()
        self.f_item_code.setText(get_next_item_code(self.db_name))
        self.f_item_code.setReadOnly(True)
        self.f_auto_barcode.setVisible(True); self.f_auto_barcode.setChecked(False)
        self.f_barcode.setReadOnly(False)
        self._toggle_variants(False)
        self._toggle_color_variants(False)
        self._toggle_custom_variants(False)
        self._load_purchase_log()
        self.batch_frame.setVisible(False); self.adj_frame.setVisible(False)
        self.tabs.setCurrentIndex(0)

    def load_for_edit(self, item_code):
        self.edit_code = item_code
        self.prod = get_product_full(self.db_name, item_code) or {}
        self._title_lbl.setText(f"Edit — {item_code}"); self._btn_save.setText("💾  Update Product")
        self._reset_fields(); self._populate()
        saved_colors = get_product_variants(
            self.db_name, item_code, COLOR_STORAGE_GROUP
        )
        saved_custom = get_product_variants(
            self.db_name, item_code, CUSTOM_STORAGE_GROUP
        )
        saved_variants = get_product_variants(self.db_name, item_code)
        if saved_custom or self.prod.get("variant_type") == CUSTOM_STORAGE_GROUP:
            self._custom_values = [name for _group, name in saved_custom]
            self.f_has_custom_variants.setChecked(True)
        elif saved_colors or self.prod.get("variant_type") == COLOR_STORAGE_GROUP:
            self.f_has_color_variants.setChecked(True)
        elif saved_variants or bool(self.prod.get("has_variants")):
            age_category = self.prod.get("variant_type") or "Generic"
            age_category = LEGACY_VARIANT_GROUPS.get(age_category, age_category)
            if age_category not in AGE_CATEGORIES:
                age_category = "Generic"
            idx = self.f_variant_type.findText(age_category)
            if idx >= 0:
                self.f_variant_type.setCurrentIndex(idx)
            radio = self._variant_radios.get(age_category)
            if radio:
                radio.setChecked(True)
            self.f_has_variants.setChecked(True)
        self.f_item_code.setReadOnly(True)
        self.f_auto_barcode.setVisible(False); self.f_barcode.setReadOnly(False)
        self._toggle_variants(self.f_has_variants.isChecked())
        self._toggle_color_variants(self.f_has_color_variants.isChecked())
        self._toggle_custom_variants(self.f_has_custom_variants.isChecked())
        self._update_tracking_fields(); self.adj_frame.setVisible(False)
        self._load_batches(); self._load_purchase_log(item_code)
        self._load_history(); self._load_audit()
        self.tabs.setCurrentIndex(0)

    def _toggle_barcode(self, state):
        if state:
            self.f_barcode.setText(get_next_ean13(self.db_name))
            self.f_barcode.setReadOnly(True)
        else:
            self.f_barcode.clear()
            self.f_barcode.setReadOnly(False)

    def _reset_fields(self):
        self._image_blob = b""; self.img_label.clear(); self.img_label.setText("No Image")
        if hasattr(self, "_variant_pending"):
            self._variant_pending.clear()
            self._variant_drafts.clear()
            self._variant_locked.clear()
            self._variant_current_group = VARIANT_STORAGE_GROUP
            self._custom_values.clear()
        for w in self.findChildren(QLineEdit):
            if not w.isReadOnly(): w.clear()
        for w in self.findChildren(QTextEdit):      w.clear()
        for w in self.findChildren(QSpinBox):       w.setValue(w.minimum())
        for w in self.findChildren(QDoubleSpinBox): w.setValue(0)
        for w in self.findChildren(QComboBox):      w.setCurrentIndex(0)
        for w in self.findChildren(QCheckBox):      w.setChecked(False)
        self.f_pack_size.setValue(1); self.f_min_order_qty.setValue(1)
        self.f_expiry_alert.setValue(30); self.f_returnable.setChecked(True)
        self.f_print_mrp.setChecked(True); self.f_print_hsn.setChecked(True)
        self.f_is_primary.setChecked(True)
        self.f_mfg_date.setDate(QDate.currentDate())
        self.f_expiry_date.setDate(QDate.currentDate().addYears(1))
        self.f_purchase_date.setDate(QDate.currentDate())
        self.f_purchase_date.clear()
        self.purchase_log_table.setRowCount(0)
        if hasattr(self, "_variant_radios"):
            self._variant_radios["Generic"].setChecked(True)
        self._update_tracking_fields()
        self.f_margin.blockSignals(True)
        self.f_margin.setValue(0.0)
        self.f_margin.blockSignals(False)
        self.lbl_markup.setText("—")
        self.f_profit.blockSignals(True)
        self.f_profit.setValue(0.0)
        self.f_profit.blockSignals(False)

    def _populate(self):
        p = self.prod
        def sv(w, key, default=""):
            val = p.get(key, default)
            if val is None: val = default
            if isinstance(w, QLineEdit):
                w.setText(str(val))
            elif isinstance(w, QComboBox):
                idx = w.findText(str(val))
                if idx >= 0: w.setCurrentIndex(idx)
                else: w.setEditText(str(val))
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                try: w.setValue(float(val))
                except: pass
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(val))
            elif isinstance(w, QTextEdit):
                w.setPlainText(str(val))
            elif isinstance(w, QDateEdit):
                d = QDate.fromString(str(val), "yyyy-MM-dd")
                if d.isValid(): w.setDate(d)
            elif isinstance(w, QLabel):
                w.setText(str(val) if val else "—")

        # Basic
        sv(self.f_item_code, "item_code");    sv(self.f_sku, "sku")
        sv(self.f_name, "name");              sv(self.f_alias, "alias_names")
        sv(self.f_use_alias_bill, "use_alias_in_billing")
        sv(self.f_barcode, "barcode");        sv(self.f_hsn, "hsn_code")
        sv(self.f_prod_type, "product_type"); sv(self.f_tax_cat, "tax_category")
        sv(self.f_product_group, "product_group"); sv(self.f_category, "category")
        sv(self.f_sub_cat, "sub_category");   sv(self.f_brand, "brand")
        sv(self.f_manufacturer, "manufacturer"); sv(self.f_country, "country_of_origin")
        sv(self.f_unit, "unit");              sv(self.f_pack_size, "pack_size", 1)
        sv(self.f_meter, "meter");            sv(self.f_shelf_life, "shelf_life_days")
        sv(self.f_storage, "storage_condition"); sv(self.f_tags, "tags")
        sv(self.f_desc, "description");       sv(self.f_notes, "internal_notes")
        sv(self.f_status, "status")
        img = p.get("image")
        if isinstance(img, (bytes, bytearray)) and img:
            self._image_blob = img; px = QPixmap(); px.loadFromData(img)
            if not px.isNull():
                self.img_label.setPixmap(
                    px.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation))
                self.img_label.setText("")
        # Pricing
        # Block discount/sell signals during load to prevent cascade recalculation
        for _w in (self.f_mrp, self.f_selling_price, self.f_retail_price,
                   self.f_discount_pct, self.f_discount_val, self.f_purchase_price):
            _w.blockSignals(True)
        sv(self.f_mrp, "mrp");                      sv(self.f_purchase_price, "purchase_price")
        sv(self.f_selling_price, "selling_price");   sv(self.f_retail_price, "retail_price")
        sv(self.f_wholesale_price, "wholesale_price"); sv(self.f_dealer_price, "dealer_price")
        sv(self.f_min_selling_price, "min_selling_price"); sv(self.f_special_price, "special_price")
        sv(self.f_sp_from, "special_price_from");    sv(self.f_sp_to, "special_price_to")
        sv(self.f_discount_pct, "discount_pct");     sv(self.f_discount_val, "discount_val")
        sv(self.f_margin, "margin_pct")
        sv(self.f_purchase_gst, "purchase_gst");     sv(self.f_tax_inclusive, "tax_inclusive")
        for _w in (self.f_mrp, self.f_selling_price, self.f_retail_price,
                   self.f_discount_pct, self.f_discount_val, self.f_purchase_price):
            _w.blockSignals(False)
        sv(self.f_gst_rate, "gst_rate");             sv(self.f_igst_rate, "igst_rate")
        sv(self.f_tax_type, "tax_type");             sv(self.f_cess_pct, "cess_pct")
        sv(self.f_tcs, "tcs_applicable");            sv(self.f_gst_ex, "gst_exemption_reason")
        self._update_purchase_actual()
        self._update_margin()
        self._update_gst_panel()
        # Inventory
        sv(self.f_opening_stock, "opening_stock");   sv(self.f_reorder_level, "reorder_level")
        sv(self.f_safety_stock, "safety_stock");     sv(self.f_reorder_qty, "reorder_qty")
        sv(self.f_min_order_qty, "min_order_qty", 1); sv(self.f_max_stock, "max_stock")
        sv(self.f_auto_reorder, "auto_reorder");     sv(self.f_allow_neg, "allow_neg_stock")
        sv(self.f_returnable, "is_returnable");      sv(self.f_warehouse, "warehouse")
        sv(self.f_rack, "rack_location");            sv(self.f_bin, "bin_location")
        sv(self.f_track_batch, "track_batch");       sv(self.f_track_expiry, "track_expiry")
        sv(self.f_track_mfg, "track_mfg");           sv(self.f_track_serial, "track_serial")
        sv(self.f_mfg_date, "mfg_date")
        sv(self.f_expiry_date, "expiry_date");       sv(self.f_expiry_alert, "expiry_alert_days", 30)
        self._update_tracking_fields()
        self._calc_shelf()
        cur = p.get("stock", 0); res = p.get("reserved_stock", 0); dam = p.get("damaged_stock", 0)
        self.lbl_available.setText(str(max(0, (cur or 0) - (res or 0) - (dam or 0))))
        pp = p.get("purchase_price", 0)
        self.lbl_stock_val.setText(f"₹{(cur or 0) * (pp or 0):,.2f}" if pp else "—")
        sold = p.get("total_qty_sold", 0)
        if sold and sold > 0:
            daily = sold / 30; days = int((cur or 0) / daily) if daily > 0 else 0
            col = C["accent"] if days < 7 else (C["warning"] if days < 15 else C["success"])
            self.lbl_days_left.setText(f"{days} days")
            self.lbl_days_left.setStyleSheet(
                f"background:{C['bg_light']};border:1px solid {C['border']};border-radius:8px;"
                f"padding:6px 10px;font-size:13px;font-weight:700;color:{col};min-height:34px;")
        # Supplier
        sv(self.f_supplier_name, "supplier_name");   sv(self.f_supplier_code, "supplier_code")
        sv(self.f_supplier_phone, "supplier_phone"); sv(self.f_supplier_email, "supplier_email")
        sv(self.f_supplier_gstin, "supplier_gstin"); sv(self.f_lead_time, "lead_time_days")
        sv(self.f_last_purchase, "last_purchase_price")
        sv(self.f_weight, "weight_kg");  sv(self.f_length, "length_cm")
        sv(self.f_width, "width_cm");   sv(self.f_height, "height_cm")
        if p.get("variant_type") not in (COLOR_STORAGE_GROUP, CUSTOM_STORAGE_GROUP):
            sv(self.f_has_variants, "has_variants")
            sv(self.f_variant_type, "variant_type")
        # Compliance
        sv(self.f_fssai, "fssai_number");     sv(self.f_drug_lic, "drug_license_no")
        sv(self.f_is_sched, "is_scheduled_drug"); sv(self.f_sched_type, "schedule_type")
        sv(self.f_einvoice, "e_invoice_applicable"); sv(self.f_eway, "e_way_bill_applicable")
        sv(self.f_print_mrp, "print_mrp_on_invoice"); sv(self.f_print_hsn, "print_hsn_on_invoice")
        sv(self.f_label_fmt, "label_format")

    def _collect(self) -> dict:
        gst  = self.f_gst_rate.currentText().split("—")[0].strip().split(" ")[0]
        igst = self.f_igst_rate.currentText().split("—")[0].strip().split(" ")[0]
        if (
            hasattr(self, "f_has_variants")
            and (
                self.f_has_variants.isChecked()
                or self.f_has_color_variants.isChecked()
                or self.f_has_custom_variants.isChecked()
            )
        ):
            self._sync_variant_total()
        return {
            "item_code":             self.f_item_code.text().strip(),
            "sku":                   self.f_sku.text().strip(),
            "name":                  self.f_name.text().strip(),
            "alias_names":           self.f_alias.text().strip(),
            "use_alias_in_billing":   int(self.f_use_alias_bill.isChecked()),
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
            "margin_pct":            self.f_margin.value(),
            "discount_val":          self.f_discount_val.value(),
            "purchase_gst":          self.f_purchase_gst.currentText(),
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
            "track_batch":           0,
            "track_expiry":          0,
            "track_mfg":             0,
            "track_serial":          0,
            "mfg_date":              "",
            "expiry_date":           "",
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
            "has_variants":          int(
                self.f_has_variants.isChecked()
                or self.f_has_color_variants.isChecked()
                or self.f_has_custom_variants.isChecked()
            ),
            "variant_type":          (
                CUSTOM_STORAGE_GROUP if self.f_has_custom_variants.isChecked()
                else (
                    COLOR_STORAGE_GROUP if self.f_has_color_variants.isChecked()
                    else self.f_variant_type.currentText().strip()
                )
            ),
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

    def _save(self):
        data = self._collect()
        stock_update_qty = self._stock_update_qty()
        if not data["name"]:
            QMessageBox.warning(self, "Validation", "Product name is required.")
            self.tabs.setCurrentIndex(0); self.f_name.setFocus(); return
        if not data["item_code"]:
            QMessageBox.warning(self, "Validation", "Product no is required.")
            self.tabs.setCurrentIndex(0); self.f_item_code.setFocus(); return
        if not data["barcode"]:
            QMessageBox.warning(self, "Validation", "Barcode / EAN is required.")
            self.tabs.setCurrentIndex(0); self.f_barcode.setFocus(); return
        if data["selling_price"] <= 0:
            QMessageBox.warning(self, "Validation", "Selling price must be > 0.")
            self.tabs.setCurrentIndex(1); self.f_selling_price.setFocus(); return
        if self.f_has_variants.isChecked() and self._variant_radio_group.checkedButton() is None:
            QMessageBox.warning(self, "Validation", "Age Category is required.")
            self.tabs.setCurrentIndex(2); return
        if self.f_has_custom_variants.isChecked() and not self._custom_values:
            QMessageBox.warning(
                self, "Validation", "Add at least one custom variant."
            )
            self.tabs.setCurrentIndex(2)
            self.f_custom_variant.setFocus()
            return
        if stock_update_qty > 0 and not self.f_purchase_invoice.text().strip():
            QMessageBox.warning(self, "Validation", "Purchase invoice number is required for stock updates.")
            self.tabs.setCurrentIndex(2); self.f_purchase_invoice.setFocus(); return
        if stock_update_qty > 0 and not self.f_purchase_date.text().strip():
            QMessageBox.warning(self, "Validation", "Date of purchase is required for stock updates.")
            self.tabs.setCurrentIndex(2); self.f_purchase_date.setFocus(); return
        if data["mrp"] > 0 and data["selling_price"] > data["mrp"]:
            if QMessageBox.question(self, "Warning",
                f"Selling price ₹{data['selling_price']:.2f} exceeds MRP ₹{data['mrp']:.2f}.\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.No:
                return
        if self.edit_code:
            d = dict(data); d.pop("item_code", None); d.pop("opening_stock", None)
            update_product(self.db_name, self.edit_code, d, self.current_user)
            if (
                self.f_has_variants.isChecked()
                or self.f_has_color_variants.isChecked()
                or self.f_has_custom_variants.isChecked()
            ):
                color_mode = self.f_has_color_variants.isChecked()
                custom_mode = self.f_has_custom_variants.isChecked()
                storage_group = (
                    CUSTOM_STORAGE_GROUP if custom_mode
                    else COLOR_STORAGE_GROUP if color_mode
                    else VARIANT_STORAGE_GROUP
                )
                delete_other_variant_mode(self.db_name, self.edit_code, storage_group)
                total = save_product_variants(
                    self.db_name, self.edit_code,
                    CUSTOM_STORAGE_GROUP if custom_mode
                    else COLOR_STORAGE_GROUP if color_mode
                    else self.f_variant_type.currentText().strip(),
                    self._custom_rows() if custom_mode
                    else self._color_rows() if color_mode
                    else self._variant_rows()
                )
                self.lbl_available.setText(str(total))
                self._variant_pending.clear()
                self._variant_drafts.clear()
                self._variant_locked.clear()
                if custom_mode:
                    self._rebuild_custom_table()
                elif color_mode:
                    self._rebuild_color_tables()
                else:
                    self._rebuild_variant_table()
            else:
                delete_product_variants(self.db_name, self.edit_code)
            self._save_purchase_entry(self.edit_code, stock_update_qty)
            self._save_supplier_link(self.edit_code)
            self.saved.emit(self.edit_code)
        else:
            if not save_product(self.db_name, data, self.current_user):
                QMessageBox.critical(self, "Error", "Could not save.\nProduct no may already exist.")
                return
            if (
                self.f_has_variants.isChecked()
                or self.f_has_color_variants.isChecked()
                or self.f_has_custom_variants.isChecked()
            ):
                color_mode = self.f_has_color_variants.isChecked()
                custom_mode = self.f_has_custom_variants.isChecked()
                total = save_product_variants(
                    self.db_name, data["item_code"],
                    CUSTOM_STORAGE_GROUP if custom_mode
                    else COLOR_STORAGE_GROUP if color_mode
                    else self.f_variant_type.currentText().strip(),
                    self._custom_rows() if custom_mode
                    else self._color_rows() if color_mode
                    else self._variant_rows()
                )
                self.lbl_available.setText(str(total))
                self._variant_pending.clear()
                self._variant_drafts.clear()
                self._variant_locked.clear()
                self.edit_code = data["item_code"]
                if custom_mode:
                    self._rebuild_custom_table()
                elif color_mode:
                    self._rebuild_color_tables()
                else:
                    self._rebuild_variant_table()
                self.edit_code = None
            self._save_purchase_entry(data["item_code"], stock_update_qty)
            self._save_supplier_link(data["item_code"])
            self.saved.emit(data["item_code"])


# ─────────────────────────────────────────────────────────────
#  PRODUCT LIST WIDGET
# ─────────────────────────────────────────────────────────────
class ProductListWidget(QWidget):

    def __init__(self, db_name, on_add, on_edit, current_user="Admin",
                 company_name="", embedded=True, on_back=None, parent=None):
        super().__init__(parent)
        self.db_name      = db_name
        self._on_edit     = on_edit
        self._filters     = {}
        self.current_user = current_user

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        self.setStyleSheet(f"background:{C['bg_light']};")

        # ── Top bar ────────────────────────────────────────
        top = QFrame(); top.setFixedHeight(56)
        top.setStyleSheet(
            "background:#f5f5f7;"
            "border-bottom:1px solid #d2d2d7;"
        )
        tl = QHBoxLayout(top); tl.setContentsMargins(24, 0, 24, 0); tl.setSpacing(12)

        if not embedded and on_back:
            back_btn = QPushButton("Back")
            back_btn.setFixedSize(80, 30)
            back_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,0,0,0.06);
                    color: #1d1d1f;
                    border: 1px solid rgba(0,0,0,0.12);
                    border-radius: 15px;
                    font-size: 13px; font-weight: 500;
                }
                QPushButton:hover { background: rgba(0,0,0,0.10); }
            """)
            back_btn.clicked.connect(on_back); tl.addWidget(back_btn)

        tl.addStretch()

        # chips kept hidden — logic still updates them internally
        self._chip_total = QLabel(); self._chip_total.hide()
        self._chip_low   = QLabel(); self._chip_low.hide()
        self._chip_exp   = QLabel(); self._chip_exp.hide()

        self._add_btn = QPushButton("＋  Add Product")
        self._add_btn.setFixedHeight(38); self._add_btn.setMinimumWidth(148)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C['accent']}, stop:1 {C['accent_dark']});
                color: white; border: none; border-radius: 10px;
                font-size: 13px; font-weight: 700; padding: 0 18px;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C['accent_dark']}, stop:1 {C['accent']});
            }}
            QPushButton:pressed {{ opacity: 0.85; }}
        """)
        self._add_btn.clicked.connect(on_add)
        tl.addWidget(self._add_btn)
        root.addWidget(top)

        # ── Content ────────────────────────────────────────
        content = QWidget(); content.setStyleSheet(f"background:{C['bg_light']};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 16, 24, 16); cl.setSpacing(10)

        # ── Beautiful Filter Bar ───────────────────────────
        ff = QFrame()
        ff.setStyleSheet(f"""
            QFrame {{
                background: {C['bg_white']};
                border: 1.5px solid {C['border']};
                border-radius: 14px;
            }}
        """)
        fl = QVBoxLayout(ff); fl.setContentsMargins(14, 12, 14, 12); fl.setSpacing(8)

        # ── Row 1: Search ──────────────────────────────────
        search_wrap = QFrame()
        search_wrap.setStyleSheet(f"""
            QFrame {{
                background: {C['bg_panel']};
                border: 1.5px solid {C['border']};
                border-radius: 10px;
            }}
            QFrame:hover {{
                border: 1.5px solid {C['blue']};
            }}
        """)
        sw_lay = QHBoxLayout(search_wrap)
        sw_lay.setContentsMargins(12, 0, 12, 0); sw_lay.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size:14px;background:transparent;border:none;")
        sw_lay.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by code, name, alias or barcode…")
        self.search_input.setFixedHeight(38)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                font-size: 13px; color: {C['text']};
            }}
            QLineEdit:focus {{ border: none; background: transparent; }}
        """)
        self.search_input.textChanged.connect(self._on_filter)
        sw_lay.addWidget(self.search_input, 1)

        # Clear search X button
        self._search_clr = QPushButton("✕")
        self._search_clr.setFixedSize(22, 22)
        self._search_clr.setStyleSheet(f"""
            QPushButton {{
                background: {C['border']}; color: {C['text2']};
                border: none; border-radius: 11px;
                font-size: 10px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {C['accent']}; color: white; }}
        """)
        self._search_clr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_clr.setVisible(False)
        self._search_clr.clicked.connect(lambda: self.search_input.clear())
        self.search_input.textChanged.connect(
            lambda t: self._search_clr.setVisible(bool(t)))
        sw_lay.addWidget(self._search_clr)

        search_wrap.setFixedHeight(44)
        fl.addWidget(search_wrap)

        # ── Row 2: Filter dropdowns + Clear button ─────────
        FLT_H  = 38   # uniform height for all filter widgets
        FLT_W  = 160  # uniform width for all dropdowns

        _COMBO_SS = f"""
            QComboBox {{
                border: 1.5px solid {C['border']};
                border-radius: 9px;
                padding: 0px 10px;
                font-size: 12px; font-weight: 600;
                background: {C['bg_white']};
                color: {C['text']};
                min-height: {FLT_H}px; max-height: {FLT_H}px;
            }}
            QComboBox:hover {{
                border: 1.5px solid {C['blue']};
                background: {C['bg_white']};
                color: {C['text']};
            }}
            QComboBox:focus {{
                border: 2px solid {C['accent']};
                background: #FFF8F9;
                color: {C['text']};
            }}
            QComboBox::drop-down {{
                border: none; width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {C['text3']};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background: white; color: #000000;
                border: 1.5px solid {C['border']};
                border-radius: 8px; padding: 4px; outline: none;
                selection-background-color: {C['blue']};
                selection-color: white;
            }}
            QComboBox QAbstractItemView::item {{
                color: #000000; background: white;
                min-height: 30px; padding: 4px 10px;
            }}
            QComboBox QAbstractItemView::item:hover    {{ background: {C['accent']}; color: #FFFFFF; }}
            QComboBox QAbstractItemView::item:selected {{ background: {C['blue']}; color: white; }}
        """

        def _flt_combo(label_text, items):
            wrap = QFrame()
            wrap.setStyleSheet("QFrame{background:transparent;border:none;}")
            vl = QVBoxLayout(wrap); vl.setContentsMargins(0,0,0,0); vl.setSpacing(3)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;font-weight:700;"
                              f"letter-spacing:0.5px;background:transparent;border:none;"
                              f"text-transform:uppercase;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            cb = QComboBox()
            cb.setFixedSize(FLT_W, FLT_H)
            cb.addItems(items)
            cb.setStyleSheet(_COMBO_SS)
            _apply_combo_delegate(cb)
            cb.currentTextChanged.connect(self._on_filter)
            vl.addWidget(lbl)
            vl.addWidget(cb)
            return wrap, cb

        filter_row = QHBoxLayout(); filter_row.setSpacing(10)

        status_wrap, self.flt_status = _flt_combo(
            "STATUS",
            ["All Status", "Active", "Draft", "Inactive", "Discontinued"])

        cat_wrap, self.flt_cat = _flt_combo(
            "CATEGORY",
            ["All Categories"])

        stock_wrap, self.flt_stock = _flt_combo(
            "STOCK LEVEL",
            ["All Stock", "Low Stock", "Out of Stock"])

        filter_row.addWidget(status_wrap)
        filter_row.addWidget(cat_wrap)
        filter_row.addWidget(stock_wrap)
        filter_row.addStretch()

        # ── Clear All button ───────────────────────────────
        clr_wrap = QFrame()
        clr_wrap.setStyleSheet("QFrame{background:transparent;border:none;}")
        clr_v = QVBoxLayout(clr_wrap); clr_v.setContentsMargins(0,0,0,0); clr_v.setSpacing(3)
        clr_spacer = QLabel("")
        clr_spacer.setStyleSheet("background:transparent;border:none;")
        clr_spacer.setFixedHeight(14)  # matches label height above
        clr_btn = QPushButton("✕  Clear All")
        clr_btn.setFixedSize(FLT_W, FLT_H)
        clr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clr_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C['bg_panel']};
                color: {C['text2']};
                border: 1.5px solid {C['border']};
                border-radius: 9px;
                font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{
                background: {C['danger_tint']};
                color: {C['accent']};
                border: 1.5px solid {C['accent']};
            }}
            QPushButton:pressed {{ opacity: 0.8; }}
        """)
        clr_btn.clicked.connect(self._clear_filters)
        clr_v.addWidget(clr_spacer)
        clr_v.addWidget(clr_btn)
        filter_row.addWidget(clr_wrap)

        fl.addLayout(filter_row)
        cl.addWidget(ff)

        # Table — 12 columns
        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "Item Code", "Product Name", "Category", "Unit",
            "MRP ₹", "Sell ₹", "Margin", "Stock", "Reorder", "Expiry", "Status", "Actions"
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col, w in enumerate([90, 0, 100, 58, 90, 90, 70, 65, 70, 100, 85, 110]):
            if w: self.table.setColumnWidth(col, w)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget{{background:{C['bg_white']};border:1px solid {C['border']};
                border-radius:10px;gridline-color:{C['bg_light']};font-size:13px;
                alternate-background-color:{C['bg_panel']};}}
            QHeaderView::section{{background:{C['bg_panel']};font-weight:700;padding:9px;
                border:none;border-bottom:2px solid {C['border']};
                color:{C['text2']};font-size:12px;}}
            QTableWidget::item{{padding:6px 8px;color:{C['text']};}}
            QTableWidget::item:selected{{background:{C['accent_tint2']};color:{C['text']};}}
        """)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self._row_codes: list  = []
        self._row_stocks: list = []
        cl.addWidget(self.table)
        root.addWidget(content)

        self._reload_cats()
        self._load_table()

    # ── Stat chip ──────────────────────────────────────────

    def _stat_chip(self, text, icon, bg=None, fg=None, border=None) -> QLabel:
        bg     = bg     or "#1c1c1e"
        fg     = fg     or "#e5e5ea"
        border = border or "#3a3a3c"
        w = QLabel(f"{icon}  {text}")
        w.setFont(_F(12, bold=True))
        w.setFixedHeight(36)
        w.setMinimumWidth(130)
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setStyleSheet(f"""
            color: {fg};
            background: {bg};
            border: 1px solid {border};
            border-radius: 18px;
            padding: 0px 16px;
            letter-spacing: 0.1px;
        """)
        return w

    # ── Filter helpers ─────────────────────────────────────

    def _reload_cats(self):
        self.flt_cat.blockSignals(True); self.flt_cat.clear()
        self.flt_cat.addItems(get_categories(self.db_name))
        _apply_combo_delegate(self.flt_cat)
        self.flt_cat.blockSignals(False)

    def _on_filter(self):
        st  = self.flt_status.currentText()
        cat = self.flt_cat.currentText()
        stk = self.flt_stock.currentText()
        self._filters = {
            "search":       self.search_input.text().strip(),
            "status":       st  if st  != "All Status" else "All",
            "category":     cat if cat not in ("All", "") else "All",
            "stock_filter": stk if stk != "All Stock"  else "All",
        }
        self._load_table()

    def _clear_filters(self):
        for w in (self.search_input, self.flt_status, self.flt_cat, self.flt_stock):
            w.blockSignals(True)
        self.search_input.clear()
        self.flt_status.setCurrentIndex(0)
        self.flt_cat.setCurrentIndex(0)
        self.flt_stock.setCurrentIndex(0)
        for w in (self.search_input, self.flt_status, self.flt_cat, self.flt_stock):
            w.blockSignals(False)
        self._filters = {}
        self._load_table()

    # ── Table load ─────────────────────────────────────────

    def _load_table(self, rows=None):
        if rows is None:
            rows = get_all_products(self.db_name, self._filters)

        today   = date.today()
        tbl     = self.table
        tbl.setUpdatesEnabled(False)
        tbl.setSortingEnabled(False)
        tbl.setRowCount(0)
        self._row_codes  = []
        self._row_stocks = []

        low_count = 0
        exp_count = 0

        for rd in rows:
            code, name, cat, unit, sell, mrp, stock, reorder, \
                status, gst, expiry, last_sold, purchase, brand = rd

            r = tbl.rowCount(); tbl.insertRow(r)
            tbl.setRowHeight(r, 42)
            self._row_codes.append(code)
            self._row_stocks.append(int(stock or 0))

            def _item(txt, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
                it = QTableWidgetItem(str(txt))
                it.setTextAlignment(align)
                return it

            C_CTR = Qt.AlignmentFlag.AlignCenter
            C_RGT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

            tbl.setItem(r, 0, _item(code or ""))
            tbl.setItem(r, 1, _item(name or ""))
            tbl.setItem(r, 2, _item(cat  or ""))
            tbl.setItem(r, 3, _item(unit or "", C_CTR))

            mrp_v = float(mrp or 0)
            tbl.setItem(r, 4, _item(f"₹{mrp_v:,.2f}" if mrp_v else "—", C_RGT))

            sp_v = float(sell or 0)
            tbl.setItem(r, 5, _item(f"₹{sp_v:,.2f}", C_RGT))

            pp_v = float(purchase or 0)
            if pp_v > 0:
                margin = (sp_v - pp_v) / pp_v * 100
                mg = _item(f"{margin:.1f}%", C_CTR)
                mg.setForeground(QBrush(QColor(C["success"] if margin >= 0 else C["accent"])))
            else:
                mg = _item("—", C_CTR)
            tbl.setItem(r, 6, mg)

            stk_v = int(stock or 0)
            rod_v = int(reorder or 0)
            si = _item(str(stk_v), C_CTR)
            if stk_v == 0:
                si.setForeground(QBrush(QColor(C["accent"])))
                si.setBackground(QBrush(QColor(C["danger_tint"])))
                low_count += 1
            elif rod_v and stk_v <= rod_v:
                si.setForeground(QBrush(QColor(C["warning"])))
                si.setBackground(QBrush(QColor(C["warning_tint"])))
                low_count += 1
            tbl.setItem(r, 7, si)

            tbl.setItem(r, 8, _item(str(rod_v) if rod_v else "—", C_CTR))

            exp_txt = "—"; exp_color = None
            if expiry:
                try:
                    diff = (datetime.strptime(expiry, "%Y-%m-%d").date() - today).days
                    exp_txt = expiry
                    if diff < 0:     exp_color = C["accent"]; exp_count += 1
                    elif diff <= 30: exp_color = C["warning"]; exp_count += 1
                except Exception:
                    pass
            ei = _item(exp_txt, C_CTR)
            if exp_color:
                ei.setForeground(QBrush(QColor(exp_color)))
                ei.setBackground(QBrush(QColor(C["danger_tint"] if exp_color == C["accent"] else C["warning_tint"])))
            tbl.setItem(r, 9, ei)

            sc = {
                "Active":       (C["success_tint"], C["success"]),
                "Draft":        (C["warning_tint"], C["warning"]),
                "Inactive":     (C["bg_panel"],     C["text3"]),
                "Discontinued": (C["danger_tint"],  C["accent"]),
            }.get(status, (C["bg_panel"], C["text3"]))
            sti = _item(str(status or ""), C_CTR)
            sti.setBackground(QBrush(QColor(sc[0])))
            sti.setForeground(QBrush(QColor(sc[1])))
            tbl.setItem(r, 10, sti)

            act = _item("✏️  🗑", C_CTR)
            act.setToolTip("Click to Edit or Delete")
            act.setForeground(QBrush(QColor(C["text2"])))
            tbl.setItem(r, 11, act)

        tbl.setUpdatesEnabled(True)
        total = tbl.rowCount()
        self._chip_total.setText(f"{total} Products")
        self._chip_low.setText(f"{low_count} Low Stock")
        self._chip_exp.setText(f"{exp_count} Expiring")


    # ── Cell click dispatcher ──────────────────────────────

    def _on_cell_clicked(self, row: int, col: int):
        if col != 11 or row >= len(self._row_codes):
            return
        code  = self._row_codes[row]
        stock = self._row_stocks[row]
        name_item = self.table.item(row, 1)
        name = name_item.text() if name_item else code

        msg = QMessageBox(self)
        msg.setWindowTitle(f"Actions — {name}")
        msg.setText(f"<b>{name}</b>  ({code})\nChoose an action:")
        edit_btn = msg.addButton("✏️  Edit",        QMessageBox.ButtonRole.ActionRole)
        del_btn  = msg.addButton("🗑  Delete",       QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Cancel",                      QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == edit_btn:
            self._on_edit(code)
        elif clicked == del_btn:
            self._confirm_delete(code)

    def _confirm_delete(self, item_code):
        reply = QMessageBox.question(
            self, "Delete Product",
            f"Soft-delete  '{item_code}'?\n"
            "It will be hidden but kept in the database (safe for old invoices).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            soft_delete_product(self.db_name, item_code, self.current_user)
            self._load_table()

    def refresh(self):
        self._reload_cats()
        self._load_table()


# ─────────────────────────────────────────────────────────────
#  PRODUCT PAGE  —  list + fade-in overlay form
# ─────────────────────────────────────────────────────────────
class ProductPage(QWidget):
    """
    Two-phase construction (same as original deferred approach):

    Phase 1 (instant): DB migration + ProductListWidget built & shown.
    Phase 2 (deferred via QTimer): ProductFormWidget (7 tabs, 200+ widgets)
            built in the next event-loop tick — no visible freeze.
    """

    def __init__(self, db_name, company_name="", on_back=None,
                 current_user="Admin", embedded=True, parent=None):
        super().__init__(parent)
        self.db_name      = db_name
        self.current_user = current_user
        self._form_ready  = False

        init_product_table(db_name, current_user)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        self.setStyleSheet(f"background:{C['bg_light']};")

        # ── List (always visible) ──────────────────────────
        self._list = ProductListWidget(
            db_name      = db_name,
            on_add       = self._open_add,
            on_edit      = self._open_edit,
            current_user = current_user,
            company_name = company_name,
            embedded     = embedded,
            on_back      = on_back,
            parent       = self,
        )
        root.addWidget(self._list)

        # ── Slide panel (overlay) ──────────────────────────
        self._panel = _SlidePanel(self)
        self._form  = None   # built deferred

        # Deferred heavy build
        QTimer.singleShot(0, self._build_form_deferred)

    def _build_form_deferred(self):
        self._form = ProductFormWidget(
            db_name      = self.db_name,
            current_user = self.current_user,
            parent       = self._panel,
        )
        fl = QVBoxLayout(self._panel)
        fl.setContentsMargins(0, 0, 0, 0); fl.setSpacing(0)
        fl.addWidget(self._form)
        self._form.cancel.connect(self._panel.slide_out)
        self._form.saved.connect(self._on_saved)
        self._form_ready = True

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._panel.resize_to_parent()

    def _open_add(self):
        if not self._form_ready:
            QTimer.singleShot(50, self._open_add); return
        self._form.load_for_add()
        self._panel.slide_in()

    def _open_edit(self, item_code):
        if not self._form_ready:
            QTimer.singleShot(50, lambda: self._open_edit(item_code)); return
        self._form.load_for_edit(item_code)
        self._panel.slide_in()

    def _on_saved(self, _item_code):
        self._list.refresh()
        self._panel.slide_out()


