"""
product_page.py  —  Evo Aura  •  Advanced Product Manager
==========================================================
PyQt6  |  SQLite  |  Apple / EvoAura design system

6-tab form: Basic · Pricing · Inventory · Supplier · Sales History · Audit
Supporting tables: stock_adjustments, price_history, suppliers, product_suppliers
List page: filter bar, MRP/margin columns, inline stock-adjust button
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
from html import escape
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QGridLayout, QComboBox,
    QAbstractItemView, QListWidget, QListWidgetItem,
    QCheckBox, QRadioButton, QButtonGroup, QTabWidget, QScrollArea, QDateEdit, QDoubleSpinBox,
    QSpinBox, QTextEdit, QApplication, QSizePolicy,
    QGraphicsOpacityEffect, QStyledItemDelegate, QStyle,
    QStackedWidget, QDialog, QVBoxLayout, QFileDialog, QToolButton, QMenu,
)
from PyQt6.QtGui  import (
    QFont, QColor, QBrush, QPainter, QPen, QLinearGradient,
    QPixmap, QPalette,
)
from PyQt6.QtCore import (
    Qt, QDate, QRect, QObject, QEvent,
    QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve,
)
from input_behavior import ensure_global_input_guard
from app_branding import apply_app_icon


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
SUB_CATEGORY_OPTIONS = {
    "Shirts": [
        "Formal Shirt", "Casual Shirt", "Printed Shirt", "Checked Shirt",
        "Striped Shirt", "Plain Shirt", "Linen Shirt", "Denim Shirt",
        "Party Wear Shirt", "Full Sleeve Shirt", "Half Sleeve Shirt",
        "Mandarin Collar Shirt",
    ],
    "T-Shirts": [
        "Round Neck T-Shirt", "V-Neck T-Shirt", "Graphic T-Shirt",
        "Printed T-Shirt", "Solid T-Shirt", "Oversized T-Shirt",
        "Athletic T-Shirt",
    ],
    "Polo T-Shirts": [
        "Solid Polo", "Striped Polo", "Printed Polo", "Premium Polo", "Sports Polo",
    ],
    "Jeans": [
        "Slim Fit Jeans", "Regular Fit Jeans", "Skinny Jeans",
        "Relaxed Fit Jeans", "Stretch Jeans", "Distressed Jeans",
    ],
    "Trousers": [
        "Formal Trousers", "Casual Trousers", "Stretch Trousers",
        "Pleated Trousers", "Flat Front Trousers",
    ],
    "Formal Pants": [
        "Office Pants", "Business Pants", "Slim Fit Formal Pants",
        "Regular Fit Formal Pants",
    ],
    "Chinos": [
        "Slim Fit Chinos", "Regular Fit Chinos", "Stretch Chinos", "Casual Chinos",
    ],
    "Shorts": [
        "Casual Shorts", "Denim Shorts", "Cotton Shorts", "Cargo Shorts",
        "Sports Shorts",
    ],
    "Blazers": [
        "Single Breasted Blazer", "Double Breasted Blazer",
        "Casual Blazer", "Formal Blazer",
    ],
    "Suits": [
        "2-Piece Suit", "3-Piece Suit", "Wedding Suit", "Business Suit", "Party Suit",
    ],
    "Jackets": [
        "Denim Jacket", "Bomber Jacket", "Leather Jacket", "Casual Jacket",
        "Winter Jacket",
    ],
    "Hoodies": [
        "Pullover Hoodie", "Zip Hoodie", "Graphic Hoodie", "Oversized Hoodie",
    ],
    "Sweatshirts": [
        "Crew Neck Sweatshirt", "Printed Sweatshirt", "Oversized Sweatshirt",
        "Fleece Sweatshirt",
    ],
    "Kurta": [
        "Cotton Kurta", "Linen Kurta", "Printed Kurta", "Festive Kurta", "Short Kurta",
    ],
    "Innerwear": ["Vest", "Briefs", "Trunks", "Boxer Shorts", "Thermal Wear"],
    "Accessories": [
        "Belt", "Wallet", "Cap", "Socks", "Tie", "Bow Tie", "Handkerchief",
        "Suspenders",
    ],
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
            sleeve                TEXT DEFAULT '',
            brand                 TEXT DEFAULT '',
            style_code            TEXT DEFAULT '',
            fabric_type           TEXT DEFAULT '',
            size                  TEXT DEFAULT '',
            color                 TEXT DEFAULT '',
            fit_type              TEXT DEFAULT '',
            pattern               TEXT DEFAULT '',
            collar_type           TEXT DEFAULT '',
            gender                TEXT DEFAULT '',
            season                TEXT DEFAULT '',
            occasion              TEXT DEFAULT '',
            manufacturer          TEXT DEFAULT '',
            country_of_origin     TEXT DEFAULT 'India',
            hsn_code              TEXT DEFAULT '',
            barcode               TEXT DEFAULT '',
            tags                  TEXT DEFAULT '',
            unit                  TEXT DEFAULT '',
            pack_size             INTEGER DEFAULT 1,
            meter                 TEXT DEFAULT '',
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
            purchase_gst          TEXT DEFAULT '0%',
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
            returned_stock        INTEGER DEFAULT 0,
            in_transit_stock      INTEGER DEFAULT 0,
            reorder_level         INTEGER DEFAULT 0,
            safety_stock          INTEGER DEFAULT 0,
            reorder_qty           INTEGER DEFAULT 0,
            min_order_qty         INTEGER DEFAULT 1,
            net_quantity          REAL DEFAULT 0,
            max_stock             INTEGER DEFAULT 0,
            auto_reorder          INTEGER DEFAULT 0,
            allow_neg_stock       INTEGER DEFAULT 0,
            is_returnable         INTEGER DEFAULT 1,
            warehouse             TEXT DEFAULT '',
            rack_location         TEXT DEFAULT '',
            bin_location          TEXT DEFAULT '',
            last_stock_updated    TEXT DEFAULT '',
            supplier_name         TEXT DEFAULT '',
            supplier_code         TEXT DEFAULT '',
            supplier_phone        TEXT DEFAULT '',
            supplier_email        TEXT DEFAULT '',
            lead_time_days        INTEGER DEFAULT 0,
            last_purchase_price   REAL DEFAULT 0,
            weight_kg             REAL DEFAULT 0,
            length_cm             REAL DEFAULT 0,
            width_cm              REAL DEFAULT 0,
            height_cm             REAL DEFAULT 0,
            has_variants          INTEGER DEFAULT 0,
            variant_type          TEXT DEFAULT '',
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
        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            adj_type     TEXT NOT NULL,
            qty          INTEGER NOT NULL,
            reason       TEXT DEFAULT '',
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
            contact_person  TEXT DEFAULT '',
            phone           TEXT DEFAULT '',
            mobile_number   TEXT DEFAULT '',
            whatsapp_number TEXT DEFAULT '',
            email           TEXT DEFAULT '',
            gstin           TEXT DEFAULT '',
            pan_number      TEXT DEFAULT '',
            address         TEXT DEFAULT '',
            address_line1   TEXT DEFAULT '',
            address_line2   TEXT DEFAULT '',
            city            TEXT DEFAULT '',
            state           TEXT DEFAULT '',
            pincode         TEXT DEFAULT '',
            country         TEXT DEFAULT 'India',
            payment_terms   TEXT DEFAULT 'Net 30',
            payment_terms_days INTEGER DEFAULT 30,
            credit_limit    REAL DEFAULT 0,
            current_balance REAL DEFAULT 0,
            bank_account    TEXT DEFAULT '',
            account_holder_name TEXT DEFAULT '',
            bank_name       TEXT DEFAULT '',
            branch_name     TEXT DEFAULT '',
            account_number  TEXT DEFAULT '',
            ifsc            TEXT DEFAULT '',
            upi_id          TEXT DEFAULT '',
            default_lead_time INTEGER DEFAULT 0,
            preferred_payment_method TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
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
            supplier_product_name TEXT DEFAULT '',
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
        CREATE TABLE IF NOT EXISTS purchase_invoice_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            supplier_code TEXT DEFAULT '',
            supplier_name TEXT DEFAULT '',
            invoice_number TEXT NOT NULL,
            invoice_date TEXT DEFAULT '',
            purchase_date TEXT DEFAULT '',
            quantity INTEGER DEFAULT 0,
            purchase_price REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            gst_rate REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            gross_amount REAL DEFAULT 0,
            gst_amount REAL DEFAULT 0,
            net_amount REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            balance_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Pending',
            stock_after INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_update_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            action_type TEXT DEFAULT '',
            reference_number TEXT DEFAULT '',
            supplier_name TEXT DEFAULT '',
            qty_in INTEGER DEFAULT 0,
            qty_out INTEGER DEFAULT 0,
            old_stock INTEGER DEFAULT 0,
            new_stock INTEGER DEFAULT 0,
            reason TEXT DEFAULT '',
            updated_by TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
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

    c.execute("PRAGMA table_info(products)")
    existing = {r[1] for r in c.fetchall()}
    new_cols = [
        ("sku","TEXT DEFAULT ''"), ("alias_names","TEXT DEFAULT ''"),
        ("product_type","TEXT DEFAULT 'Goods'"), ("tax_category","TEXT DEFAULT 'Standard'"),
        ("product_group","TEXT DEFAULT ''"), ("country_of_origin","TEXT DEFAULT 'India'"),
        ("tags","TEXT DEFAULT ''"), ("image","BLOB"),
        ("mrp","REAL DEFAULT 0"), ("retail_price","REAL DEFAULT 0"),
        ("dealer_price","REAL DEFAULT 0"), ("special_price","REAL DEFAULT 0"),
        ("special_price_from","TEXT DEFAULT ''"), ("special_price_to","TEXT DEFAULT ''"),
        ("igst_rate","TEXT DEFAULT '0%'"), ("tcs_applicable","INTEGER DEFAULT 0"),
        ("gst_exemption_reason","TEXT DEFAULT ''"), ("reserved_stock","INTEGER DEFAULT 0"),
        ("damaged_stock","INTEGER DEFAULT 0"), ("returned_stock","INTEGER DEFAULT 0"),
        ("in_transit_stock","INTEGER DEFAULT 0"),
        ("safety_stock","INTEGER DEFAULT 0"), ("reorder_qty","INTEGER DEFAULT 0"),
        ("auto_reorder","INTEGER DEFAULT 0"), ("bin_location","TEXT DEFAULT ''"),
        ("last_stock_updated","TEXT DEFAULT ''"),
        ("supplier_phone","TEXT DEFAULT ''"),
        ("supplier_email","TEXT DEFAULT ''"),
        ("total_qty_sold","INTEGER DEFAULT 0"),
        ("total_revenue","REAL DEFAULT 0"), ("last_sold_date","TEXT DEFAULT ''"),
        ("return_count","INTEGER DEFAULT 0"), ("sale_count","INTEGER DEFAULT 0"),
        ("is_deleted","INTEGER DEFAULT 0"), ("deleted_at","TEXT DEFAULT ''"),
        ("deleted_by","TEXT DEFAULT ''"), ("created_at","TEXT DEFAULT ''"),
        ("created_by","TEXT DEFAULT ''"), ("updated_at","TEXT DEFAULT ''"),
        ("updated_by","TEXT DEFAULT ''"),
        ("description","TEXT DEFAULT ''"), ("sub_category","TEXT DEFAULT ''"),
        ("sleeve","TEXT DEFAULT ''"), ("net_quantity","REAL DEFAULT 0"),
        ("brand","TEXT DEFAULT ''"), ("style_code","TEXT DEFAULT ''"),
        ("fabric_type","TEXT DEFAULT ''"), ("size","TEXT DEFAULT ''"),
        ("color","TEXT DEFAULT ''"), ("fit_type","TEXT DEFAULT ''"),
        ("pattern","TEXT DEFAULT ''"), ("collar_type","TEXT DEFAULT ''"),
        ("gender","TEXT DEFAULT ''"), ("season","TEXT DEFAULT ''"),
        ("occasion","TEXT DEFAULT ''"), ("manufacturer","TEXT DEFAULT ''"),
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
        ("is_returnable","INTEGER DEFAULT 1"),
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

    c.execute("PRAGMA table_info(suppliers)")
    supplier_existing = {r[1] for r in c.fetchall()}
    supplier_cols = [
        ("contact_person", "TEXT DEFAULT ''"),
        ("mobile_number", "TEXT DEFAULT ''"),
        ("whatsapp_number", "TEXT DEFAULT ''"),
        ("gstin", "TEXT DEFAULT ''"),
        ("pan_number", "TEXT DEFAULT ''"),
        ("address_line1", "TEXT DEFAULT ''"),
        ("address_line2", "TEXT DEFAULT ''"),
        ("country", "TEXT DEFAULT 'India'"),
        ("payment_terms_days", "INTEGER DEFAULT 30"),
        ("account_holder_name", "TEXT DEFAULT ''"),
        ("bank_name", "TEXT DEFAULT ''"),
        ("branch_name", "TEXT DEFAULT ''"),
        ("account_number", "TEXT DEFAULT ''"),
        ("upi_id", "TEXT DEFAULT ''"),
        ("default_lead_time", "INTEGER DEFAULT 0"),
        ("preferred_payment_method", "TEXT DEFAULT ''"),
        ("notes", "TEXT DEFAULT ''"),
    ]
    for col, defn in supplier_cols:
        if col not in supplier_existing:
            try:
                c.execute(f"ALTER TABLE suppliers ADD COLUMN {col} {defn}")
            except Exception:
                pass

    c.execute("PRAGMA table_info(product_suppliers)")
    ps_existing = {r[1] for r in c.fetchall()}
    if "supplier_product_name" not in ps_existing:
        try:
            c.execute(
                "ALTER TABLE product_suppliers "
                "ADD COLUMN supplier_product_name TEXT DEFAULT ''"
            )
        except Exception:
            pass

    c.execute("PRAGMA table_info(purchase_invoice_logs)")
    purchase_log_existing = {r[1] for r in c.fetchall()}
    if "selling_price" not in purchase_log_existing:
        try:
            c.execute(
                "ALTER TABLE purchase_invoice_logs "
                "ADD COLUMN selling_price REAL DEFAULT 0"
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    _initialized_dbs.add(db_name)


# ── Query helpers ──────────────────────────────────────────

def get_all_products(db_name, filters=None):
    filters = filters or {}
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    sql = """
        SELECT p.*,
               COALESCE(
                   (SELECT s.name
                    FROM product_suppliers ps
                    LEFT JOIN suppliers s ON s.code=ps.supplier_code
                    WHERE ps.product_code=p.item_code
                    ORDER BY ps.is_primary DESC, ps.id DESC LIMIT 1),
                   p.supplier_name, ''
               ) AS list_supplier,
               COALESCE(
                   (SELECT pil.purchase_date
                    FROM purchase_invoice_logs pil
                    WHERE pil.product_code=p.item_code
                    ORDER BY pil.purchase_date DESC, pil.id DESC LIMIT 1),
                   ''
               ) AS list_last_purchase_date,
               COALESCE(
                   (SELECT pil.invoice_number
                    FROM purchase_invoice_logs pil
                    WHERE pil.product_code=p.item_code
                    ORDER BY pil.purchase_date DESC, pil.id DESC LIMIT 1),
                   ''
               ) AS list_last_invoice
        FROM products p WHERE p.is_deleted=0
    """
    params = []
    if filters.get("status") and filters["status"] != "All":
        sql += " AND p.status=?"; params.append(filters["status"])
    if filters.get("category") and filters["category"] not in ("All", ""):
        sql += " AND p.category=?"; params.append(filters["category"])
    if filters.get("stock_filter") == "Low Stock":
        sql += " AND p.stock <= p.reorder_level AND p.reorder_level > 0"
    elif filters.get("stock_filter") == "Out of Stock":
        sql += " AND p.stock = 0"
    if filters.get("search"):
        q = f"%{filters['search']}%"
        sql += """ AND (
            p.item_code LIKE ? OR p.name LIKE ? OR p.alias_names LIKE ?
            OR p.barcode LIKE ? OR p.sku LIKE ? OR p.brand LIKE ?
            OR p.category LIKE ? OR p.color LIKE ?
        )"""
        params += [q] * 8
    sql += " ORDER BY p.name"
    c.execute(sql, params)
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_product_admin_kpis(db_name):
    """Return the eight headline product KPIs used by the admin list."""
    with sqlite3.connect(db_name) as conn:
        row = conn.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='Active' THEN 1 ELSE 0 END),
                   COALESCE(SUM(stock), 0),
                   COALESCE(SUM(stock * purchase_price), 0),
                   COALESCE(SUM(stock * selling_price), 0),
                   SUM(CASE WHEN reorder_level>0 AND stock<=reorder_level
                            THEN 1 ELSE 0 END),
                   SUM(CASE WHEN stock=0 THEN 1 ELSE 0 END)
            FROM products
            WHERE is_deleted=0
        """).fetchone()
        today_added = conn.execute("""
            SELECT COALESCE(SUM(qty_in), 0)
            FROM stock_update_logs
            WHERE date(created_at)=date('now', 'localtime')
        """).fetchone()[0]
    return {
        "total": int(row[0] or 0),
        "active": int(row[1] or 0),
        "stock_qty": int(row[2] or 0),
        "stock_value": float(row[3] or 0),
        "selling_value": float(row[4] or 0),
        "low_stock": int(row[5] or 0),
        "out_stock": int(row[6] or 0),
        "today_added": int(today_added or 0),
    }


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


def create_supplier(db_name, name, code="", contact_person="", mobile_number="",
                    whatsapp_number="", email="", gstin="", pan_number="",
                    address_line1="", address_line2="", city="", state="",
                    pincode="", country="India", account_holder_name="",
                    bank_name="", branch_name="", account_number="", ifsc="",
                    upi_id="", payment_terms_days=30, credit_limit=0,
                    default_lead_time=0, preferred_payment_method="", notes=""):
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
            requested_code = code.strip().upper()
            base = requested_code or ("SUP" + str(int(time.time()))[-7:])
            code = base
            n = 1
            while conn.execute("SELECT 1 FROM suppliers WHERE code=? LIMIT 1", (code,)).fetchone():
                if requested_code:
                    return None
                code = f"{base}{n}"
                n += 1
            conn.execute(
                """INSERT INTO suppliers(
                    code, name, contact_person, phone, mobile_number,
                    whatsapp_number, email, gstin, pan_number, address,
                    address_line1, address_line2, city, state, pincode, country,
                    payment_terms, payment_terms_days, credit_limit,
                    bank_account, account_holder_name, bank_name, branch_name,
                    account_number, ifsc, upi_id, default_lead_time,
                    preferred_payment_method, notes, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    code, name, contact_person.strip(), mobile_number.strip(),
                    mobile_number.strip(), whatsapp_number.strip(), email.strip(),
                    gstin.strip().upper(), pan_number.strip().upper(),
                    address_line1.strip(), address_line1.strip(),
                    address_line2.strip(), city.strip(), state.strip(),
                    pincode.strip(), country.strip() or "India",
                    f"Net {int(payment_terms_days)}", int(payment_terms_days),
                    float(credit_limit), account_number.strip(),
                    account_holder_name.strip(), bank_name.strip(),
                    branch_name.strip(), account_number.strip(), ifsc.strip().upper(),
                    upi_id.strip(), int(default_lead_time),
                    preferred_payment_method.strip(), notes.strip(), now,
                ))
            conn.commit()
        return code
    except Exception:
        return None


def save_product_supplier(db_name, product_code, supplier_code,
                          sup_sku="", unit_price=0.0, moq=1,
                          lead_days=0, is_primary=0, default_qty=1,
                          supplier_product_name=""):
    """Upsert product_suppliers row."""
    now = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_name) as conn:
            conn.execute("""
                INSERT INTO product_suppliers
                    (product_code, supplier_code, supplier_product_code,
                     unit_price, moq, lead_time_days, is_primary, pack_size,
                     last_ordered_date, supplier_product_name)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(product_code, supplier_code) DO UPDATE SET
                    supplier_product_code = excluded.supplier_product_code,
                    unit_price            = excluded.unit_price,
                    moq                   = excluded.moq,
                    lead_time_days        = excluded.lead_time_days,
                    is_primary            = excluded.is_primary,
                    pack_size             = excluded.pack_size,
                    supplier_product_name = excluded.supplier_product_name
            """, (product_code, supplier_code, sup_sku, unit_price,
                  moq, lead_days, is_primary, default_qty, now,
                  supplier_product_name))
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
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT ps.*, s.name, s.contact_person, s.phone, s.mobile_number,
                       s.email, s.address, s.city, s.state, s.payment_terms,
                       s.current_balance, s.status AS supplier_status
                FROM product_suppliers ps
                JOIN suppliers s ON s.code = ps.supplier_code
                WHERE ps.product_code = ?
                ORDER BY ps.is_primary DESC, s.name
            """, (product_code,)).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def get_saved_sub_categories(db_name, category=""):
    """Return reusable sub-category names, optionally for one category."""
    with sqlite3.connect(db_name) as conn:
        sql = (
            "SELECT DISTINCT TRIM(sub_category) FROM products "
            "WHERE TRIM(COALESCE(sub_category, ''))<>'' AND is_deleted=0"
        )
        params = []
        if category.strip():
            sql += " AND lower(TRIM(category))=lower(?)"
            params.append(category.strip())
        sql += " ORDER BY TRIM(sub_category) COLLATE NOCASE"
        rows = conn.execute(sql, params).fetchall()
    return [row[0] for row in rows if row and row[0]]


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


def get_product_sales_rows(db_name, product_code, product_name=""):
    """Read local billing rows while tolerating common offline invoice schemas."""
    try:
        with sqlite3.connect(db_name) as conn:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "invoices" not in tables or "invoice_items" not in tables:
                return []
            inv_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(invoices)").fetchall()
            }
            item_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(invoice_items)").fetchall()
            }

            def pick(columns, choices):
                return next((name for name in choices if name in columns), None)

            join_col = pick(item_cols, ["invoice_id", "invoice_number", "invoice_no"])
            inv_join = join_col if join_col in inv_cols else pick(
                inv_cols, ["invoice_id", "invoice_number", "invoice_no"])
            product_col = pick(
                item_cols, ["product_code", "item_code", "code", "sku"])
            name_col = pick(item_cols, ["product_name", "item_name", "name"])
            qty_col = pick(item_cols, ["quantity", "qty", "stock_qty"])
            price_col = pick(
                item_cols, ["selling_price", "unit_price", "price", "rate"])
            revenue_col = pick(
                item_cols, ["total", "total_amount", "line_total", "amount"])
            cost_col = pick(
                item_cols, ["purchase_price", "cost_price", "cost"])
            return_col = pick(
                item_cols, ["return_status", "is_returned", "returned_qty"])
            date_col = pick(
                inv_cols, ["date", "sale_date", "invoice_date", "created_at"])
            invoice_col = pick(
                inv_cols, ["invoice_number", "invoice_no", "invoice_id", "id"])
            if not all((join_col, inv_join, qty_col, date_col, invoice_col)):
                return []
            if not price_col and not revenue_col:
                return []
            where_col, where_value = (
                (product_col, product_code) if product_col
                else (name_col, product_name)
            )
            if not where_col:
                return []
            q = lambda name: f'"{name}"'
            revenue_expr = (
                f"ii.{q(revenue_col)}"
                if revenue_col else
                f"(ii.{q(qty_col)} * ii.{q(price_col)})"
            )
            price_expr = (
                f"ii.{q(price_col)}" if price_col else
                f"({revenue_expr} / NULLIF(ii.{q(qty_col)}, 0))"
            )
            cost_expr = f"ii.{q(cost_col)}" if cost_col else "NULL"
            return_expr = f"ii.{q(return_col)}" if return_col else "''"
            sql = f"""
                SELECT i.{q(invoice_col)}, i.{q(date_col)}, ii.{q(qty_col)},
                       {price_expr}, {revenue_expr}, {cost_expr}, {return_expr}
                FROM invoice_items ii
                JOIN invoices i ON ii.{q(join_col)} = i.{q(inv_join)}
                WHERE lower(trim(CAST(ii.{q(where_col)} AS TEXT))) =
                      lower(trim(CAST(? AS TEXT)))
                ORDER BY i.{q(date_col)} DESC
            """
            rows = conn.execute(sql, (where_value,)).fetchall()
        return [{
            "invoice": row[0], "date": row[1], "qty": float(row[2] or 0),
            "price": float(row[3] or 0), "revenue": float(row[4] or 0),
            "cost": None if row[5] is None else float(row[5] or 0),
            "return_status": row[6],
        } for row in rows]
    except Exception:
        return []


def get_purchase_price_insights(db_name, product_code):
    """Return latest and average non-zero purchase prices for a product."""
    if not product_code:
        return 0.0, 0.0
    try:
        with sqlite3.connect(db_name) as conn:
            supplier_row = conn.execute(
                "SELECT COALESCE(NULLIF(last_received_price,0), NULLIF(unit_price,0), 0) "
                "FROM product_suppliers WHERE product_code=? "
                "ORDER BY CASE WHEN last_ordered_date='' THEN 1 ELSE 0 END, "
                "last_ordered_date DESC, id DESC LIMIT 1",
                (product_code,),
            ).fetchone()
            rows = conn.execute(
                "SELECT purchase_price FROM price_history "
                "WHERE product_code=? AND purchase_price>0 "
                "ORDER BY changed_at DESC, id DESC",
                (product_code,),
            ).fetchall()
        values = [float(row[0] or 0) for row in rows if float(row[0] or 0) > 0]
        supplier_latest = float(supplier_row[0] or 0) if supplier_row else 0.0
        if not values:
            return supplier_latest, supplier_latest
        return supplier_latest or values[0], sum(values) / len(values)
    except Exception:
        return 0.0, 0.0


def get_saved_product_values(db_name, column):
    """Return reusable values for approved product dropdown columns."""
    allowed = {
        "brand", "fabric_type", "fit_type", "product_group", "category",
        "color", "pattern", "occasion",
    }
    if column not in allowed:
        return []
    try:
        with sqlite3.connect(db_name) as conn:
            rows = conn.execute(
                f"SELECT DISTINCT TRIM({column}) FROM products "
                f"WHERE TRIM(COALESCE({column}, ''))<>'' AND is_deleted=0 "
                f"ORDER BY TRIM({column}) COLLATE NOCASE"
            ).fetchall()
        return [row[0] for row in rows]
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


def get_purchase_invoice_logs(db_name, product_code):
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(
            "SELECT * FROM purchase_invoice_logs WHERE product_code=? "
            "ORDER BY purchase_date DESC, id DESC",
            (product_code,),
        ).fetchall()]


def get_stock_update_logs(db_name, product_code):
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(
            "SELECT * FROM stock_update_logs WHERE product_code=? "
            "ORDER BY created_at DESC, id DESC",
            (product_code,),
        ).fetchall()]


def get_supplier_product_stats(db_name, product_code, supplier_code):
    with sqlite3.connect(db_name) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(quantity),0), COALESCE(SUM(net_amount),0),
                      COALESCE(AVG(NULLIF(purchase_price,0)),0),
                      COALESCE(MAX(purchase_date),''),
                      COALESCE(MAX(invoice_number),'')
               FROM purchase_invoice_logs
               WHERE product_code=? AND supplier_code=?""",
            (product_code, supplier_code),
        ).fetchone()
        total_all = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM purchase_invoice_logs "
            "WHERE product_code=?",
            (product_code,),
        ).fetchone()[0]
    qty = int(row[0] or 0)
    contribution = (qty / float(total_all) * 100) if total_all else 0
    return {
        "total_qty": qty, "total_value": float(row[1] or 0),
        "average_price": float(row[2] or 0), "last_date": row[3] or "",
        "last_invoice": row[4] or "", "contribution": contribution,
    }


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
            "UPDATE products SET stock=?, last_stock_updated=? WHERE item_code=?",
            (
                int(total or 0),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                product_code,
            )
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


def soft_delete_product(db_name, item_code, current_user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_name) as conn:
        conn.execute(
            "UPDATE products SET is_deleted=1, deleted_at=?, deleted_by=?, status='Inactive' WHERE item_code=?",
            (now, current_user, item_code)
        )


def save_stock_adjustment(db_name, product_code, adj_type, qty, reason,
                          note="", user="system"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_name) as conn:
        conn.execute("""
            INSERT INTO stock_adjustments
            (product_code, adj_type, qty, reason, adj_date, created_by, note)
            VALUES (?,?,?,?,?,?,?)
        """, (product_code, adj_type, qty, reason, now, user, note))
        if adj_type == "IN":
            conn.execute(
                "UPDATE products SET stock=stock+?, last_stock_updated=? "
                "WHERE item_code=?",
                (qty, now, product_code),
            )
        else:
            conn.execute(
                "UPDATE products SET stock=MAX(0,stock-?), last_stock_updated=? "
                "WHERE item_code=?",
                (qty, now, product_code),
            )


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
    frame.setMinimumWidth(0)
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
    # Keep forms responsive when the application sidebar is expanded.
    grid.setColumnMinimumWidth(0, 92)
    grid.setColumnMinimumWidth(1, 110)
    grid.setColumnMinimumWidth(2, 92)
    grid.setColumnMinimumWidth(3, 110)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
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
    if (
        not hint
        and isinstance(widget, QComboBox)
        and bool(widget.property("supportsAddNew"))
    ):
        hint = "Select from the list or type to add new"
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


class _MonthlySalesChart(QWidget):
    """Small dependency-free monthly quantity trend chart."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = []
        self.setMinimumHeight(190)

    def set_values(self, values):
        self._values = list(values)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(42, 18, -18, -32)
        painter.setPen(QColor(C["border"]))
        painter.drawLine(area.bottomLeft(), area.bottomRight())
        painter.drawLine(area.bottomLeft(), area.topLeft())
        if not self._values:
            painter.setPen(QColor(C["text3"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No sales data")
            return
        maximum = max(max(value for _label, value in self._values), 1)
        count = len(self._values)
        step = area.width() / max(count, 1)
        points = []
        for index, (label, value) in enumerate(self._values):
            x = area.left() + step * index + step / 2
            y = area.bottom() - (float(value) / maximum) * area.height()
            points.append((x, y))
            painter.setPen(QColor(C["text3"]))
            painter.drawText(
                QRect(int(x - step / 2), area.bottom() + 5, int(step), 20),
                Qt.AlignmentFlag.AlignCenter, str(label))
        painter.setPen(QPen(QColor(C["blue"]), 3))
        for first, second in zip(points, points[1:]):
            painter.drawLine(int(first[0]), int(first[1]), int(second[0]), int(second[1]))
        painter.setBrush(QColor(C["accent"]))
        painter.setPen(Qt.PenStyle.NoPen)
        for x, y in points:
            painter.drawEllipse(QRect(int(x - 4), int(y - 4), 8, 8))


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
                 parent=None):
        super().__init__(parent)
        self.db_name = db_name; self.product_code = product_code; self.user = user
        self.product_name = product_name; self.current_stock = current_stock
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
            "OUT — Damaged",
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

        self.adj_type.currentTextChanged.connect(self._on_type_changed)
        self._ok_btn.clicked.connect(self._apply)
        cancel.clicked.connect(self.reject)
        self._on_type_changed(self.adj_type.currentText())
        self.adjustSize()

    def _on_type_changed(self, text):
        is_in_received = text == "IN — Stock Received"
        self._ok_btn.setText(
            "✅  Receive Stock" if is_in_received else "✅  Apply Adjustment")
        self.adjustSize()

    def _apply(self):
        adj_raw  = self.adj_type.currentText()
        adj_type = "IN" if adj_raw.startswith("IN") else "OUT"
        qty      = self.qty_spin.value()
        reason   = self.reason.text().strip() or adj_raw
        notes    = self.note.text().strip()

        save_stock_adjustment(
            self.db_name, self.product_code, adj_type, qty,
            reason, notes, self.user)
        QMessageBox.information(self, "Done",
            f"Stock {'increased' if adj_type == 'IN' else 'reduced'} by {qty} units.")
        self.accept()


class PurchaseStockDialog(QDialog):
    """Offline purchase invoice and stock-in entry."""
    def __init__(self, db_name, product_code, product_name, current_stock,
                 current_user, parent=None, invoice_record=None):
        super().__init__(parent)
        self.db_name, self.product_code = db_name, product_code
        self.current_stock, self.current_user = int(current_stock or 0), current_user
        self.product_record = get_product_full(db_name, product_code) or {}
        self.invoice_record = invoice_record or None
        self.original_qty = int((invoice_record or {}).get("quantity", 0) or 0)
        self.setWindowTitle(
            "Edit Purchase Invoice & Stock"
            if self.invoice_record else
            "Adjust / Update Stock & Purchase Invoice"
        )
        self.setMinimumWidth(680)
        root = QVBoxLayout(self); root.setContentsMargins(20, 18, 20, 18)
        form = QGridLayout(); form.setHorizontalSpacing(12); form.setVerticalSpacing(9)
        root.addLayout(form)

        self.supplier = QComboBox(); self.supplier.setEditable(True)
        self.supplier.addItems([""] + get_all_supplier_names(db_name))
        self.invoice = QLineEdit()
        self.invoice_date = QDateEdit(QDate.currentDate())
        self.purchase_date = QDateEdit(QDate.currentDate())
        self.qty = QSpinBox(); self.qty.setRange(1, 9999999)
        self.price = price_spin()
        self.gst = QComboBox(); self.gst.addItems(["0%", "5%", "12%", "18%", "28%"])
        self.actual_purchase = ro_label("₹ 0.00")
        self.selling_price = price_spin()
        self.selling_gst = QComboBox()
        self.selling_gst.addItems(["0%", "5%", "12%", "18%", "28%"])
        self.selling_tax_inclusive = ToggleSwitch("Selling price includes GST")
        self.actual_selling = ro_label("₹ 0.00")
        self.discount = price_spin()
        self.paid = price_spin()
        self.notes = QTextEdit(); self.notes.setFixedHeight(65)
        self.total = ro_label("₹ 0.00"); self.balance = ro_label("₹ 0.00")
        self.status = ro_label("Pending"); self.new_stock = ro_label(str(self.current_stock))

        self.selling_price.setValue(
            float(self.product_record.get("selling_price", 0) or 0))
        self.selling_gst.setCurrentText(
            str(self.product_record.get("gst_rate", "0%") or "0%"))
        self.selling_tax_inclusive.setChecked(
            bool(self.product_record.get("tax_inclusive", 0)))
        if not self.invoice_record:
            self.price.setValue(
                float(self.product_record.get("purchase_price", 0) or 0))
            self.gst.setCurrentText(
                str(self.product_record.get("purchase_gst", "0%") or "0%"))

        if self.invoice_record:
            self.supplier.setCurrentText(str(self.invoice_record.get("supplier_name", "") or ""))
            self.invoice.setText(str(self.invoice_record.get("invoice_number", "") or ""))
            inv_date = QDate.fromString(
                str(self.invoice_record.get("invoice_date", "") or ""), "yyyy-MM-dd")
            pur_date = QDate.fromString(
                str(self.invoice_record.get("purchase_date", "") or ""), "yyyy-MM-dd")
            self.invoice_date.setDate(inv_date if inv_date.isValid() else QDate.currentDate())
            self.purchase_date.setDate(pur_date if pur_date.isValid() else QDate.currentDate())
            self.qty.setValue(max(1, self.original_qty))
            self.price.setValue(float(self.invoice_record.get("purchase_price", 0) or 0))
            self.gst.setCurrentText(
                f"{float(self.invoice_record.get('gst_rate', 0) or 0):g}%")
            self.discount.setValue(
                float(self.invoice_record.get("discount_amount", 0) or 0))
            self.paid.setValue(float(self.invoice_record.get("paid_amount", 0) or 0))
            self.notes.setPlainText(str(self.invoice_record.get("notes", "") or ""))

        info = [
            ("Product Code", ro_label(product_code)), ("Product Name", ro_label(product_name)),
            ("Current Available Stock", ro_label(str(current_stock))), ("Supplier Name", self.supplier),
            ("Invoice Number", self.invoice), ("Invoice Date", self.invoice_date),
            ("Purchase Date", self.purchase_date), ("Quantity Purchased", self.qty),
            ("Purchase Price", self.price), ("Purchase GST Rate", self.gst),
            ("Actual Purchase Cost", self.actual_purchase),
            ("Selling Price", self.selling_price),
            ("Selling GST Rate", self.selling_gst),
            ("Final Selling Price", self.actual_selling),
            ("Discount Amount", self.discount), ("Paid Amount", self.paid),
            ("Net Purchase Value", self.total), ("Balance Amount", self.balance),
            ("Payment Status", self.status), ("New Available Stock", self.new_stock),
        ]
        for i, (label, widget) in enumerate(info):
            add_field(form, i // 2, (i % 2) * 2, label, widget)
        row = (len(info) + 1) // 2
        form.addWidget(self.selling_tax_inclusive, row, 0, 1, 4)
        row += 1
        form.addWidget(QLabel("Notes", styleSheet=LABEL_SS), row, 0)
        form.addWidget(self.notes, row, 1, 1, 3)

        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = _GBtn("Cancel", "ghost")
        save = _GBtn(
            "Save Invoice Changes" if self.invoice_record else "Save & Update Stock",
            "success")
        cancel.clicked.connect(self.reject); save.clicked.connect(self._save)
        buttons.addWidget(cancel); buttons.addWidget(save); root.addLayout(buttons)
        for w in (
            self.qty, self.price, self.selling_price,
            self.discount, self.paid
        ):
            w.valueChanged.connect(self._calculate)
        self.gst.currentTextChanged.connect(self._calculate)
        self.selling_gst.currentTextChanged.connect(self._calculate)
        self.selling_tax_inclusive.stateChanged.connect(self._calculate)
        self._calculate()

    def _calculate(self):
        gross = self.qty.value() * self.price.value()
        rate = float(self.gst.currentText().replace("%", "") or 0)
        purchase_unit_actual = self.price.value() * (1 + rate / 100)
        selling_rate = float(
            self.selling_gst.currentText().replace("%", "") or 0)
        if self.selling_tax_inclusive.isChecked():
            final_selling = self.selling_price.value()
        else:
            final_selling = self.selling_price.value() * (1 + selling_rate / 100)
        net = max(0.0, gross + gross * rate / 100 - self.discount.value())
        balance = max(0.0, net - self.paid.value())
        status = "Paid" if balance <= 0.005 else (
            "Partial" if self.paid.value() > 0 else "Pending")
        self.total.setText(f"₹ {net:,.2f}")
        self.actual_purchase.setText(f"₹ {purchase_unit_actual:,.2f}")
        self.actual_selling.setText(f"₹ {final_selling:,.2f}")
        self.balance.setText(f"₹ {balance:,.2f}")
        self.status.setText(status)
        stock_delta = self.qty.value() - self.original_qty
        self.new_stock.setText(str(max(0, self.current_stock + stock_delta)))

    def _save(self):
        supplier_name = self.supplier.currentText().strip()
        if (
            not supplier_name or not self.invoice.text().strip()
            or self.price.value() <= 0 or self.selling_price.value() <= 0
        ):
            QMessageBox.warning(
                self, "Required",
                "Supplier, invoice number, purchase price and selling price are required.")
            return
        supplier = get_supplier_by_name(self.db_name, supplier_name)
        supplier_code = supplier["code"] if supplier else create_supplier(self.db_name, supplier_name)
        gross = self.qty.value() * self.price.value()
        rate = float(self.gst.currentText().replace("%", "") or 0)
        gst_amount = gross * rate / 100
        net = max(0.0, gross + gst_amount - self.discount.value())
        balance = max(0.0, net - self.paid.value())
        status = "Paid" if balance <= 0.005 else ("Partial" if self.paid.value() > 0 else "Pending")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stock_delta = self.qty.value() - self.original_qty
        new_stock = max(0, self.current_stock + stock_delta)
        with sqlite3.connect(self.db_name) as conn:
            if self.invoice_record:
                conn.execute(
                    """UPDATE purchase_invoice_logs SET
                       supplier_code=?,supplier_name=?,invoice_number=?,
                       invoice_date=?,purchase_date=?,quantity=?,purchase_price=?,
                       selling_price=?,gst_rate=?,discount_amount=?,gross_amount=?,gst_amount=?,
                       net_amount=?,paid_amount=?,balance_amount=?,payment_status=?,
                       stock_after=?,notes=? WHERE id=?""",
                    (supplier_code or "", supplier_name, self.invoice.text().strip(),
                     self.invoice_date.date().toString("yyyy-MM-dd"),
                     self.purchase_date.date().toString("yyyy-MM-dd"),
                     self.qty.value(), self.price.value(),
                     self.selling_price.value(), rate,
                     self.discount.value(), gross, gst_amount, net,
                     self.paid.value(), balance, status, new_stock,
                     self.notes.toPlainText().strip(), self.invoice_record["id"]))
            else:
                conn.execute(
                    """INSERT INTO purchase_invoice_logs(
                        product_code,supplier_code,supplier_name,invoice_number,
                        invoice_date,purchase_date,quantity,purchase_price,gst_rate,
                        selling_price,
                        discount_amount,gross_amount,gst_amount,net_amount,paid_amount,
                        balance_amount,payment_status,stock_after,notes,created_at,created_by
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (self.product_code, supplier_code or "", supplier_name,
                     self.invoice.text().strip(), self.invoice_date.date().toString("yyyy-MM-dd"),
                     self.purchase_date.date().toString("yyyy-MM-dd"), self.qty.value(),
                     self.price.value(), rate, self.selling_price.value(),
                     self.discount.value(), gross, gst_amount,
                     net, self.paid.value(), balance, status, new_stock,
                     self.notes.toPlainText().strip(), now, self.current_user))
            conn.execute(
                """INSERT INTO stock_update_logs(
                    product_code,action_type,reference_number,supplier_name,qty_in,
                    qty_out,old_stock,new_stock,reason,updated_by,notes,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (self.product_code,
                 "Invoice Edited" if self.invoice_record else "Purchase Stock In",
                 self.invoice.text().strip(), supplier_name,
                 max(stock_delta, 0), max(-stock_delta, 0),
                 self.current_stock, new_stock,
                 "Purchase invoice edited" if self.invoice_record else "Purchase Invoice",
                 self.current_user,
                 self.notes.toPlainText().strip(), now))
            conn.execute(
                """UPDATE products SET stock=?,purchase_price=?,
                   last_purchase_price=?,purchase_gst=?,selling_price=?,
                   gst_rate=?,igst_rate=?,tax_inclusive=?,
                   last_stock_updated=?,updated_at=? WHERE item_code=?""",
                (
                    new_stock, self.price.value(), self.price.value(),
                    self.gst.currentText(), self.selling_price.value(),
                    self.selling_gst.currentText(),
                    self.selling_gst.currentText(),
                    int(self.selling_tax_inclusive.isChecked()),
                    now, now, self.product_code,
                ))
            old_purchase = float(
                self.product_record.get("purchase_price", 0) or 0)
            old_selling = float(
                self.product_record.get("selling_price", 0) or 0)
            if (
                abs(old_purchase - self.price.value()) > 0.005
                or abs(old_selling - self.selling_price.value()) > 0.005
            ):
                conn.execute(
                    """INSERT INTO price_history(
                        product_code,purchase_price,selling_price,mrp,
                        changed_at,changed_by,note
                    ) VALUES(?,?,?,?,?,?,?)""",
                    (
                        self.product_code, self.price.value(),
                        self.selling_price.value(),
                        float(self.product_record.get("mrp", 0) or 0),
                        now, self.current_user,
                        (
                            "Purchase invoice edited: "
                            if self.invoice_record else
                            "Purchase stock update: "
                        ) + self.invoice.text().strip(),
                    ))
            conn.execute(
                "UPDATE product_suppliers SET unit_price=?, last_received_price=?, "
                "last_ordered_date=? WHERE product_code=? AND supplier_code=?",
                (self.price.value(), self.price.value(),
                 self.purchase_date.date().toString("yyyy-MM-dd"),
                 self.product_code, supplier_code or ""))
            conn.execute(
                """INSERT OR IGNORE INTO product_suppliers(
                    product_code,supplier_code,unit_price,moq,lead_time_days,
                    is_primary,pack_size,last_ordered_date,last_received_price
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (self.product_code, supplier_code or "", self.price.value(), 1, 0,
                 0, 1, self.purchase_date.date().toString("yyyy-MM-dd"),
                 self.price.value()))
        self.accept()


class ManualStockDialog(QDialog):
    def __init__(self, db_name, product_code, product_name, current_stock,
                 current_user, parent=None):
        super().__init__(parent)
        self.db_name, self.product_code = db_name, product_code
        self.current_stock, self.current_user = int(current_stock or 0), current_user
        self.setWindowTitle("Manual Stock Update"); self.setMinimumWidth(560)
        root = QVBoxLayout(self); form = QGridLayout(); root.addLayout(form)
        self.action = QComboBox(); self.action.addItems([
            "Manual Stock In", "Manual Stock Out", "Damaged Stock",
            "Return From Customer", "Return To Supplier", "Stock Correction"])
        self.qty = QSpinBox(); self.qty.setRange(1, 9999999)
        self.reason = QComboBox(); self.reason.setEditable(True)
        self.reason.addItems([
            "Stock Correction", "Damaged Item", "Customer Return", "Supplier Return",
            "Missing Item", "Found Extra Stock", "Opening Stock Adjustment", "Internal Use"])
        self.notes = QTextEdit(); self.notes.setFixedHeight(65)
        self.new_stock = ro_label(str(self.current_stock))
        fields = [
            ("Product Code", ro_label(product_code)), ("Product Name", ro_label(product_name)),
            ("Current Stock", ro_label(str(current_stock))), ("Action Type", self.action),
            ("Quantity", self.qty), ("Reason", self.reason), ("New Stock", self.new_stock),
        ]
        for i, (label, widget) in enumerate(fields):
            add_field(form, i, 0, label, widget, span=2)
        form.addWidget(QLabel("Notes", styleSheet=LABEL_SS), len(fields), 0)
        form.addWidget(self.notes, len(fields), 1, 1, 3)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = _GBtn("Cancel", "ghost"); save = _GBtn("Update Stock", "success")
        cancel.clicked.connect(self.reject); save.clicked.connect(self._save)
        buttons.addWidget(cancel); buttons.addWidget(save); root.addLayout(buttons)
        self.action.currentTextChanged.connect(self._calculate)
        self.qty.valueChanged.connect(self._calculate); self._calculate()

    def _calculate(self):
        inbound = self.action.currentText() in ("Manual Stock In", "Return From Customer")
        delta = self.qty.value() if inbound else -self.qty.value()
        self.new_stock.setText(str(max(0, self.current_stock + delta)))

    def _save(self):
        inbound = self.action.currentText() in ("Manual Stock In", "Return From Customer")
        qty_in, qty_out = (self.qty.value(), 0) if inbound else (0, self.qty.value())
        new_stock = max(0, self.current_stock + qty_in - qty_out)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_name) as conn:
            conn.execute(
                """INSERT INTO stock_update_logs(
                    product_code,action_type,qty_in,qty_out,old_stock,new_stock,
                    reason,updated_by,notes,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (self.product_code, self.action.currentText(), qty_in, qty_out,
                 self.current_stock, new_stock, self.reason.currentText().strip(),
                 self.current_user, self.notes.toPlainText().strip(), now))
            conn.execute(
                "UPDATE products SET stock=?, last_stock_updated=?, updated_at=? "
                "WHERE item_code=?",
                (new_stock, now, now, self.product_code))
        self.accept()


class PurchaseInvoiceDetailDialog(QDialog):
    """Read-only purchase invoice detail for one product."""
    def __init__(self, record, product_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            f"Purchase Invoice — {record.get('invoice_number', '')}")
        self.setMinimumWidth(620)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        title = QLabel("Purchase Invoice Details")
        title.setStyleSheet(
            f"font-size:17px;font-weight:700;color:{C['text']};"
            "background:transparent;border:none;")
        root.addWidget(title)

        section, grid = make_section("Invoice Information", "🧾")
        quantity = float(record.get("quantity", 0) or 0)
        purchase_price = float(record.get("purchase_price", 0) or 0)
        selling_price = float(record.get("selling_price", 0) or 0)
        total_value = float(
            record.get("net_amount")
            or quantity * purchase_price
            or 0)
        values = [
            ("Invoice Number", record.get("invoice_number", "")),
            ("Supplier", record.get("supplier_name", "")),
            ("Purchase Date", record.get("purchase_date", "")),
            ("Product Name", product_name),
            ("Quantity Purchased", f"{quantity:g}"),
            ("Purchase Price", f"₹ {purchase_price:,.2f}"),
            ("Selling Price", f"₹ {selling_price:,.2f}"),
            ("Total Value", f"₹ {total_value:,.2f}"),
        ]
        for index, (label, value) in enumerate(values):
            add_field(
                grid, index // 2, (index % 2) * 2,
                label, ro_label(str(value or "—")))
        root.addWidget(section)
        close = _GBtn("Close", "ghost")
        close.clicked.connect(self.accept)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(close)
        root.addLayout(row)


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
        ensure_global_input_guard()
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
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setUsesScrollButtons(True)

        self._build_tab_basic()
        self._build_tab_pricing()
        self._build_tab_inventory()
        self._build_tab_supplier()
        self._build_tab_purchase_history()
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:#f5f5f7;")
        wrap = QWidget(); wrap.setStyleSheet("background:#f5f5f7;")
        wrap.setMinimumWidth(0)
        wrap.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.tabs.setMinimumWidth(0)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
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

        sec, g = make_section("Product Identity", "🔖")

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
        self.f_use_alias_bill.setToolTip("When checked, the first alias is used during billing")
        self.f_prod_type = QComboBox()
        self.f_prod_type.addItems(["Goods", "Service", "Digital", "Composite"])
        self.f_prod_type.hide()
        self.f_desc = QTextEdit()
        self.f_desc.setPlaceholderText("Product description, material details, care notes…")
        self.f_desc.setFixedHeight(78)

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
        add_field(g, r, 0, "Alias Name", self.f_alias,
                  hint="Comma-separated · used in billing search", span=2)
        r += 1
        g.addWidget(self.f_use_alias_bill, r, 1, 1, 3,
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        r += 1
        add_field(g, r, 0, "Product Description", self.f_desc, span=2)
        lay.addWidget(sec)

        # Image + key textile style fields in a balanced two-panel row.
        media_row = QHBoxLayout()
        media_row.setContentsMargins(0, 0, 0, 0)
        media_row.setSpacing(12)

        sec_img, g_img = make_section("Product Image", "🖼️")
        img_row = QHBoxLayout()
        self.img_label = QLabel("No Image")
        self.img_label.setFixedSize(120, 120); self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        sec_style, g_style = make_section("Additional", "📦")
        self.f_unit = QComboBox(); self.f_unit.setEditable(True)
        self.f_unit.addItems(["Piece", "Pair", "Set", "Box", "Pack", "Meter"])
        self.f_pack_size = QSpinBox()
        self.f_pack_size.setFixedHeight(38)
        self.f_pack_size.setStyleSheet(_NO_ARROW)
        self.f_pack_size.setRange(1, 99999); self.f_pack_size.setValue(1)
        self.f_status = QComboBox()
        self.f_status.addItems(["Active", "Draft", "Inactive", "Discontinued"])
        add_field(g_style, 0, 0, "Unit", self.f_unit, span=2)
        add_field(g_style, 1, 0, "Pack Size", self.f_pack_size, span=2)
        add_field(g_style, 2, 0, "Product Status", self.f_status, span=2)

        sec_img.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sec_style.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        media_row.addWidget(sec_img, 1)
        media_row.addWidget(sec_style, 1)
        lay.addLayout(media_row)

        # Classification
        sec2, g2 = make_section("Product Classification", "🗂️")

        self.f_product_group = QComboBox()
        self.f_product_group.setEditable(True)
        self.f_product_group.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.f_product_group.setProperty("supportsAddNew", True)
        self.f_product_group.addItems([""] + list(dict.fromkeys([
            "Apparel", "Footwear", "Accessories", "Innerwear",
            "Seasonal Collection",
        ] + get_saved_product_values(self.db_name, "product_group"))))
        self.f_product_group.lineEdit().setPlaceholderText("Select or add product group")
        _apply_combo_delegate(self.f_product_group)

        self.f_category = QComboBox(); self.f_category.setEditable(True)
        self.f_category.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.f_category.setProperty("supportsAddNew", True)
        self.f_category.addItems(list(dict.fromkeys([
            "",
            "Shirts", "T-Shirts", "Polo T-Shirts", "Jeans", "Trousers",
            "Formal Pants", "Chinos", "Shorts", "Blazers", "Suits",
            "Jackets", "Hoodies", "Sweatshirts", "Kurta", "Innerwear",
            "Accessories",
        ] + get_saved_product_values(self.db_name, "category"))))
        self.f_category.lineEdit().setPlaceholderText("Select or add category")
        self.f_category.currentTextChanged.connect(self._on_category_changed)

        self.f_sub_cat = QComboBox()
        self.f_sub_cat.setEditable(True)
        self.f_sub_cat.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.f_sub_cat.setProperty("supportsAddNew", True)
        self.f_sub_cat.addItem("")
        self.f_sub_cat.lineEdit().setPlaceholderText(
            "Select or enter a new sub-category"
        )
        _apply_combo_delegate(self.f_sub_cat)
        self.f_brand = QComboBox()
        self.f_brand.setEditable(True)
        self.f_brand.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.f_brand.setProperty("supportsAddNew", True)
        self.f_brand.addItems([""] + get_saved_product_values(self.db_name, "brand"))
        self.f_brand.lineEdit().setPlaceholderText("Select or add brand")
        _apply_combo_delegate(self.f_brand)
        self.f_manufacturer = QLineEdit()
        self.f_manufacturer.setPlaceholderText("e.g. Raymond Ltd")
        self.f_manufacturer.hide()
        self.f_country = QLineEdit(); self.f_country.setText("India"); self.f_country.hide()

        # hidden stubs so _collect / _save_fields still work
        self.f_meter = QLineEdit(); self.f_meter.hide()
        self.f_tags  = QLineEdit(); self.f_tags.hide()

        r2 = 0
        add_field(g2, r2, 0, "Product Group", self.f_product_group)
        add_field(g2, r2, 2, "Category",      self.f_category)
        r2 += 1
        add_field(g2, r2, 0, "Sub-category",  self.f_sub_cat)
        add_field(g2, r2, 2, "Brand",         self.f_brand)
        r2 += 1
        lay.addWidget(sec2)

        # Textile information
        sec_textile, gt = make_section("Textile Information", "🧵")
        self.f_style_code = QLineEdit(); self.f_style_code.setPlaceholderText("Style / design code")

        def editable_combo(defaults, column=None, placeholder="Select or add"):
            combo = QComboBox(); combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.setProperty("supportsAddNew", True)
            saved = get_saved_product_values(self.db_name, column) if column else []
            combo.addItems([""] + list(dict.fromkeys(defaults + saved)))
            combo.lineEdit().setPlaceholderText(placeholder)
            _apply_combo_delegate(combo)
            return combo

        self.f_fabric = editable_combo(
            ["Cotton", "Linen", "Polyester", "Cotton Blend", "Denim", "Rayon",
             "Viscose", "Lycra", "Spandex", "Wool", "Silk", "Satin", "Terry Cotton"],
            "fabric_type", "Select or add fabric")
        self.f_size = QComboBox()
        self.f_size.addItems(["", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "Free Size"])
        self.f_color = editable_combo(
            ["Black", "White", "Navy Blue", "Sky Blue", "Grey", "Charcoal Grey",
             "Brown", "Beige", "Khaki", "Olive Green", "Green", "Maroon", "Red",
             "Yellow", "Orange", "Pink", "Purple", "Multi Color"],
            "color", "Select or add color")
        self.f_fit = editable_combo(
            ["Slim Fit", "Regular Fit", "Relaxed Fit", "Skinny Fit", "Comfort Fit", "Oversized"],
            "fit_type", "Select or add fit")
        self.f_pattern = editable_combo(
            ["Solid", "Checked", "Striped", "Printed", "Floral", "Self Design",
             "Textured", "Graphic Print"], "pattern", "Select or add pattern")
        self.f_sleeve = QComboBox()
        self.f_sleeve.addItems(["", "Full Sleeve", "Half Sleeve", "Sleeveless", "Roll-Up Sleeve"])
        self.f_collar = QComboBox()
        self.f_collar.addItems([
            "", "Regular Collar", "Mandarin Collar", "Chinese Collar", "Spread Collar",
            "Polo Neck", "Round Neck", "V Neck", "Turtle Neck", "Henley Neck",
        ])
        self.f_gender = QComboBox()
        self.f_gender.addItems(["", "Men", "Women", "Unisex", "Boys", "Girls"])
        self.f_season = QComboBox()
        self.f_season.addItems(["", "Summer", "Winter", "Monsoon", "Spring", "All Season"])
        self.f_occasion = editable_combo(
            ["Casual", "Formal", "Party Wear", "Wedding", "Office Wear", "Daily Wear",
             "Sports Wear", "Ethnic Wear", "Travel"],
            "occasion", "Select or add occasion")

        textile_fields = [
            ("Style Code", self.f_style_code), ("Fabric Type", self.f_fabric),
            ("Size", self.f_size), ("Color", self.f_color),
            ("Fit Type", self.f_fit), ("Pattern", self.f_pattern),
            ("Sleeve Type", self.f_sleeve), ("Neck / Collar Type", self.f_collar),
            ("Gender", self.f_gender), ("Season", self.f_season),
            ("Occasion", self.f_occasion),
        ]
        for index, (label, widget) in enumerate(textile_fields):
            row, side = divmod(index, 2)
            add_field(gt, row, side * 2, label, widget)
        lay.addWidget(sec_textile)

        # Hidden compatibility field.
        self.f_notes = QTextEdit(); self.f_notes.hide()
        lay.addStretch()
        self.tabs.addTab(page, "BASIC DETAIL")

    # ── TAB 2: PRICING ────────────────────────────────────

    def _build_tab_pricing(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        outer = QVBoxLayout(page); outer.setContentsMargins(0, 16, 0, 0); outer.setSpacing(0)

        # ── Two-column master layout ──────────────────────────
        cols = QHBoxLayout(); cols.setContentsMargins(0, 0, 0, 0); cols.setSpacing(16)

        # Left column — fields
        left_w = QWidget(); left_w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(left_w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)

        # Right column — live GST breakdown
        right_w = QWidget(); right_w.setStyleSheet("background:transparent;")
        right_w.setMinimumWidth(240); right_w.setMaximumWidth(320)
        right_w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        right_lay = QVBoxLayout(right_w); right_lay.setContentsMargins(0, 0, 0, 0); right_lay.setSpacing(12)

        cols.addWidget(left_w, 1)
        cols.addWidget(right_w, 0)
        outer.addLayout(cols)

        # ── FIELD WIDGETS ────────────────────────────────────
        self.f_mrp            = price_spin()
        self.f_purchase_price = price_spin()
        self.f_purchase_gst   = QComboBox()
        self.f_purchase_gst.addItems(["0%","5%","12%","18%","28%"])
        self.lbl_purchase_gst_amount = ro_label("₹ 0.00")
        self.lbl_purchase_actual = ro_label("₹ 0.00")
        self.f_selling_price  = price_spin()
        self.f_retail_price   = price_spin(); self.f_retail_price.hide()

        self.f_discount_pct = QDoubleSpinBox()
        self.f_discount_pct.setFixedHeight(38)
        self.f_discount_pct.setStyleSheet(_NO_ARROW)
        self.f_discount_pct.setRange(0, 100); self.f_discount_pct.setDecimals(2)
        self.f_discount_pct.setSuffix(" %")
        self.f_discount_pct.hide()
        self.f_discount_val = QDoubleSpinBox()
        self.f_discount_val.setFixedHeight(38)
        self.f_discount_val.setStyleSheet(_NO_ARROW)
        self.f_discount_val.setRange(0, 999999); self.f_discount_val.setDecimals(2)
        self.f_discount_val.setPrefix("₹ ")
        self.f_discount_val.hide()

        self.f_margin = QDoubleSpinBox()
        self.f_margin.setRange(-999, 9999); self.f_margin.setDecimals(1)
        self.f_margin.setSuffix(" %"); self.f_margin.setValue(0.0)
        self.f_margin.setFixedHeight(38)
        self.f_margin.setStyleSheet(_NO_ARROW)
        self.f_margin.setReadOnly(True)
        self.f_margin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.lbl_margin = self.f_margin   # alias so old refs still work
        self.f_profit = QDoubleSpinBox()
        self.f_profit.setRange(-9999999, 9999999); self.f_profit.setDecimals(2)
        self.f_profit.setPrefix("₹ "); self.f_profit.setValue(0.0)
        self.f_profit.setFixedHeight(38)
        self.f_profit.setStyleSheet(_NO_ARROW)
        self.f_profit.setReadOnly(True)
        self.f_profit.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.lbl_profit = self.f_profit   # alias so old setText refs still resolve

        # Hidden stubs
        self.f_wholesale_price   = price_spin(); self.f_wholesale_price.hide()
        self.f_dealer_price      = price_spin(); self.f_dealer_price.hide()
        self.f_min_selling_price = price_spin()
        self.lbl_markup          = ro_label("—")
        self.f_special_price     = price_spin()
        self.lbl_last_purchase_price = ro_label("—")
        self.lbl_average_purchase_price = ro_label("—")
        self.f_sp_from = QDateEdit(); self.f_sp_from.hide()
        self.f_sp_to   = QDateEdit(); self.f_sp_to.hide()

        self.f_tax_inclusive = ToggleSwitch("Tax Inclusive")
        self.f_tax_inclusive.setChecked(True)
        # f_tax_inclusive is ToggleSwitch — no stylesheet needed

        # GST fields
        self.f_tax_cat = QComboBox()
        self.f_tax_cat.addItems(["Standard", "Nil Rated", "Exempt", "Zero Rated", "Non-GST"])
        self.f_tax_cat.hide()
        self.f_hsn = QLineEdit(); self.f_hsn.setPlaceholderText("e.g. 6205")
        self.f_hsn.hide()
        self.f_gst_rate = QComboBox()
        self.f_gst_rate.addItems(["0%","5%","12%","18%","28%"])
        self.f_igst_rate = QComboBox(); self.f_igst_rate.addItems(["0%","5%","12%","18%","28%"])
        self.f_igst_rate.hide()
        self.f_tax_type  = QComboBox(); self.f_tax_type.addItems(["CGST+SGST", "IGST"])
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
                  self.f_min_selling_price, self.f_special_price,
                  self.f_discount_pct, self.f_discount_val,
                  self.lbl_purchase_gst_amount, self.lbl_purchase_actual,
                  self.f_purchase_gst, self.f_tax_cat, self.f_hsn, self.f_gst_rate,
                  self.f_igst_rate, self.f_tax_type,
                  self.lbl_cgst_rate, self.lbl_sgst_rate, self.lbl_markup,
                  self.lbl_last_purchase_price, self.lbl_average_purchase_price):
            w.setFixedHeight(FIELD_H)

        # ── LEFT: Price Tiers section ─────────────────────────
        sec, g = make_section("Retail Pricing", "💰")
        g.setHorizontalSpacing(12); g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)
        g.setColumnMinimumWidth(0, 110); g.setColumnMinimumWidth(2, 110)

        r = 0
        add_field(g, r, 0, "Purchase Price", self.f_purchase_price, required=True)
        add_field(g, r, 2, "Purchase GST %", self.f_purchase_gst)
        r += 1
        add_field(g, r, 0, "Purchase GST Amount", self.lbl_purchase_gst_amount, hint="Auto-calculated")
        add_field(g, r, 2, "Actual Cost", self.lbl_purchase_actual, hint="Purchase price + purchase GST")
        r += 1
        add_field(g, r, 0, "MRP", self.f_mrp, required=True)
        add_field(g, r, 2, "Selling Price", self.f_selling_price, required=True)
        r += 1
        add_field(g, r, 0, "Minimum Selling Price", self.f_min_selling_price)
        add_field(g, r, 2, "Offer Price", self.f_special_price, hint="Optional promotional price")
        r += 1
        add_field(g, r, 0, "Profit Per Piece", self.f_profit, hint="Auto: selling price − actual cost")
        add_field(g, r, 2, "Margin %", self.f_margin, hint="Auto: profit ÷ selling price")
        r += 1
        add_field(g, r, 0, "Markup %", self.lbl_markup, hint="Auto: profit ÷ actual cost")
        add_field(g, r, 2, "Last Purchase Price", self.lbl_last_purchase_price, hint="From latest price history")
        r += 1
        add_field(g, r, 0, "Average Purchase Price", self.lbl_average_purchase_price,
                  hint="From purchase price history", span=2)
        lay.addWidget(sec)

        # ── LEFT: GST & Tax section ───────────────────────────
        sec3, g3 = make_section("GST & Tax", "🧾")
        g3.setHorizontalSpacing(12); g3.setVerticalSpacing(10)
        g3.setColumnStretch(1, 1); g3.setColumnStretch(3, 1)
        g3.setColumnMinimumWidth(0, 110); g3.setColumnMinimumWidth(2, 110)

        r3 = 0
        add_field(g3, r3, 0, "Tax Type", self.f_tax_type)
        add_field(g3, r3, 2, "GST Rate", self.f_gst_rate, required=True)
        r3 += 1
        g3.addWidget(self.f_tax_inclusive, r3, 0, 1, 2,
                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        add_field(g3, r3, 2, "CGST %", self.lbl_cgst_rate, hint="Half of GST for local sales")
        r3 += 1
        add_field(g3, r3, 0, "SGST %", self.lbl_sgst_rate, hint="Half of GST for local sales")
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

        row_sp,  self._gst_lbl_sp   = _gst_row("Net Selling Price")
        row_gp,  self._gst_lbl_pct  = _gst_row("GST Rate")
        row_bp,  self._gst_lbl_base = _gst_row("Taxable Value")
        row_cg,  self._gst_lbl_cgst = _gst_row("CGST", indent=True)
        row_sg,  self._gst_lbl_sgst = _gst_row("SGST", indent=True)
        row_ig,  self._gst_lbl_igst = _gst_row("IGST", indent=True)
        row_ga,  self._gst_lbl_amt  = _gst_row("Total GST Amount")
        row_cp,  self._gst_lbl_cust = _gst_row("Final Selling Price")
        for row in [row_sp, row_gp, row_bp, row_cg, row_sg, row_ig, row_ga, row_cp]:
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
            """Auto-calculate profit, retail margin, and cost markup."""
            if actual_pp > 0 and sell > 0:
                profit = round(sell - actual_pp, 2)
                margin = round(profit / sell * 100, 1)
                markup = round(profit / actual_pp * 100, 1)
                col_m  = C["success"] if margin >= 0 else C["accent"]
                col_p  = C["success"] if profit >= 0 else C["accent"]
                self.f_margin.blockSignals(True)
                self.f_margin.setValue(margin)
                self.f_margin.setStyleSheet(
                    _NO_ARROW + f"QDoubleSpinBox{{color:{col_m};font-weight:700;}}")
                self.f_margin.blockSignals(False)
                self.lbl_markup.setText(f"{markup:.1f}%")
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
        self._recalculate_pricing = lambda: _sync_profit_margin(
            self.f_selling_price.value(), _actual_cost()
        )

        def on_purchase_changed():
            """Purchase price or GST changed → update actual cost + profit + margin."""
            actual = _actual_cost()
            gst_amount = round(actual - self.f_purchase_price.value(), 2)
            self.lbl_purchase_gst_amount.setText(f"\u20b9 {gst_amount:.2f}")
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

        self.f_gst_rate.currentTextChanged.connect(self._update_gst_panel)
        self.f_igst_rate.currentTextChanged.connect(self._update_gst_panel)
        self.f_tax_type.currentTextChanged.connect(self._update_gst_panel)
        self.f_tax_cat.currentTextChanged.connect(self._on_tax_category_changed)
        self.f_tax_inclusive.stateChanged.connect(self._update_gst_panel)
        on_purchase_changed()
        self._update_gst_panel()

    def _on_tax_category_changed(self, category):
        taxable = category == "Standard"
        for widget in (
            self.f_gst_rate, self.f_igst_rate, self.f_tax_type,
            self.f_tax_inclusive, self.f_hsn,
        ):
            widget.setEnabled(taxable)
        if not taxable:
            self.f_gst_rate.setCurrentText("0%")
            self.f_igst_rate.setCurrentText("0%")
        self._update_gst_panel()

    def _update_purchase_actual(self):
        """Kept for _save_fields / _populate compatibility."""
        pp = self.f_purchase_price.value()
        try:
            g = float(self.f_purchase_gst.currentText().replace("%","").strip())
        except Exception:
            g = 0.0
        actual = round(pp * (1 + g / 100), 2)
        self.lbl_purchase_gst_amount.setText(f"\u20b9 {actual - pp:.2f}")
        self.lbl_purchase_actual.setText(f"\u20b9 {actual:.2f}")
        self.lbl_purchase_actual.setStyleSheet(
            f"background:{C['bg_light']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:6px 10px;font-size:13px;"
            f"font-weight:700;color:{C['text']};min-height:38px;")

    def _update_discount_from_sell(self):
        pass   # logic now inline in on_sell_changed

    def _update_margin(self):
        if hasattr(self, "_recalculate_pricing"):
            self._recalculate_pricing()

    def _update_gst_panel(self):
        sp        = self.f_selling_price.value()
        interstate = self.f_tax_type.currentText().startswith("IGST")
        gst_str = self.f_gst_rate.currentText()
        self.f_igst_rate.setCurrentText(gst_str)
        inclusive = self.f_tax_inclusive.isChecked()
        try:
            gst_pct = float(gst_str.replace("%", "").strip())
        except Exception:
            gst_pct = 0.0

        half = gst_pct / 2
        self.lbl_cgst_rate.setText("—" if interstate else f"{half:.1f}%")
        self.lbl_sgst_rate.setText("—" if interstate else f"{half:.1f}%")

        if gst_pct == 0:
            self._gst_panel.setStyleSheet(
                f"QFrame{{background:{C['bg_light']};border:1.5px solid {C['border']};border-radius:10px;}}")
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}")
            self._gst_lbl_pct.setText("0%  — No GST")
            self._gst_lbl_base.setText(f"₹ {sp:.2f}")
            self._gst_lbl_cgst.setText("₹ 0.00")
            self._gst_lbl_sgst.setText("₹ 0.00")
            self._gst_lbl_igst.setText("₹ 0.00")
            self._gst_lbl_amt.setText("₹ 0.00")
            self._gst_lbl_cust.setText(f"₹ {sp:.2f}")
            self._gst_msg_lbl.setText("ℹ️  GST rate is 0% — no tax will be added to this product.")
            self._gst_msg_lbl.setStyleSheet(f"font-size:11px;color:{C['text3']};background:transparent;padding-top:4px;border:none;")
            return

        if inclusive:
            # GST is already in the selling price — extract it
            base    = round(sp / (1 + gst_pct / 100), 2)
            gst_amt = round(sp - base, 2)
            cgst = 0 if interstate else round(gst_amt / 2, 2)
            sgst = 0 if interstate else round(gst_amt - cgst, 2)
            igst = gst_amt if interstate else 0
            self._gst_panel.setStyleSheet(
                "QFrame{background:#F0FDF4;border:1.5px solid #86EFAC;border-radius:10px;}")
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}  (GST included)")
            self._gst_lbl_pct.setText(gst_str)
            self._gst_lbl_base.setText(f"₹ {base:.2f}")
            self._gst_lbl_cgst.setText(f"₹ {cgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_sgst.setText(f"₹ {sgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_igst.setText(f"₹ {igst:.2f}  ({gst_pct:.1f}%)")
            self._gst_lbl_amt.setText(f"₹ {gst_amt:.2f}")
            self._gst_lbl_cust.setText(f"₹ {sp:.2f}  ✅ (no extra charge)")
            self._gst_msg_lbl.setStyleSheet(f"font-size:11px;color:{C['success']};background:transparent;padding-top:4px;border:none;")
            self._gst_msg_lbl.setText(
                f"✅  GST included in ₹ {sp:.2f}.  "
                f"Base ₹ {base:.2f}  +  "
                f"{'IGST ₹ ' + format(igst, '.2f') if interstate else 'CGST ₹ ' + format(cgst, '.2f') + ' + SGST ₹ ' + format(sgst, '.2f')}  =  ₹ {sp:.2f}")
        else:
            # GST added on top of selling price
            gst_amt   = round(sp * gst_pct / 100, 2)
            cgst = 0 if interstate else round(gst_amt / 2, 2)
            sgst = 0 if interstate else round(gst_amt - cgst, 2)
            igst = gst_amt if interstate else 0
            cust_pays = round(sp + gst_amt, 2)
            self._gst_panel.setStyleSheet(
                "QFrame{background:#FFF7ED;border:1.5px solid #FDBA74;border-radius:10px;}")
            self._gst_lbl_sp.setText(f"₹ {sp:.2f}  (base / excl. GST)")
            self._gst_lbl_pct.setText(gst_str)
            self._gst_lbl_base.setText(f"₹ {sp:.2f}")
            self._gst_lbl_cgst.setText(f"₹ {cgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_sgst.setText(f"₹ {sgst:.2f}  ({half:.1f}%)")
            self._gst_lbl_igst.setText(f"₹ {igst:.2f}  ({gst_pct:.1f}%)")
            self._gst_lbl_amt.setText(f"₹ {gst_amt:.2f}")
            self._gst_lbl_cust.setText(f"₹ {cust_pays:.2f}  ⚠️ (GST added on top)")
            self._gst_msg_lbl.setStyleSheet(f"font-size:11px;color:{C['warning']};background:transparent;padding-top:4px;border:none;")
            self._gst_msg_lbl.setText(
                f"⚠️  GST added at billing.  "
                f"₹ {sp:.2f}  +  "
                f"{'IGST ₹ ' + format(igst, '.2f') if interstate else 'CGST ₹ ' + format(cgst, '.2f') + ' + SGST ₹ ' + format(sgst, '.2f')}  =  Customer pays ₹ {cust_pays:.2f}")

    # ── TAB 3: INVENTORY ──────────────────────────────────

    def _build_tab_inventory(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

        sec, g = make_section("Stock Summary", "📦")
        self.f_opening_stock = QSpinBox(); self.f_opening_stock.setRange(0, 9999999)
        self.f_opening_stock.setFixedHeight(38)
        self.f_opening_stock.setStyleSheet(_NO_ARROW)
        self.f_reorder_level = QSpinBox(); self.f_reorder_level.setRange(0, 9999999)
        self.f_reorder_level.setFixedHeight(38)
        self.f_reorder_level.setStyleSheet(_NO_ARROW)
        self.f_safety_stock  = QSpinBox(); self.f_safety_stock.setRange(0, 9999999)
        self.f_safety_stock.hide()
        self.f_safety_stock.setFixedHeight(38)
        self.f_safety_stock.setStyleSheet(_NO_ARROW)
        self.f_reorder_qty   = QSpinBox(); self.f_reorder_qty.setRange(0, 9999999)
        self.f_reorder_qty.setFixedHeight(38)
        self.f_reorder_qty.setStyleSheet(_NO_ARROW)
        self.f_net_quantity = QDoubleSpinBox()
        self.f_net_quantity.hide()
        self.f_net_quantity.setRange(0, 9999999)
        self.f_net_quantity.setDecimals(3)
        self.f_net_quantity.setFixedHeight(38)
        self.f_net_quantity.setStyleSheet(_NO_ARROW)
        self.f_max_stock     = QSpinBox(); self.f_max_stock.setRange(0, 9999999)
        self.f_max_stock.hide()
        self.f_max_stock.setFixedHeight(38)
        self.f_max_stock.setStyleSheet(_NO_ARROW)
        self.f_reserved_stock = QSpinBox(); self.f_reserved_stock.setRange(0, 9999999)
        self.f_reserved_stock.hide()
        self.f_damaged_stock = QSpinBox(); self.f_damaged_stock.setRange(0, 9999999)
        self.f_damaged_stock.setFixedHeight(38); self.f_damaged_stock.setStyleSheet(_NO_ARROW)
        self.f_returned_stock = QSpinBox(); self.f_returned_stock.setRange(0, 9999999)
        self.f_returned_stock.setFixedHeight(38); self.f_returned_stock.setStyleSheet(_NO_ARROW)
        self.f_min_order_qty = QSpinBox(); self.f_min_order_qty.setRange(1, 9999999)
        self.f_min_order_qty.setFixedHeight(38); self.f_min_order_qty.setStyleSheet(_NO_ARROW)
        self.lbl_current_stock = ro_label("0")
        self.lbl_available   = ro_label("—")
        self.lbl_stock_val   = ro_label("—")
        self.lbl_stock_status = ro_label("—")
        self.lbl_last_stock_updated = ro_label("—")
        self.lbl_days_left   = ro_label("—")
        self.lbl_days_left.hide()
        self.f_auto_reorder  = ToggleSwitch("Auto-generate PO when stock hits reorder level")
        self.f_auto_reorder.hide()
        self.f_allow_neg     = ToggleSwitch("Allow negative stock")
        self.f_returnable    = ToggleSwitch("Product is returnable"); self.f_returnable.setChecked(True)
        self.f_opening_stock.valueChanged.connect(self._update_stock_calcs)
        self.f_reorder_level.valueChanged.connect(self._update_stock_calcs)
        self.f_damaged_stock.valueChanged.connect(self._update_stock_calcs)
        self.f_returned_stock.valueChanged.connect(self._update_stock_calcs)
        self.f_purchase_price.valueChanged.connect(self._update_stock_calcs)

        r = 0
        add_field(g, r, 0, "Opening Stock",   self.f_opening_stock, required=True)
        add_field(g, r, 2, "Current Stock", self.lbl_current_stock, hint="Updated through stock movements")
        r += 1
        add_field(g, r, 0, "Available Stock", self.lbl_available,
                  hint="Current stock − reserved − damaged")
        add_field(g, r, 2, "Damaged Stock", self.f_damaged_stock,
                  hint="Damaged or defective pieces")
        r += 1
        add_field(g, r, 0, "Returned Stock", self.f_returned_stock,
                  hint="Customer returns or exchanges")
        add_field(g, r, 2, "Stock Value", self.lbl_stock_val,
                  hint="Current stock × average purchase price")
        r += 1
        add_field(g, r, 0, "Stock Status", self.lbl_stock_status,
                  hint="In Stock / Low Stock / Out of Stock")
        add_field(g, r, 2, "Last Stock Updated", self.lbl_last_stock_updated,
                  hint="Updated when stock details change")
        lay.addWidget(sec)

        sec_control, gc = make_section("Inventory Control & Location", "📍")
        r = 0
        add_field(gc, r, 0, "Reorder Level", self.f_reorder_level,
                  hint="Low-stock alert threshold")
        add_field(gc, r, 2, "Reorder Quantity", self.f_reorder_qty,
                  hint="Suggested purchase quantity")
        r += 1
        add_field(gc, r, 0, "Minimum Order Quantity", self.f_min_order_qty,
                  hint="Supplier MOQ")
        self.f_rack = QLineEdit(); self.f_rack.setPlaceholderText("e.g. Rack A-3")
        add_field(gc, r, 2, "Rack Location", self.f_rack)
        r += 1
        gc.addWidget(self.f_allow_neg, r, 0, 1, 2)
        gc.addWidget(self.f_returnable, r, 2, 1, 2)
        lay.addWidget(sec_control)

        # Hidden storage compatibility fields.
        self.f_warehouse = QComboBox(); self.f_warehouse.setEditable(True); self.f_warehouse.hide()
        self.f_warehouse.addItems(["Main Store"])
        self.f_bin  = QLineEdit(); self.f_bin.hide()

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

        self.custom_variant_table = QTableWidget(0, 4)
        self.custom_variant_table.setHorizontalHeaderLabels(
            ["Custom Variant", "Available Stock", "Update Stock", "Action"]
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

        self.variant_table = QTableWidget(0, 4)
        self.variant_table.setHorizontalHeaderLabels(
            ["Size", "Available Stock", "Update Stock", "Action"]
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

        # Hidden compatibility stubs. Stock is updated directly in the variant table.
        self.adj_frame = QFrame(); self.adj_frame.hide()
        self.adj_table = mini_table(["Type", "Qty", "Reason", "Date", "By"])
        self.adj_table.hide()

        lay.addStretch()
        self.tabs.addTab(page, "📦  Inventory")

    def _open_purchase_stock_dialog(self):
        product_code = self.edit_code or self.f_item_code.text().strip()
        if not self.edit_code:
            QMessageBox.information(self, "Save Product", "Save the product before adding a purchase invoice.")
            return
        current = int((get_product_full(self.db_name, product_code) or {}).get("stock", 0))
        dlg = PurchaseStockDialog(
            self.db_name, product_code, self.f_name.text().strip() or product_code,
            current, self.current_user, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.prod = get_product_full(self.db_name, product_code) or self.prod
            self._refresh_supplier_logs()
            self._load_purchase_history()
            self._update_stock_calcs()
            self._refresh_supplier_summary()
            self._load_history()

    def _open_manual_stock_dialog(self):
        product_code = self.edit_code or self.f_item_code.text().strip()
        if not self.edit_code:
            QMessageBox.information(self, "Save Product", "Save the product before updating stock.")
            return
        current = int((get_product_full(self.db_name, product_code) or {}).get("stock", 0))
        dlg = ManualStockDialog(
            self.db_name, product_code, self.f_name.text().strip() or product_code,
            current, self.current_user, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.prod = get_product_full(self.db_name, product_code) or self.prod
            self._refresh_supplier_logs()
            self._update_stock_calcs()

    def _refresh_supplier_logs(self):
        product_code = self.edit_code or ""
        if not hasattr(self, "supplier_log_table"):
            return
        self.supplier_log_table.setRowCount(0)
        self._supplier_log_rows = []
        if not product_code:
            return
        for record in get_purchase_invoice_logs(self.db_name, product_code):
            row = self.supplier_log_table.rowCount()
            self.supplier_log_table.insertRow(row)
            values = [
                record.get("created_at", ""), "Purchase Invoice",
                record.get("invoice_number", ""), record.get("invoice_date", ""),
                record.get("supplier_name", ""), record.get("quantity", 0), 0,
                f"₹ {float(record.get('purchase_price', 0) or 0):,.2f}",
                f"₹ {float(record.get('net_amount', 0) or 0):,.2f}",
                record.get("stock_after", 0), record.get("payment_status", ""),
                record.get("notes", ""),
            ]
            for col, value in enumerate(values):
                self.supplier_log_table.setItem(row, col, QTableWidgetItem(str(value)))
            self._supplier_log_rows.append(("invoice", record))
        for record in get_stock_update_logs(self.db_name, product_code):
            if record.get("action_type") == "Purchase Stock In":
                continue
            row = self.supplier_log_table.rowCount()
            self.supplier_log_table.insertRow(row)
            values = [
                record.get("created_at", ""), record.get("action_type", ""),
                record.get("reference_number", ""), "", record.get("supplier_name", ""),
                record.get("qty_in", 0), record.get("qty_out", 0), "—", "—",
                record.get("new_stock", 0), "—",
                " | ".join(filter(None, [record.get("reason", ""), record.get("notes", "")])),
            ]
            for col, value in enumerate(values):
                self.supplier_log_table.setItem(row, col, QTableWidgetItem(str(value)))
            self._supplier_log_rows.append(("stock", record))

    def _update_stock_calcs(self):
        current = int(
            self.prod.get("stock", self.f_opening_stock.value())
            if self.edit_code else self.f_opening_stock.value()
        )
        reserved = self.f_reserved_stock.value()
        damaged = self.f_damaged_stock.value()
        available = max(0, current - reserved - damaged)
        reorder = self.f_reorder_level.value()

        self.lbl_current_stock.setText(str(current))
        self.lbl_available.setText(str(available))

        _last, average = get_purchase_price_insights(
            self.db_name, self.edit_code or ""
        )
        cost = average or self.f_purchase_price.value()
        self.lbl_stock_val.setText(
            f"₹ {current * cost:,.2f}" if cost > 0 else "₹ 0.00"
        )

        if current <= 0:
            status, color = "Out of Stock", C["accent"]
        elif reorder > 0 and available <= reorder:
            status, color = "Low Stock", C["warning"]
        else:
            status, color = "In Stock", C["success"]
        self.lbl_stock_status.setText(status)
        self.lbl_stock_status.setStyleSheet(
            f"background:{C['bg_light']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:6px 10px;font-size:13px;"
            f"font-weight:700;color:{color};min-height:34px;"
        )
        saved_at = str(
            self.prod.get("last_stock_updated")
            or self.prod.get("updated_at")
            or ""
        )
        self.lbl_last_stock_updated.setText(
            saved_at or ("Will be set on save" if not self.edit_code else "—")
        )

    def _stock_update_timestamp(self):
        """Keep the prior timestamp unless a stock-related value changed."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.edit_code:
            return now
        changed = any([
            int(self.prod.get("opening_stock") or 0) != self.f_opening_stock.value(),
            int(self.prod.get("reserved_stock") or 0) != self.f_reserved_stock.value(),
            int(self.prod.get("damaged_stock") or 0) != self.f_damaged_stock.value(),
            int(self.prod.get("returned_stock") or 0) != self.f_returned_stock.value(),
            bool(getattr(self, "_variant_pending", {})),
        ])
        return now if changed else str(
            self.prod.get("last_stock_updated")
            or self.prod.get("updated_at")
            or now
        )

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
            table = QTableWidget(0, 4)
            table.setHorizontalHeaderLabels(
                ["Color", "Available Stock", "Update Stock", "Action"]
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
        self.lbl_current_stock.setText(str(
            available_total if self.edit_code else pending_total
        ))
        self.lbl_available.setText(str(available_total))

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

    def _stock_update_qty(self):
        if (
            self.f_has_variants.isChecked()
            or self.f_has_color_variants.isChecked()
            or self.f_has_custom_variants.isChecked()
        ):
            return self._variant_pending_total()
        return self.f_opening_stock.value() if not self.edit_code else 0

    def _do_adj(self):
        if not self.edit_code:
            QMessageBox.information(self, "Info", "Save the product first.")
            return
        p = get_product_full(self.db_name, self.edit_code)
        dlg = StockAdjDialog(self.db_name, self.edit_code,
                             self.f_name.text() or self.edit_code,
                             p.get("stock", 0) if p else 0, self.current_user, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_adj()

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
        self.lbl_supplier_master_code = ro_label("—")
        self.lbl_supplier_contact = ro_label("—")
        self.lbl_supplier_phone = ro_label("—")
        self.lbl_supplier_email = ro_label("—")
        self.lbl_supplier_gstin = ro_label("—")
        self.lbl_supplier_address = ro_label("—")
        add_field(g_top, 2, 0, "Supplier Code", self.lbl_supplier_master_code)
        add_field(g_top, 2, 2, "Contact Person", self.lbl_supplier_contact)
        add_field(g_top, 3, 0, "Phone", self.lbl_supplier_phone)
        add_field(g_top, 3, 2, "Email", self.lbl_supplier_email)
        add_field(g_top, 4, 0, "GSTIN", self.lbl_supplier_gstin)
        add_field(g_top, 4, 2, "Address", self.lbl_supplier_address)

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

        def _line(placeholder=""):
            w = QLineEdit(); w.setFixedHeight(38); w.setPlaceholderText(placeholder)
            return w

        def _supplier_group(title):
            box = QFrame()
            box.setStyleSheet(
                "QFrame{background:#ffffff;border:1px solid #dbeafe;border-radius:8px;}")
            vl = QVBoxLayout(box); vl.setContentsMargins(12, 10, 12, 12); vl.setSpacing(8)
            heading = QLabel(title)
            heading.setStyleSheet(
                "font-size:12px;font-weight:700;color:#1d4ed8;"
                "background:transparent;border:none;")
            vl.addWidget(heading)
            grid = QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(9)
            grid.setColumnStretch(1, 1); grid.setColumnStretch(3, 1)
            vl.addLayout(grid)
            nsf_lay.addWidget(box)
            return grid

        # Basic information
        self.f_new_sup_name = _line("Supplier / business name")
        self.f_new_sup_code = _line("Auto-generated if left blank")
        self.f_new_sup_contact = _line("Contact person")
        self.f_new_sup_mobile = _line("+91 98765 43210")
        self.f_new_sup_whatsapp = _line("+91 98765 43210")
        self.f_new_sup_email = _line("supplier@example.com")
        self.f_new_sup_gstin = _line("15-character GSTIN")
        self.f_new_sup_pan = _line("10-character PAN")
        basic = _supplier_group("Basic Information")
        add_field(basic, 0, 0, "Supplier Name *", self.f_new_sup_name)
        add_field(basic, 0, 2, "Supplier Code", self.f_new_sup_code)
        add_field(basic, 1, 0, "Contact Person", self.f_new_sup_contact)
        add_field(basic, 1, 2, "Mobile Number", self.f_new_sup_mobile)
        add_field(basic, 2, 0, "WhatsApp Number", self.f_new_sup_whatsapp)
        add_field(basic, 2, 2, "Email", self.f_new_sup_email)
        add_field(basic, 3, 0, "GSTIN", self.f_new_sup_gstin)
        add_field(basic, 3, 2, "PAN Number", self.f_new_sup_pan)

        # Address information
        self.f_new_sup_address1 = _line("Building, street, area")
        self.f_new_sup_address2 = _line("Landmark or additional address")
        self.f_new_sup_city = _line("City")
        self.f_new_sup_state = _line("State")
        self.f_new_sup_pincode = _line("Pincode")
        self.f_new_sup_country = _line("Country")
        self.f_new_sup_country.setText("India")
        address = _supplier_group("Address Information")
        add_field(address, 0, 0, "Address Line 1", self.f_new_sup_address1, span=2)
        add_field(address, 1, 0, "Address Line 2", self.f_new_sup_address2, span=2)
        add_field(address, 2, 0, "City", self.f_new_sup_city)
        add_field(address, 2, 2, "State", self.f_new_sup_state)
        add_field(address, 3, 0, "Pincode", self.f_new_sup_pincode)
        add_field(address, 3, 2, "Country", self.f_new_sup_country)

        # Banking information
        self.f_new_sup_account_holder = _line("Name as per bank account")
        self.f_new_sup_bank = _line("Bank name")
        self.f_new_sup_branch = _line("Branch name")
        self.f_new_sup_account_number = _line("Account number")
        self.f_new_sup_ifsc = _line("IFSC code")
        self.f_new_sup_upi = _line("name@bank")
        banking = _supplier_group("Banking Information")
        add_field(banking, 0, 0, "Account Holder Name", self.f_new_sup_account_holder)
        add_field(banking, 0, 2, "Bank Name", self.f_new_sup_bank)
        add_field(banking, 1, 0, "Branch Name", self.f_new_sup_branch)
        add_field(banking, 1, 2, "Account Number", self.f_new_sup_account_number)
        add_field(banking, 2, 0, "IFSC Code", self.f_new_sup_ifsc)
        add_field(banking, 2, 2, "UPI ID", self.f_new_sup_upi)

        # Purchase configuration
        self.f_new_sup_payment_terms = QComboBox()
        self.f_new_sup_payment_terms.addItems(
            ["Immediate", "Net 7", "Net 15", "Net 30", "Net 45", "Net 60", "Net 90"])
        self.f_new_sup_payment_terms.setCurrentText("Net 30")
        self.f_new_sup_payment_terms.setFixedHeight(38)
        _apply_combo_delegate(self.f_new_sup_payment_terms)
        self.f_new_sup_credit = price_spin()
        self.f_new_sup_default_lead = QSpinBox()
        self.f_new_sup_default_lead.setRange(0, 365)
        self.f_new_sup_default_lead.setSuffix(" days")
        self.f_new_sup_default_lead.setFixedHeight(38)
        self.f_new_sup_default_lead.setStyleSheet(_NO_ARROW)
        self.f_new_sup_payment_method = QComboBox()
        self.f_new_sup_payment_method.addItems(
            ["", "Cash", "Bank Transfer", "UPI", "Cheque", "Credit", "Other"])
        self.f_new_sup_payment_method.setFixedHeight(38)
        _apply_combo_delegate(self.f_new_sup_payment_method)
        self.f_new_sup_notes = QTextEdit()
        self.f_new_sup_notes.setPlaceholderText("Purchase notes or supplier instructions")
        self.f_new_sup_notes.setFixedHeight(72)
        purchase = _supplier_group("Purchase Configuration")
        add_field(purchase, 0, 0, "Payment Terms", self.f_new_sup_payment_terms)
        add_field(purchase, 0, 2, "Credit Limit", self.f_new_sup_credit)
        add_field(purchase, 1, 0, "Default Lead Time", self.f_new_sup_default_lead)
        add_field(purchase, 1, 2, "Preferred Payment Method", self.f_new_sup_payment_method)
        purchase.addWidget(QLabel("Notes", styleSheet=LABEL_SS), 2, 0)
        purchase.addWidget(self.f_new_sup_notes, 2, 1, 1, 3)
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

        self.f_supplier_code = QLineEdit(); self.f_supplier_code.setPlaceholderText("Supplier's product SKU/code")
        self.f_supplier_code.setFixedHeight(38)
        self.f_supplier_product_name = QLineEdit()
        self.f_supplier_product_name.setPlaceholderText("Supplier's name for this product")
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
        add_field(g2, r2, 2, "Supplier Product Name", self.f_supplier_product_name)
        r2 += 1
        add_field(g2, r2, 0, "MOQ",                 self.f_sup_moq,        hint="Min order quantity")
        add_field(g2, r2, 2, "Default Order Qty",   self.f_sup_default_qty)
        r2 += 1
        add_field(g2, r2, 0, "Lead Time",           self.f_lead_time,      hint="Days to restock")
        add_field(g2, r2, 2, "Last Purchase Price", self.f_last_purchase)
        r2 += 1
        g2.addWidget(self.f_is_primary, r2, 0, 1, 4)
        lay.addWidget(sec2)

        summary_sec, summary_grid = make_section("Purchase & Supplier Statistics", "📊")
        self.lbl_sup_last_date = ro_label("—")
        self.lbl_sup_last_invoice = ro_label("—")
        self.lbl_sup_avg_price = ro_label("—")
        self.lbl_sup_total_qty = ro_label("0")
        self.lbl_sup_total_value = ro_label("₹ 0.00")
        self.lbl_sup_available = ro_label("0")
        self.lbl_sup_contribution = ro_label("0.0%")
        summary_fields = [
            ("Last Purchase Date", self.lbl_sup_last_date),
            ("Last Invoice Number", self.lbl_sup_last_invoice),
            ("Average Purchase Price", self.lbl_sup_avg_price),
            ("Total Purchased Quantity", self.lbl_sup_total_qty),
            ("Total Purchase Value", self.lbl_sup_total_value),
            ("Available Stock From Supplier", self.lbl_sup_available),
            ("Supplier Contribution %", self.lbl_sup_contribution),
        ]
        for i, (label, widget) in enumerate(summary_fields):
            add_field(summary_grid, i // 2, (i % 2) * 2, label, widget)
        lay.addWidget(summary_sec)

        log_sec, log_grid = make_section("Purchase & Stock Log", "🧾")
        log_actions = QHBoxLayout()
        log_actions.addStretch()
        self.btn_edit_invoice_log = _GBtn("Edit Selected Invoice", "warning")
        self.btn_edit_invoice_log.clicked.connect(self._edit_selected_invoice)
        log_actions.addWidget(self.btn_edit_invoice_log)
        log_grid.addLayout(log_actions, 0, 0, 1, 4)
        self.supplier_log_table = mini_table([
            "Date", "Type", "Invoice / Reference", "Invoice Date", "Supplier",
            "Qty In", "Qty Out", "Purchase Price", "Net Amount", "Available Stock",
            "Payment Status", "Notes"
        ], height=300)
        self.supplier_log_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.supplier_log_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        log_grid.addWidget(self.supplier_log_table, 1, 0, 1, 4)
        lay.addWidget(log_sec)
        self._supplier_log_section = log_sec
        self._supplier_log_rows = []

        # ── Linked Suppliers list (shows existing links after save) ───────────
        self._sec_linked, g_linked = make_section("Linked Suppliers", "\U0001f517")
        self._linked_list = QWidget(); self._linked_list.setStyleSheet("background:transparent;")
        self._linked_vlay = QVBoxLayout(self._linked_list)
        self._linked_vlay.setContentsMargins(4, 4, 4, 4); self._linked_vlay.setSpacing(6)
        g_linked.addWidget(self._linked_list, 0, 0, 1, 4)
        lay.addWidget(self._sec_linked)

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
            # Existing supplier found — auto-fill contact details.
            row = get_supplier_by_name(self.db_name, match)
            if row:
                self.f_supplier_phone.setText(
                    row.get("mobile_number","") or row.get("phone",""))
                self.f_supplier_email.setText(row.get("email",""))
                self.lbl_supplier_master_code.setText(row.get("code", "") or "—")
                self.lbl_supplier_contact.setText(row.get("contact_person", "") or "—")
                self.lbl_supplier_phone.setText(
                    row.get("mobile_number", "") or row.get("phone", "") or "—")
                self.lbl_supplier_email.setText(row.get("email", "") or "—")
                self.lbl_supplier_gstin.setText(row.get("gstin", "") or "—")
                address = ", ".join(filter(None, [
                    row.get("address_line1", "") or row.get("address", ""),
                    row.get("address_line2", ""), row.get("city", ""),
                    row.get("state", ""), row.get("pincode", "")]))
                self.lbl_supplier_address.setText(address or "—")
                if self.f_lead_time.value() == 0:
                    self.f_lead_time.setValue(row.get("default_lead_time", 0) or 0)
            self._new_sup_frame.setVisible(False)
            self._sup_status_lbl.setText(
                f"\u2705  Existing supplier selected")
            self._sup_status_lbl.setStyleSheet(
                "font-size:11px;color:#16a34a;background:transparent;border:none;")
        else:
            # No match — show create-new panel
            self._new_sup_frame.setVisible(True)
            self.f_new_sup_name.setText(text)
            if not self.f_new_sup_country.text().strip():
                self.f_new_sup_country.setText("India")
            self._sup_status_lbl.setText(
                "\u2795  New supplier — fill details below to create")
            self._sup_status_lbl.setStyleSheet(
                "font-size:11px;color:#0369a1;background:transparent;border:none;")
        self._refresh_supplier_summary()

    def _refresh_supplier_summary(self):
        if not hasattr(self, "lbl_sup_total_qty"):
            return
        product_code = self.edit_code or ""
        supplier = get_supplier_by_name(
            self.db_name, self.f_supplier_name.currentText().strip())
        stats = get_supplier_product_stats(
            self.db_name, product_code, supplier["code"]) if product_code and supplier else {}
        self.lbl_sup_last_date.setText(stats.get("last_date") or "—")
        self.lbl_sup_last_invoice.setText(stats.get("last_invoice") or "—")
        self.lbl_sup_avg_price.setText(
            f"₹ {stats.get('average_price', 0):,.2f}" if stats else "—")
        self.lbl_sup_total_qty.setText(str(stats.get("total_qty", 0)))
        self.lbl_sup_total_value.setText(f"₹ {stats.get('total_value', 0):,.2f}")
        available = int((get_product_full(self.db_name, product_code) or {}).get("stock", 0)) if product_code else 0
        self.lbl_sup_available.setText(str(min(available, stats.get("total_qty", 0))))
        self.lbl_sup_contribution.setText(f"{stats.get('contribution', 0):.1f}%")

    def _view_supplier_profile(self):
        row = get_supplier_by_name(
            self.db_name, self.f_supplier_name.currentText().strip())
        if not row:
            QMessageBox.information(self, "Supplier", "Select an existing supplier first.")
            return
        details = [
            f"Code: {row.get('code', '')}", f"Contact: {row.get('contact_person', '')}",
            f"Phone: {row.get('mobile_number', '') or row.get('phone', '')}",
            f"WhatsApp: {row.get('whatsapp_number', '')}", f"Email: {row.get('email', '')}",
            f"GSTIN: {row.get('gstin', '')}", f"PAN: {row.get('pan_number', '')}",
            f"Payment Terms: {row.get('payment_terms', '')}",
            f"Credit Limit: ₹ {float(row.get('credit_limit', 0) or 0):,.2f}",
            f"Bank: {row.get('bank_name', '')}", f"UPI: {row.get('upi_id', '')}",
            f"Notes: {row.get('notes', '')}",
        ]
        QMessageBox.information(self, row.get("name", "Supplier"), "\n".join(details))

    def _focus_supplier_logs(self):
        self.tabs.setCurrentWidget(self.tabs.widget(3))
        self.supplier_log_table.setFocus()

    def _edit_selected_invoice(self):
        row = self.supplier_log_table.currentRow()
        if row < 0 or row >= len(self._supplier_log_rows):
            QMessageBox.information(self, "Select Invoice", "Select an invoice row to edit.")
            return
        row_type, record = self._supplier_log_rows[row]
        if row_type != "invoice":
            QMessageBox.information(self, "Invoice Only", "Only purchase invoice rows can be edited.")
            return

        product = get_product_full(self.db_name, self.edit_code) or {}
        dlg = PurchaseStockDialog(
            self.db_name, self.edit_code,
            self.f_name.text().strip() or self.edit_code,
            int(product.get("stock", 0) or 0), self.current_user,
            self, invoice_record=record)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.prod = get_product_full(self.db_name, self.edit_code) or self.prod
            self._refresh_supplier_logs()
            self._load_purchase_history()
            self._refresh_supplier_summary()
            self._update_stock_calcs()
            self._load_history()

    def _refresh_linked_suppliers(self):
        """Populate the Linked Suppliers section from DB."""
        # Clear existing
        while self._linked_vlay.count():
            item = self._linked_vlay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        product_code = self.edit_code
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
            name = self.f_new_sup_name.text().strip() or name
            terms_text = self.f_new_sup_payment_terms.currentText().strip()
            payment_days = 0 if terms_text == "Immediate" else int(
                "".join(ch for ch in terms_text if ch.isdigit()) or 0)
            sup_code = create_supplier(
                self.db_name, name,
                code = self.f_new_sup_code.text().strip(),
                contact_person = self.f_new_sup_contact.text().strip(),
                mobile_number = self.f_new_sup_mobile.text().strip(),
                whatsapp_number = self.f_new_sup_whatsapp.text().strip(),
                email = self.f_new_sup_email.text().strip(),
                gstin = self.f_new_sup_gstin.text().strip(),
                pan_number = self.f_new_sup_pan.text().strip(),
                address_line1 = self.f_new_sup_address1.text().strip(),
                address_line2 = self.f_new_sup_address2.text().strip(),
                city = self.f_new_sup_city.text().strip(),
                state = self.f_new_sup_state.text().strip(),
                pincode = self.f_new_sup_pincode.text().strip(),
                country = self.f_new_sup_country.text().strip(),
                account_holder_name = self.f_new_sup_account_holder.text().strip(),
                bank_name = self.f_new_sup_bank.text().strip(),
                branch_name = self.f_new_sup_branch.text().strip(),
                account_number = self.f_new_sup_account_number.text().strip(),
                ifsc = self.f_new_sup_ifsc.text().strip(),
                upi_id = self.f_new_sup_upi.text().strip(),
                payment_terms_days = payment_days,
                credit_limit = self.f_new_sup_credit.value(),
                default_lead_time = self.f_new_sup_default_lead.value(),
                preferred_payment_method =
                    self.f_new_sup_payment_method.currentText().strip(),
                notes = self.f_new_sup_notes.toPlainText().strip(),
            )
            if not sup_code:
                QMessageBox.warning(
                    self, "Supplier Not Created",
                    "The supplier code is already in use, or the supplier details "
                    "could not be saved.")
                return
            self.f_supplier_phone.setText(self.f_new_sup_mobile.text().strip())
            self.f_supplier_email.setText(self.f_new_sup_email.text().strip())
            # Refresh cache
            self._sup_names_cache = get_all_supplier_names(self.db_name)

        # Save product-supplier relationship
        save_product_supplier(
            self.db_name, product_code, sup_code,
            sup_sku     = self.f_supplier_code.text().strip(),
            unit_price  = self.f_last_purchase.value(),
            moq         = self.f_sup_moq.value(),
            lead_days   = self.f_lead_time.value() or (
                self.f_new_sup_default_lead.value() if not row else 0),
            is_primary  = int(self.f_is_primary.isChecked()),
            default_qty = self.f_sup_default_qty.value(),
            supplier_product_name = self.f_supplier_product_name.text().strip(),
        )
        self._refresh_linked_suppliers()
        self._refresh_supplier_summary()

    # ── TAB 5: PURCHASE HISTORY ───────────────────────────

    def _build_tab_purchase_history(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

        section, grid = make_section("Product Purchase History", "🧾")
        hint = QLabel("Click an invoice row to view its purchase details.")
        hint.setStyleSheet(HINT_SS)
        grid.addWidget(hint, 0, 0, 1, 4)
        self.purchase_history_table = mini_table([
            "Invoice Number", "Purchase Date", "Supplier Name",
            "Quantity Purchased", "Purchase Price", "Total Value",
            "Payment Status"
        ], height=420)
        self.purchase_history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.purchase_history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.purchase_history_table.cellClicked.connect(
            self._open_purchase_history_invoice)
        grid.addWidget(self.purchase_history_table, 1, 0, 1, 4)
        lay.addWidget(section)
        lay.addStretch()
        self._purchase_history_rows = []
        self.tabs.addTab(page, "🧾  Purchase History")

    def _load_purchase_history(self):
        self.purchase_history_table.setRowCount(0)
        self._purchase_history_rows = []
        if not self.edit_code:
            return
        rows = get_purchase_invoice_logs(self.db_name, self.edit_code)
        current_product = get_product_full(self.db_name, self.edit_code) or {}
        for record in rows:
            if not float(record.get("selling_price", 0) or 0):
                record["selling_price"] = float(
                    current_product.get("selling_price", 0) or 0)
            row = self.purchase_history_table.rowCount()
            self.purchase_history_table.insertRow(row)
            total_value = float(
                record.get("net_amount")
                or float(record.get("quantity", 0) or 0)
                * float(record.get("purchase_price", 0) or 0))
            values = [
                record.get("invoice_number", ""),
                record.get("purchase_date", ""),
                record.get("supplier_name", ""),
                record.get("quantity", 0),
                f"₹ {float(record.get('purchase_price', 0) or 0):,.2f}",
                f"₹ {total_value:,.2f}",
                record.get("payment_status", "Pending"),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.purchase_history_table.setItem(row, col, item)
            self._purchase_history_rows.append(record)

    def _open_purchase_history_invoice(self, row, _column):
        if row < 0 or row >= len(self._purchase_history_rows):
            return
        PurchaseInvoiceDetailDialog(
            self._purchase_history_rows[row],
            self.f_name.text().strip() or self.edit_code,
            self,
        ).exec()

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
        kpi_row.addWidget(kpi("Total Qty Sold", "lbl_total_sold"))
        kpi_row.addWidget(kpi("Total Revenue", "lbl_total_rev"))
        kpi_row.addWidget(kpi("Total Profit", "lbl_total_profit"))
        kpi_row.addWidget(kpi("Last Sold Date", "lbl_last_sold"))
        kpi_row.addWidget(kpi("Return Count", "lbl_returns"))
        lay.addLayout(kpi_row)

        sec, g = make_section("Product Performance", "📊")
        self.lbl_movement_status = ro_label("New Product")
        self.lbl_sales_30 = ro_label("0")
        self.lbl_sales_90 = ro_label("0")
        self.lbl_avg_sp    = ro_label("—")
        self.lbl_inv_count = ro_label("0")
        add_field(g, 0, 0, "Movement Status", self.lbl_movement_status)
        add_field(g, 0, 2, "Last 30 Days Sales", self.lbl_sales_30)
        add_field(g, 1, 0, "Last 90 Days Sales", self.lbl_sales_90)
        add_field(g, 1, 2, "Average Selling Price", self.lbl_avg_sp)
        add_field(g, 2, 0, "Sale Count", self.lbl_inv_count)
        lay.addWidget(sec)

        chart_sec, chart_grid = make_section("Monthly Sales Trend", "📈")
        self.monthly_sales_chart = _MonthlySalesChart()
        chart_grid.addWidget(self.monthly_sales_chart, 0, 0, 1, 4)
        lay.addWidget(chart_sec)

        sales_sec, sales_grid = make_section("Recent Sales", "🧾")
        self.recent_sales_table = mini_table([
            "Invoice Number", "Sale Date", "Qty Sold", "Selling Price",
            "Revenue", "Profit", "Return Status"
        ], height=250)
        sales_grid.addWidget(self.recent_sales_table, 0, 0, 1, 4)
        lay.addWidget(sales_sec)

        price_sec, price_grid = make_section("Price Change History", "💹")
        self.price_hist_table = mini_table(
            ["Date", "Purchase", "Selling", "MRP", "Changed By"], height=170)
        price_grid.addWidget(self.price_hist_table, 0, 0, 1, 4)
        lay.addWidget(price_sec)
        lay.addStretch()
        self.tabs.addTab(page, "📊  Sales History")

    def _load_history(self):
        if not self.edit_code:
            return
        p = get_product_full(self.db_name, self.edit_code) or {}
        rows = get_product_sales_rows(
            self.db_name, self.edit_code, p.get("name", ""))
        fallback_cost = float(
            p.get("last_purchase_price") or p.get("purchase_price") or 0)
        now = datetime.now()

        def parsed_date(value):
            text = str(value or "")[:19]
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
            return None

        total_qty = sum(row["qty"] for row in rows)
        total_revenue = sum(row["revenue"] for row in rows)
        total_profit = sum(
            row["revenue"] - row["qty"] * (
                row["cost"] if row["cost"] is not None else fallback_cost)
            for row in rows)
        dated_rows = [(row, parsed_date(row["date"])) for row in rows]
        dated_rows = [(row, date) for row, date in dated_rows if date]
        sales_30 = sum(
            row["qty"] for row, date in dated_rows
            if date >= now - timedelta(days=30))
        sales_90 = sum(
            row["qty"] for row, date in dated_rows
            if date >= now - timedelta(days=90))
        last_date = max((date for _row, date in dated_rows), default=None)
        returned = sum(
            1 for row in rows
            if str(row["return_status"]).lower() not in ("", "0", "no", "false", "none"))

        created = parsed_date(p.get("created_at"))
        if not rows and created and created >= now - timedelta(days=90):
            status, color = "New Product", C["blue"]
        elif not last_date or last_date < now - timedelta(days=90):
            status, color = "Dead Stock", C["accent"]
        elif sales_30 >= 10:
            status, color = "Fast Moving", C["success"]
        else:
            status, color = "Slow Moving", C["warning"]

        self.lbl_total_sold.setText(f"{total_qty:g}")
        self.lbl_total_rev.setText(f"₹ {total_revenue:,.2f}")
        self.lbl_total_profit.setText(f"₹ {total_profit:,.2f}")
        self.lbl_last_sold.setText(
            last_date.strftime("%d-%m-%Y") if last_date else "—")
        self.lbl_returns.setText(str(returned or int(p.get("return_count", 0) or 0)))
        self.lbl_sales_30.setText(f"{sales_30:g}")
        self.lbl_sales_90.setText(f"{sales_90:g}")
        self.lbl_avg_sp.setText(
            f"₹ {total_revenue / total_qty:,.2f}" if total_qty else "—")
        self.lbl_inv_count.setText(str(len({str(row["invoice"]) for row in rows})))
        self.lbl_movement_status.setText(status)
        self.lbl_movement_status.setStyleSheet(
            f"background:{C['bg_light']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:6px 10px;font-size:13px;"
            f"font-weight:700;color:{color};min-height:34px;")

        monthly = {}
        for row, date in dated_rows:
            key = date.strftime("%Y-%m")
            monthly[key] = monthly.get(key, 0) + row["qty"]
        month_keys = []
        cursor = datetime(now.year, now.month, 1)
        for offset in range(5, -1, -1):
            year = cursor.year
            month = cursor.month - offset
            while month <= 0:
                month += 12; year -= 1
            month_keys.append(f"{year:04d}-{month:02d}")
        self.monthly_sales_chart.set_values([
            (datetime.strptime(key, "%Y-%m").strftime("%b"), monthly.get(key, 0))
            for key in month_keys])

        self.recent_sales_table.setRowCount(0)
        for row in rows[:50]:
            table_row = self.recent_sales_table.rowCount()
            self.recent_sales_table.insertRow(table_row)
            cost = row["cost"] if row["cost"] is not None else fallback_cost
            profit = row["revenue"] - row["qty"] * cost
            values = [
                row["invoice"], row["date"], f"{row['qty']:g}",
                f"₹ {row['price']:,.2f}", f"₹ {row['revenue']:,.2f}",
                f"₹ {profit:,.2f}", row["return_status"] or "No",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.recent_sales_table.setItem(table_row, col, item)

        self.price_hist_table.setRowCount(0)
        for purchase, selling, mrp, changed_at, changed_by, _note in get_price_history(
            self.db_name, self.edit_code
        ):
            table_row = self.price_hist_table.rowCount()
            self.price_hist_table.insertRow(table_row)
            values = [
                changed_at, f"₹ {float(purchase or 0):,.2f}",
                f"₹ {float(selling or 0):,.2f}", f"₹ {float(mrp or 0):,.2f}",
                changed_by,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.price_hist_table.setItem(table_row, col, item)

    # ── TAB 7: AUDIT & ACTIVITY ───────────────────────────

    def _build_tab_audit(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(0, 16, 0, 0); lay.setSpacing(12)

        sec, g = make_section("Creation Information", "🗓️")
        self.lbl_created_at = ro_label("—"); self.lbl_created_by = ro_label("—")
        add_field(g, 0, 0, "Created Date", self.lbl_created_at)
        add_field(g, 0, 2, "Created By", self.lbl_created_by)
        lay.addWidget(sec)

        sec, g = make_section("Update Information", "✏️")
        self.lbl_updated_at = ro_label("—"); self.lbl_updated_by = ro_label("—")
        add_field(g, 0, 0, "Updated Date", self.lbl_updated_at)
        add_field(g, 0, 2, "Updated By", self.lbl_updated_by)
        lay.addWidget(sec)

        sec, g = make_section("Activity Tracking", "📍")
        self.lbl_last_price_change = ro_label("—")
        self.lbl_last_stock_change = ro_label("—")
        self.lbl_last_supplier_change = ro_label("—")
        self.lbl_last_purchase_linked = ro_label("—")
        self.lbl_last_invoice_linked = ro_label("—")
        add_field(g, 0, 0, "Last Price Change", self.lbl_last_price_change)
        add_field(g, 0, 2, "Last Stock Change", self.lbl_last_stock_change)
        add_field(g, 1, 0, "Last Supplier Change", self.lbl_last_supplier_change)
        add_field(g, 1, 2, "Last Purchase Linked", self.lbl_last_purchase_linked)
        add_field(g, 2, 0, "Last Invoice Linked", self.lbl_last_invoice_linked)
        lay.addWidget(sec)

        sec, g = make_section("Notes", "📝")
        self.lbl_audit_notes = ro_label("—")
        self.lbl_internal_notes = ro_label("—")
        self.lbl_audit_notes.setWordWrap(True)
        self.lbl_internal_notes.setWordWrap(True)
        add_field(g, 0, 0, "Notes", self.lbl_audit_notes, span=3)
        add_field(g, 1, 0, "Internal Notes", self.lbl_internal_notes, span=3)
        lay.addWidget(sec)

        sec, g = make_section("Change Log", "🔄")
        self.change_log_table = mini_table(
            ["Date", "Change Type", "Reference", "Details", "Changed By"], 230)
        g.addWidget(self.change_log_table, 0, 0, 1, 4)
        lay.addWidget(sec)

        sec, g = make_section("User Activity Log", "👤")
        self.user_activity_table = mini_table(
            ["Date", "User", "Activity", "Reference", "Notes"], 210)
        g.addWidget(self.user_activity_table, 0, 0, 1, 4)
        lay.addWidget(sec)

        hint = QLabel("🔒  Read-only. All changes are recorded automatically.")
        hint.setStyleSheet(f"color:{C['text3']};font-size:12px;padding:8px;border:none;background:transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        lay.addStretch()
        self.tabs.addTab(page, "🗃️  Audit & Activity")

    def _clear_audit(self):
        labels = (
            "lbl_created_at", "lbl_created_by", "lbl_updated_at", "lbl_updated_by",
            "lbl_last_price_change", "lbl_last_stock_change",
            "lbl_last_supplier_change", "lbl_last_purchase_linked",
            "lbl_last_invoice_linked", "lbl_audit_notes", "lbl_internal_notes",
        )
        for name in labels:
            label = getattr(self, name, None)
            if label is not None:
                label.setText("—")
        for name in ("change_log_table", "user_activity_table"):
            table = getattr(self, name, None)
            if table is not None:
                table.setRowCount(0)

    def _load_audit(self):
        self._clear_audit()
        if not self.edit_code:
            return
        p = self.prod
        self.lbl_created_at.setText(p.get("created_at", "—") or "—")
        self.lbl_created_by.setText(p.get("created_by", "—") or "—")
        self.lbl_updated_at.setText(p.get("updated_at", "—") or "—")
        self.lbl_updated_by.setText(p.get("updated_by", "—") or "—")
        self.lbl_audit_notes.setText(
            p.get("notes") or p.get("description") or "—")
        self.lbl_internal_notes.setText(p.get("internal_notes") or "—")

        activities = []
        price_dates, stock_dates, supplier_dates, purchase_dates = [], [], [], []
        latest_invoice = ("", "")

        for purchase, selling, mrp, changed_at, changed_by, note in get_price_history(
            self.db_name, self.edit_code
        ):
            date = str(changed_at or "")
            price_dates.append(date)
            details = (
                f"Purchase ₹{float(purchase or 0):,.2f} · "
                f"Selling ₹{float(selling or 0):,.2f} · "
                f"MRP ₹{float(mrp or 0):,.2f}"
            )
            activities.append({
                "date": date, "type": "Price Change", "reference": "",
                "details": details, "user": changed_by or "system",
                "notes": note or "",
            })

        for record in get_stock_update_logs(self.db_name, self.edit_code):
            date = str(record.get("created_at") or "")
            stock_dates.append(date)
            details = (
                f"Stock {int(record.get('old_stock') or 0)} → "
                f"{int(record.get('new_stock') or 0)}"
            )
            movement = []
            if int(record.get("qty_in") or 0):
                movement.append(f"In {int(record.get('qty_in') or 0)}")
            if int(record.get("qty_out") or 0):
                movement.append(f"Out {int(record.get('qty_out') or 0)}")
            if movement:
                details += " · " + " / ".join(movement)
            activities.append({
                "date": date,
                "type": record.get("action_type") or "Stock Change",
                "reference": record.get("reference_number") or "",
                "details": details,
                "user": record.get("updated_by") or "system",
                "notes": " · ".join(filter(None, [
                    record.get("reason"), record.get("notes")])),
            })

        for adj_type, qty, reason, adj_date, created_by, note in get_stock_history(
            self.db_name, self.edit_code
        ):
            date = str(adj_date or "")
            stock_dates.append(date)
            activities.append({
                "date": date, "type": f"Stock {adj_type or 'Change'}",
                "reference": "", "details": f"Quantity {int(qty or 0)}",
                "user": created_by or "system",
                "notes": " · ".join(filter(None, [reason, note])),
            })

        purchases = get_purchase_invoice_logs(self.db_name, self.edit_code)
        for record in purchases:
            date = str(
                record.get("purchase_date") or record.get("invoice_date")
                or record.get("created_at") or "")
            purchase_dates.append(date)
            invoice = str(record.get("invoice_number") or "")
            if not latest_invoice or date > latest_invoice[0]:
                latest_invoice = (date, invoice)
            activities.append({
                "date": date, "type": "Purchase Invoice Linked",
                "reference": invoice,
                "details": (
                    f"{record.get('supplier_name') or 'Supplier'} · "
                    f"Qty {int(record.get('quantity') or 0)} · "
                    f"₹{float(record.get('net_amount') or 0):,.2f}"
                ),
                "user": record.get("created_by") or "system",
                "notes": record.get("notes") or "",
            })

        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                supplier_rows = conn.execute(
                    """SELECT ps.supplier_code, ps.last_ordered_date,
                              ps.supplier_product_code, s.name
                       FROM product_suppliers ps
                       LEFT JOIN suppliers s ON s.code=ps.supplier_code
                       WHERE ps.product_code=?""",
                    (self.edit_code,),
                ).fetchall()
            for row in supplier_rows:
                date = str(row["last_ordered_date"] or "")
                supplier_dates.append(date)
                activities.append({
                    "date": date, "type": "Supplier Linked",
                    "reference": row["supplier_code"] or "",
                    "details": " · ".join(filter(None, [
                        row["name"], row["supplier_product_code"]])),
                    "user": p.get("updated_by") or "system", "notes": "",
                })
        except sqlite3.Error:
            pass

        activities.sort(key=lambda item: item["date"], reverse=True)
        self.lbl_last_price_change.setText(max(price_dates, default="") or "—")
        self.lbl_last_stock_change.setText(
            max(stock_dates, default="") or p.get("last_stock_updated") or "—")
        self.lbl_last_supplier_change.setText(
            max(supplier_dates, default="") or "—")
        self.lbl_last_purchase_linked.setText(
            max(purchase_dates, default="") or "—")
        if latest_invoice[1]:
            self.lbl_last_invoice_linked.setText(
                f"{latest_invoice[1]} · {latest_invoice[0]}")

        for activity in activities:
            row = self.change_log_table.rowCount()
            self.change_log_table.insertRow(row)
            values = [
                activity["date"], activity["type"], activity["reference"],
                activity["details"], activity["user"],
            ]
            for col, value in enumerate(values):
                self.change_log_table.setItem(
                    row, col, QTableWidgetItem(str(value or "—")))

            row = self.user_activity_table.rowCount()
            self.user_activity_table.insertRow(row)
            values = [
                activity["date"], activity["user"], activity["type"],
                activity["reference"], activity["notes"] or activity["details"],
            ]
            for col, value in enumerate(values):
                self.user_activity_table.setItem(
                    row, col, QTableWidgetItem(str(value or "—")))

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
                    px.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation))
                self.img_label.setText("")

    def _clear_image(self):
        self._image_blob = b""; self.img_label.clear(); self.img_label.setText("No Image")

    # ── Load / Reset / Populate ────────────────────────────

    def load_for_add(self):
        self.edit_code = None; self.prod = {}
        self._title_lbl.setText("Add Product"); self._btn_save.setText("💾  Save Product")
        self._reset_fields()
        self._clear_audit()
        self._refresh_reusable_product_dropdowns()
        self._refresh_sub_categories()
        self.f_item_code.setText(get_next_item_code(self.db_name))
        self.f_item_code.setReadOnly(True)
        self.f_auto_barcode.setVisible(True); self.f_auto_barcode.setChecked(False)
        self.f_barcode.setReadOnly(False)
        self._toggle_variants(False)
        self._toggle_color_variants(False)
        self._toggle_custom_variants(False)
        self.adj_frame.setVisible(False)
        self._refresh_supplier_logs()
        self._refresh_supplier_summary()
        self._load_purchase_history()
        self.tabs.setCurrentIndex(0)

    def _on_category_changed(self, category):
        self._refresh_sub_categories(category=category, preserve_current=False)

    def _refresh_sub_categories(self, category=None, preserve_current=True):
        if not hasattr(self, "f_sub_cat"):
            return
        current = self.f_sub_cat.currentText().strip() if preserve_current else ""
        category = (
            category.strip() if isinstance(category, str)
            else self.f_category.currentText().strip()
        )
        mapped = SUB_CATEGORY_OPTIONS.get(category, [])
        saved = get_saved_sub_categories(self.db_name, category)
        values = list(dict.fromkeys(mapped + saved))
        self.f_sub_cat.blockSignals(True)
        self.f_sub_cat.clear()
        self.f_sub_cat.addItem("")
        self.f_sub_cat.addItems(values)
        if current:
            index = self.f_sub_cat.findText(
                current, Qt.MatchFlag.MatchFixedString
            )
            if index >= 0:
                self.f_sub_cat.setCurrentIndex(index)
            else:
                self.f_sub_cat.setEditText(current)
        self.f_sub_cat.blockSignals(False)

    def _refresh_reusable_product_dropdowns(self):
        """Refresh editable dropdowns while preserving typed/current values."""
        configs = [
            (self.f_category, "category",
             ["Shirts", "T-Shirts", "Polo T-Shirts", "Jeans", "Trousers",
              "Formal Pants", "Chinos", "Shorts", "Blazers", "Suits",
              "Jackets", "Hoodies", "Sweatshirts", "Kurta", "Innerwear",
              "Accessories"]),
            (self.f_product_group, "product_group",
             ["Apparel", "Footwear", "Accessories", "Innerwear", "Seasonal Collection"]),
            (self.f_brand, "brand", []),
            (self.f_fabric, "fabric_type",
             ["Cotton", "Linen", "Polyester", "Cotton Blend", "Denim", "Rayon",
              "Viscose", "Lycra", "Spandex", "Wool", "Silk", "Satin", "Terry Cotton"]),
            (self.f_fit, "fit_type",
             ["Slim Fit", "Regular Fit", "Relaxed Fit", "Skinny Fit",
              "Comfort Fit", "Oversized"]),
            (self.f_color, "color",
             ["Black", "White", "Navy Blue", "Sky Blue", "Grey", "Charcoal Grey",
              "Brown", "Beige", "Khaki", "Olive Green", "Green", "Maroon", "Red",
              "Yellow", "Orange", "Pink", "Purple", "Multi Color"]),
            (self.f_pattern, "pattern",
             ["Solid", "Checked", "Striped", "Printed", "Floral", "Self Design",
              "Textured", "Graphic Print"]),
            (self.f_occasion, "occasion",
             ["Casual", "Formal", "Party Wear", "Wedding", "Office Wear",
              "Daily Wear", "Sports Wear", "Ethnic Wear", "Travel"]),
        ]
        for combo, column, defaults in configs:
            current = combo.currentText().strip()
            values = list(dict.fromkeys(defaults + get_saved_product_values(
                self.db_name, column
            )))
            combo.blockSignals(True)
            combo.clear()
            combo.addItems([""] + values)
            if current:
                index = combo.findText(current, Qt.MatchFlag.MatchFixedString)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setEditText(current)
            combo.blockSignals(False)

    def load_for_edit(self, item_code):
        self.edit_code = item_code
        self.prod = get_product_full(self.db_name, item_code) or {}
        self._title_lbl.setText(f"Edit — {item_code}"); self._btn_save.setText("💾  Update Product")
        self._reset_fields()
        self._refresh_reusable_product_dropdowns()
        self._refresh_sub_categories()
        self._populate()
        linked_suppliers = get_product_suppliers(self.db_name, item_code)
        if linked_suppliers:
            linked = next(
                (row for row in linked_suppliers if row.get("is_primary")),
                linked_suppliers[0])
            self.f_supplier_product_name.setText(
                linked.get("supplier_product_name", "") or "")
            self.f_sup_moq.setValue(int(linked.get("moq", 1) or 1))
            self.f_sup_default_qty.setValue(int(linked.get("pack_size", 1) or 1))
            self.f_is_primary.setChecked(bool(linked.get("is_primary")))
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
        self.adj_frame.setVisible(False)
        self._load_history(); self._load_audit()
        self._load_purchase_history()
        self._refresh_supplier_logs()
        self._refresh_linked_suppliers()
        self._refresh_supplier_summary()
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
        self.f_pack_size.setValue(1)
        self.f_warehouse.setCurrentText("Main Store")
        self.f_returnable.setChecked(True)
        self.f_is_primary.setChecked(True)
        self.f_tax_inclusive.setChecked(True)
        if hasattr(self, "f_new_sup_country"):
            self.f_new_sup_country.setText("India")
            self.f_new_sup_payment_terms.setCurrentText("Net 30")
        if hasattr(self, "_variant_radios"):
            self._variant_radios["Generic"].setChecked(True)
        self.f_margin.blockSignals(True)
        self.f_margin.setValue(0.0)
        self.f_margin.blockSignals(False)
        self.lbl_markup.setText("—")
        self.lbl_last_purchase_price.setText("—")
        self.lbl_average_purchase_price.setText("—")
        self.f_profit.blockSignals(True)
        self.f_profit.setValue(0.0)
        self.f_profit.blockSignals(False)
        self._update_stock_calcs()

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
        sv(self.f_style_code, "style_code");   sv(self.f_fabric, "fabric_type")
        sv(self.f_size, "size");               sv(self.f_color, "color")
        sv(self.f_fit, "fit_type");            sv(self.f_pattern, "pattern")
        sv(self.f_sleeve, "sleeve")
        sv(self.f_collar, "collar_type");      sv(self.f_gender, "gender")
        sv(self.f_season, "season");           sv(self.f_occasion, "occasion")
        sv(self.f_manufacturer, "manufacturer"); sv(self.f_country, "country_of_origin")
        sv(self.f_unit, "unit");              sv(self.f_pack_size, "pack_size", 1)
        sv(self.f_meter, "meter");             sv(self.f_tags, "tags")
        sv(self.f_desc, "description");       sv(self.f_notes, "internal_notes")
        sv(self.f_status, "status")
        img = p.get("image")
        if isinstance(img, (bytes, bytearray)) and img:
            self._image_blob = img; px = QPixmap(); px.loadFromData(img)
            if not px.isNull():
                self.img_label.setPixmap(
                    px.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
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
        old_tax_type = str(p.get("tax_type") or "")
        self.f_tax_type.setCurrentText(
            "IGST" if old_tax_type.startswith("IGST") else "CGST+SGST"
        )
        sv(self.f_cess_pct, "cess_pct")
        sv(self.f_tcs, "tcs_applicable");            sv(self.f_gst_ex, "gst_exemption_reason")
        self._update_purchase_actual()
        self._update_margin()
        self._on_tax_category_changed(self.f_tax_cat.currentText())
        last_purchase, average_purchase = get_purchase_price_insights(
            self.db_name, self.edit_code
        )
        if not last_purchase:
            last_purchase = float(
                p.get("last_purchase_price") or p.get("purchase_price") or 0
            )
        if not average_purchase:
            average_purchase = float(p.get("purchase_price") or 0)
        self.lbl_last_purchase_price.setText(
            f"₹ {last_purchase:,.2f}" if last_purchase else "—"
        )
        self.lbl_average_purchase_price.setText(
            f"₹ {average_purchase:,.2f}" if average_purchase else "—"
        )
        # Inventory
        sv(self.f_opening_stock, "opening_stock");   sv(self.f_reorder_level, "reorder_level")
        sv(self.f_safety_stock, "safety_stock");     sv(self.f_reorder_qty, "reorder_qty")
        sv(self.f_net_quantity, "net_quantity"); sv(self.f_max_stock, "max_stock")
        sv(self.f_reserved_stock, "reserved_stock")
        sv(self.f_damaged_stock, "damaged_stock")
        sv(self.f_returned_stock, "returned_stock")
        sv(self.f_min_order_qty, "min_order_qty", 1)
        sv(self.f_auto_reorder, "auto_reorder");     sv(self.f_allow_neg, "allow_neg_stock")
        sv(self.f_returnable, "is_returnable");      sv(self.f_warehouse, "warehouse")
        sv(self.f_rack, "rack_location");            sv(self.f_bin, "bin_location")
        self._update_stock_calcs()
        # Supplier
        sv(self.f_supplier_name, "supplier_name");   sv(self.f_supplier_code, "supplier_code")
        sv(self.f_supplier_phone, "supplier_phone"); sv(self.f_supplier_email, "supplier_email")
        sv(self.f_lead_time, "lead_time_days")
        sv(self.f_last_purchase, "last_purchase_price")
        if p.get("variant_type") not in (COLOR_STORAGE_GROUP, CUSTOM_STORAGE_GROUP):
            sv(self.f_has_variants, "has_variants")
            sv(self.f_variant_type, "variant_type")

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
            "product_group":         self.f_product_group.currentText().strip(),
            "category":              self.f_category.currentText().strip(),
            "sub_category":          self.f_sub_cat.currentText().strip(),
            "sleeve":                self.f_sleeve.currentText().strip(),
            "brand":                 self.f_brand.currentText().strip(),
            "style_code":            self.f_style_code.text().strip(),
            "fabric_type":           self.f_fabric.currentText().strip(),
            "size":                  self.f_size.currentText().strip(),
            "color":                 self.f_color.currentText().strip(),
            "fit_type":              self.f_fit.currentText().strip(),
            "pattern":               self.f_pattern.currentText().strip(),
            "collar_type":           self.f_collar.currentText().strip(),
            "gender":                self.f_gender.currentText().strip(),
            "season":                self.f_season.currentText().strip(),
            "occasion":              self.f_occasion.currentText().strip(),
            "manufacturer":          self.f_manufacturer.text().strip(),
            "country_of_origin":     self.f_country.text().strip() or "India",
            "hsn_code":              self.f_hsn.text().strip(),
            "barcode":               self.f_barcode.text().strip(),
            "tags":                  self.f_tags.text().strip(),
            "unit":                  self.f_unit.currentText().strip(),
            "pack_size":             self.f_pack_size.value(),
            "meter":                 self.f_meter.text().strip(),
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
            "reserved_stock":        self.f_reserved_stock.value(),
            "damaged_stock":         self.f_damaged_stock.value(),
            "returned_stock":        self.f_returned_stock.value(),
            "reorder_level":         self.f_reorder_level.value(),
            "safety_stock":          self.f_safety_stock.value(),
            "reorder_qty":           self.f_reorder_qty.value(),
            "min_order_qty":         self.f_min_order_qty.value(),
            "net_quantity":          self.f_net_quantity.value(),
            "max_stock":             self.f_max_stock.value(),
            "auto_reorder":          int(self.f_auto_reorder.isChecked()),
            "allow_neg_stock":       int(self.f_allow_neg.isChecked()),
            "is_returnable":         int(self.f_returnable.isChecked()),
            "warehouse":             self.f_warehouse.currentText().strip() or "Main Store",
            "rack_location":         self.f_rack.text().strip(),
            "bin_location":          self.f_bin.text().strip(),
            "last_stock_updated":    self._stock_update_timestamp(),
            "supplier_name":         self.f_supplier_name.currentText().strip(),
            "supplier_code":         self.f_supplier_code.text().strip(),
            "supplier_phone":        self.f_supplier_phone.text().strip(),
            "supplier_email":        self.f_supplier_email.text().strip(),
            "lead_time_days":        self.f_lead_time.value(),
            "last_purchase_price":   self.f_last_purchase.value(),
            "weight_kg":             self.prod.get("weight_kg", 0),
            "length_cm":             self.prod.get("length_cm", 0),
            "width_cm":              self.prod.get("width_cm", 0),
            "height_cm":             self.prod.get("height_cm", 0),
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
            "internal_notes":        self.f_notes.toPlainText().strip(),
            "status":                self.f_status.currentText(),
        }

    def _save(self):
        data = self._collect()
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
        current_stock = int(
            self.prod.get("stock", data["opening_stock"])
            if self.edit_code else data["opening_stock"]
        )
        if data["damaged_stock"] > current_stock:
            QMessageBox.warning(
                self, "Validation",
                "Damaged stock cannot be greater than current stock."
            )
            self.tabs.setCurrentIndex(2)
            self.f_damaged_stock.setFocus()
            return
        if (
            data["min_selling_price"] > 0
            and data["selling_price"] < data["min_selling_price"]
        ):
            QMessageBox.warning(
                self, "Validation",
                "Selling price cannot be below the minimum selling price."
            )
            self.tabs.setCurrentIndex(1)
            self.f_selling_price.setFocus()
            return
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
        filter_title = QLabel("Advanced Filter")
        filter_title.setStyleSheet(
            f"color:{C['text']};font-size:13px;font-weight:800;"
            "background:transparent;border:none;")
        fl.addWidget(filter_title)

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

        # ── KPI cards ──────────────────────────────────────
        self._kpi_labels = {}
        kpi_grid = QGridLayout()
        kpi_grid.setContentsMargins(0, 0, 0, 0)
        kpi_grid.setHorizontalSpacing(10)
        kpi_grid.setVerticalSpacing(10)
        kpi_specs = [
            ("total", "Total Products", "📦", C["blue"]),
            ("active", "Active Products", "✅", C["success"]),
            ("stock_qty", "Total Stock Qty", "🧮", "#5856D6"),
            ("stock_value", "Stock Value", "💰", "#AF52DE"),
            ("selling_value", "Selling Value", "🏷️", "#007AFF"),
            ("low_stock", "Low Stock Items", "⚠️", C["warning"]),
            ("out_stock", "Out of Stock Items", "⛔", C["accent"]),
            ("today_added", "Today Stock Added", "📥", "#00A67E"),
        ]
        for index, (key, title, icon, color) in enumerate(kpi_specs):
            card = QFrame()
            card.setMinimumHeight(82)
            card.setStyleSheet(f"""
                QFrame {{
                    background:{C['bg_white']}; border:1px solid {C['border']};
                    border-radius:13px; border-left:4px solid {color};
                }}
                QLabel {{ border:none; background:transparent; }}
            """)
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(13, 9, 13, 9)
            card_lay.setSpacing(3)
            title_lbl = QLabel(f"{icon}  {title}")
            title_lbl.setStyleSheet(
                f"color:{C['text3']};font-size:11px;font-weight:700;")
            value_lbl = QLabel("—")
            value_lbl.setStyleSheet(
                f"color:{C['text']};font-size:20px;font-weight:800;")
            card_lay.addWidget(title_lbl)
            card_lay.addWidget(value_lbl)
            self._kpi_labels[key] = value_lbl
            kpi_grid.addWidget(card, index // 4, index % 4)
        cl.addLayout(kpi_grid)

        # ── Table heading and column settings ──────────────
        table_head = QHBoxLayout()
        table_title = QLabel("Daily Product Control")
        table_title.setStyleSheet(
            f"color:{C['text']};font-size:15px;font-weight:800;"
            "background:transparent;")
        table_head.addWidget(table_title)
        table_head.addStretch()
        self.column_btn = QToolButton()
        self.column_btn.setText("⚙  Columns")
        self.column_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.column_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.column_btn.setStyleSheet(f"""
            QToolButton {{
                background:{C['bg_white']}; color:{C['text2']};
                border:1px solid {C['border']}; border-radius:8px;
                padding:7px 13px; font-size:12px; font-weight:700;
            }}
            QToolButton:hover {{ border-color:{C['blue']}; color:{C['blue']}; }}
        """)
        self.column_menu = QMenu(self.column_btn)
        self.column_menu.setStyleSheet(CALENDAR_MENU_SS)
        self.column_btn.setMenu(self.column_menu)
        table_head.addWidget(self.column_btn)
        cl.addLayout(table_head)

        self._columns = [
            ("item_code", "Item Code", False),
            ("name", "Product Name", False),
            ("category", "Category", False),
            ("brand", "Brand", False),
            ("size", "Size", False),
            ("color", "Color", False),
            ("list_supplier", "Supplier", False),
            ("purchase_price", "Purchase Price", False),
            ("selling_price", "Selling Price", False),
            ("margin", "Margin %", False),
            ("stock", "Available Stock", False),
            ("stock_status", "Stock Status", False),
            ("list_last_purchase_date", "Last Purchase Date", False),
            ("status", "Status", False),
            ("actions", "Actions", False),
            ("sku", "SKU", True),
            ("barcode", "Barcode", True),
            ("sub_category", "Sub Category", True),
            ("fabric_type", "Fabric", True),
            ("fit_type", "Fit", True),
            ("mrp", "MRP", True),
            ("stock", "Current Stock", True),
            ("damaged_stock", "Damaged Stock", True),
            ("returned_stock", "Returned Stock", True),
            ("stock_value", "Stock Value", True),
            ("reorder_level", "Reorder Level", True),
            ("last_sold_date", "Last Sold Date", True),
            ("list_last_invoice", "Last Invoice Number", True),
        ]

        # Table — minimal admin view plus optional hidden columns
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels([col[1] for col in self._columns])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        widths = [92, 190, 105, 100, 75, 95, 135, 105, 105, 82, 95, 105, 118, 85, 150]
        for col, width in enumerate(widths):
            self.table.setColumnWidth(col, width)
        for col, (_key, title, hidden) in enumerate(self._columns):
            action = self.column_menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(not hidden)
            action.toggled.connect(
                lambda checked, index=col: self.table.setColumnHidden(index, not checked))
            self.table.setColumnHidden(col, hidden)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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
        self._row_codes: list = []
        self._row_stocks: list = []
        self._row_records: list = []

        # ── Right-side product preview drawer ──────────────
        self.preview_drawer = QFrame()
        self.preview_drawer.setObjectName("productPreviewDrawer")
        self.preview_drawer.setMinimumWidth(350)
        self.preview_drawer.setMaximumWidth(390)
        self.preview_drawer.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.preview_drawer.setVisible(False)
        self.preview_drawer.setStyleSheet(f"""
            QFrame#productPreviewDrawer {{
                background:{C['bg_white']}; border:1px solid {C['border']};
                border-radius:14px;
            }}
            QFrame#productPreviewDrawer QLabel {{
                border:none; background:transparent;
            }}
            QScrollArea {{
                border:none; background:transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background:transparent;
            }}
            QScrollBar:vertical {{
                background:transparent; width:7px; margin:2px;
            }}
            QScrollBar::handle:vertical {{
                background:{C['border']}; border-radius:3px; min-height:24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0px;
            }}
        """)
        drawer_lay = QVBoxLayout(self.preview_drawer)
        drawer_lay.setContentsMargins(16, 14, 16, 14)
        drawer_lay.setSpacing(8)

        # Header stays visible while product details scroll.
        drawer_top = QHBoxLayout()
        drawer_title = QLabel("Product Preview")
        drawer_title.setStyleSheet(
            f"font-size:16px;font-weight:800;color:{C['text']};padding:0;")
        drawer_close = QPushButton("✕")
        drawer_close.setFixedSize(28, 28)
        drawer_close.setCursor(Qt.CursorShape.PointingHandCursor)
        drawer_close.setStyleSheet(f"""
            QPushButton {{
                border:none;border-radius:14px;background:{C['bg_panel']};
                color:{C['text2']};font-size:13px;font-weight:800;
            }}
            QPushButton:hover {{
                background:{C['danger_tint']};color:{C['accent']};
            }}
        """)
        drawer_close.clicked.connect(lambda: self.preview_drawer.hide())
        drawer_top.addWidget(drawer_title)
        drawer_top.addStretch()
        drawer_top.addWidget(drawer_close)
        drawer_lay.addLayout(drawer_top)

        drawer_rule = QFrame()
        drawer_rule.setFixedHeight(1)
        drawer_rule.setStyleSheet(
            f"background:{C['border']};border:none;")
        drawer_lay.addWidget(drawer_rule)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        preview_content = QWidget()
        preview_content.setStyleSheet("background:transparent;")
        preview_content_lay = QVBoxLayout(preview_content)
        preview_content_lay.setContentsMargins(1, 3, 5, 3)
        preview_content_lay.setSpacing(8)

        self.preview_image = QLabel("No Image")
        self.preview_image.setMinimumHeight(105)
        self.preview_image.setMaximumHeight(125)
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setStyleSheet(
            f"background:{C['bg_panel']};border:1px dashed {C['border']};"
            "border-radius:10px;color:#8e8e93;font-size:12px;")
        preview_content_lay.addWidget(self.preview_image)

        self.preview_name = QLabel("—")
        self.preview_name.setWordWrap(True)
        self.preview_name.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.preview_name.setStyleSheet(
            f"font-size:17px;font-weight:800;color:{C['text']};padding-top:2px;")
        self.preview_code = QLabel("—")
        self.preview_code.setWordWrap(True)
        self.preview_code.setStyleSheet(
            f"font-size:11px;color:{C['text3']};padding-bottom:3px;")
        preview_content_lay.addWidget(self.preview_name)
        preview_content_lay.addWidget(self.preview_code)

        detail_rule = QFrame()
        detail_rule.setFixedHeight(1)
        detail_rule.setStyleSheet(
            f"background:{C['border']};border:none;")
        preview_content_lay.addWidget(detail_rule)

        self.preview_details = QLabel("—")
        self.preview_details.setWordWrap(True)
        self.preview_details.setTextFormat(Qt.TextFormat.RichText)
        self.preview_details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview_details.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.preview_details.setStyleSheet(
            f"font-size:12px;color:{C['text2']};padding:2px 0 6px 0;")
        preview_content_lay.addWidget(self.preview_details)
        preview_content_lay.addStretch()
        self.preview_scroll.setWidget(preview_content)
        drawer_lay.addWidget(self.preview_scroll, 1)

        # Footer actions remain visible and never overlap the content.
        footer_rule = QFrame()
        footer_rule.setFixedHeight(1)
        footer_rule.setStyleSheet(
            f"background:{C['border']};border:none;")
        drawer_lay.addWidget(footer_rule)
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 1, 0, 0)
        action_row.setSpacing(8)
        self.preview_edit_btn = QPushButton("✏️  Edit")
        self.preview_stock_btn = QPushButton("📦  Update Stock")
        for button in (self.preview_edit_btn, self.preview_stock_btn):
            button.setMinimumHeight(39)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(f"""
                QPushButton {{
                    background:{C['blue']};color:white;border:none;
                    border-radius:9px;font-size:12px;font-weight:700;
                    padding:0 10px;
                }}
                QPushButton:hover {{ background:#1265C4; }}
                QPushButton:pressed {{ background:#0E55A8; }}
            """)
            action_row.addWidget(button, 1)
        drawer_lay.addLayout(action_row)
        self.preview_edit_btn.clicked.connect(self._edit_preview_product)
        self.preview_stock_btn.clicked.connect(self._stock_preview_product)
        self._preview_code = ""

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)
        body.addWidget(self.table, 1)
        body.addWidget(self.preview_drawer)
        cl.addLayout(body, 1)
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

        self._load_kpis()
        tbl = self.table
        tbl.setUpdatesEnabled(False)
        tbl.setSortingEnabled(False)
        tbl.setRowCount(0)
        self._row_codes = []
        self._row_stocks = []
        self._row_records = []

        for record in rows:
            code = record.get("item_code", "")
            name = record.get("name", "")
            stock = int(record.get("stock") or 0)
            reorder = int(record.get("reorder_level") or 0)
            purchase = float(record.get("purchase_price") or 0)
            selling = float(record.get("selling_price") or 0)
            margin = ((selling - purchase) / selling * 100) if selling else 0
            if stock <= 0:
                stock_status = "Out of Stock"
            elif reorder > 0 and stock <= reorder:
                stock_status = "Low Stock"
            else:
                stock_status = "In Stock"
            record = dict(record)
            record.update({
                "margin": margin,
                "stock_status": stock_status,
                "stock_value": stock * purchase,
            })

            r = tbl.rowCount(); tbl.insertRow(r)
            tbl.setRowHeight(r, 44)
            self._row_codes.append(code)
            self._row_stocks.append(stock)
            self._row_records.append(record)

            def _item(txt, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
                it = QTableWidgetItem(str(txt))
                it.setTextAlignment(align)
                return it

            C_CTR = Qt.AlignmentFlag.AlignCenter
            C_RGT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            for col, (key, _title, _hidden) in enumerate(self._columns):
                if key == "actions":
                    tbl.setCellWidget(r, col, self._make_action_widget(record))
                    continue
                value = record.get(key, "")
                alignment = C_CTR if key in (
                    "size", "color", "margin", "stock", "stock_status",
                    "status", "damaged_stock", "returned_stock",
                    "reorder_level") else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                if key in ("purchase_price", "selling_price", "mrp", "stock_value"):
                    numeric = float(value or 0)
                    text = f"₹{numeric:,.2f}" if numeric else "—"
                    alignment = C_RGT
                elif key == "margin":
                    text = f"{float(value or 0):.1f}%" if selling else "—"
                elif key in ("stock", "damaged_stock", "returned_stock", "reorder_level"):
                    text = str(int(value or 0))
                else:
                    text = str(value or "—")
                item = _item(text, alignment)
                if key == "margin" and selling:
                    item.setForeground(QBrush(QColor(
                        C["success"] if margin >= 0 else C["accent"])))
                elif key == "stock_status":
                    palette = {
                        "In Stock": (C["success_tint"], C["success"]),
                        "Low Stock": (C["warning_tint"], C["warning"]),
                        "Out of Stock": (C["danger_tint"], C["accent"]),
                    }[stock_status]
                    item.setBackground(QBrush(QColor(palette[0])))
                    item.setForeground(QBrush(QColor(palette[1])))
                elif key == "status":
                    palette = {
                        "Active": (C["success_tint"], C["success"]),
                        "Draft": (C["warning_tint"], C["warning"]),
                        "Inactive": (C["bg_panel"], C["text3"]),
                        "Discontinued": (C["danger_tint"], C["accent"]),
                    }.get(value, (C["bg_panel"], C["text3"]))
                    item.setBackground(QBrush(QColor(palette[0])))
                    item.setForeground(QBrush(QColor(palette[1])))
                tbl.setItem(r, col, item)

        tbl.setUpdatesEnabled(True)
        total = tbl.rowCount()
        self._chip_total.setText(f"{total} Products")
        self._chip_low.setText(
            f"{sum(1 for row in self._row_records if row['stock_status'] != 'In Stock')} Low Stock")

    def _load_kpis(self):
        values = get_product_admin_kpis(self.db_name)
        for key, label in self._kpi_labels.items():
            value = values.get(key, 0)
            if key in ("stock_value", "selling_value"):
                label.setText(f"₹{float(value):,.2f}")
            else:
                label.setText(f"{int(value):,}")

    def _make_action_widget(self, record):
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(3)
        code = record.get("item_code", "")

        def icon_button(text, tooltip, callback):
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.setFixedSize(29, 29)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(f"""
                QPushButton {{
                    background:{C['bg_panel']};border:1px solid {C['border']};
                    border-radius:7px;font-size:13px;
                }}
                QPushButton:hover {{ background:{C['accent_tint2']};border-color:{C['accent']}; }}
            """)
            button.clicked.connect(callback)
            lay.addWidget(button)

        icon_button("👁", "View Product", lambda: self._show_preview(code))
        icon_button("✏", "Edit Product", lambda: self._on_edit(code))
        icon_button("📦", "Add / Update Stock", lambda: self._open_stock(code))

        more = QToolButton()
        more.setText("⋯")
        more.setToolTip("More actions")
        more.setFixedSize(29, 29)
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.setStyleSheet(f"""
            QToolButton {{
                background:{C['bg_panel']};border:1px solid {C['border']};
                border-radius:7px;font-size:16px;font-weight:800;
            }}
            QToolButton:hover {{ background:{C['accent_tint2']};border-color:{C['accent']}; }}
        """)
        menu = QMenu(more)
        menu.setStyleSheet(CALENDAR_MENU_SS)
        menu.addAction("🧾  Invoice Log", lambda: self._show_invoice_log(code))
        menu.addAction("📋  Stock Log", lambda: self._show_stock_log(code))
        menu.addAction("🏭  Supplier Profile", lambda: self._show_supplier_profile(code))
        menu.addSeparator()
        menu.addAction("⛔  Delete / Inactive", lambda: self._confirm_delete(code))
        more.setMenu(menu)
        lay.addWidget(more)
        return wrap


    # ── Cell click dispatcher ──────────────────────────────

    def _on_cell_clicked(self, row: int, col: int):
        if row >= len(self._row_codes):
            return
        if self._columns[col][0] != "actions":
            self._show_preview(self._row_codes[row])

    def _record_for_code(self, code):
        return next(
            (record for record in self._row_records
             if record.get("item_code") == code),
            get_product_full(self.db_name, code) or {},
        )

    def _show_preview(self, code):
        record = self._record_for_code(code)
        if not record:
            return
        self._preview_code = code
        self.preview_name.setText(record.get("name") or "Unnamed Product")
        self.preview_code.setText(
            f"{code}  ·  {record.get('sku') or 'No SKU'}")
        stock = int(record.get("stock") or 0)
        purchase = float(record.get("purchase_price") or 0)
        selling = float(record.get("selling_price") or 0)
        margin = ((selling - purchase) / selling * 100) if selling else 0
        supplier = record.get("list_supplier") or record.get("supplier_name") or "—"
        details = [
            ("Category", record.get("category") or "—"),
            ("Sub Category", record.get("sub_category") or "—"),
            ("Brand", record.get("brand") or "—"),
            ("Size", record.get("size") or "—"),
            ("Color", record.get("color") or "—"),
            ("Supplier", supplier),
            ("Purchase Price", f"₹{purchase:,.2f}"),
            ("Selling Price", f"₹{selling:,.2f}"),
            ("Margin", f"{margin:.1f}%"),
            ("Available Stock", f"{stock:,}"),
            ("Last Purchase", record.get("list_last_purchase_date") or "—"),
            ("Last Invoice", record.get("list_last_invoice") or "—"),
        ]
        rows = "".join(
            "<tr>"
            f"<td style='color:#86868b;padding:4px 12px 4px 0;'>{escape(label)}</td>"
            f"<td style='color:#1d1d1f;padding:4px 0;'><b>{escape(str(value))}</b></td>"
            "</tr>"
            for label, value in details
        )
        self.preview_details.setText(
            f"<table width='100%' cellspacing='0' cellpadding='0'>{rows}</table>")
        image = record.get("image")
        self.preview_image.clear()
        if image:
            pixmap = QPixmap()
            pixmap.loadFromData(image)
            if not pixmap.isNull():
                self.preview_image.setPixmap(
                    pixmap.scaled(
                        315, 118, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation))
            else:
                self.preview_image.setText("No Image")
        else:
            self.preview_image.setText("No Image")
        self.preview_drawer.show()
        QTimer.singleShot(
            0, lambda: self.preview_scroll.verticalScrollBar().setValue(0))

    def _edit_preview_product(self):
        if self._preview_code:
            self._on_edit(self._preview_code)

    def _stock_preview_product(self):
        if self._preview_code:
            self._open_stock(self._preview_code)

    def _open_stock(self, code):
        product = get_product_full(self.db_name, code) or {}
        if not product:
            return
        dlg = PurchaseStockDialog(
            self.db_name, code, product.get("name") or code,
            int(product.get("stock") or 0), self.current_user, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_table()
            self._show_preview(code)

    def _log_dialog(self, title, columns, rows):
        dialog = QDialog(self)
        apply_app_icon(dialog)
        dialog.setWindowTitle(title)
        dialog.resize(1050, 480)
        layout = QVBoxLayout(dialog)
        heading = QLabel(title)
        heading.setStyleSheet(
            f"font-size:18px;font-weight:800;color:{C['text']};padding:4px;")
        layout.addWidget(heading)
        table = mini_table(columns, 380)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for values in rows:
            row = table.rowCount()
            table.insertRow(row)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value if value not in (None, "") else "—"))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, col, item)
        layout.addWidget(table)
        close = QPushButton("Close")
        close.setFixedHeight(38)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _show_invoice_log(self, code):
        records = get_purchase_invoice_logs(self.db_name, code)
        rows = [[
            record.get("invoice_number"), record.get("purchase_date"),
            record.get("supplier_name"), record.get("quantity"),
            f"₹{float(record.get('purchase_price') or 0):,.2f}",
            f"₹{float(record.get('net_amount') or 0):,.2f}",
            record.get("payment_status"), record.get("stock_after"),
        ] for record in records]
        self._log_dialog(
            f"Invoice Log — {code}",
            ["Invoice", "Purchase Date", "Supplier", "Qty", "Purchase Price",
             "Net Amount", "Payment", "Stock After"],
            rows,
        )

    def _show_stock_log(self, code):
        records = get_stock_update_logs(self.db_name, code)
        rows = [[
            record.get("created_at"), record.get("action_type"),
            record.get("reference_number"), record.get("qty_in"),
            record.get("qty_out"), record.get("old_stock"),
            record.get("new_stock"), record.get("updated_by"),
            " · ".join(filter(None, [record.get("reason"), record.get("notes")])),
        ] for record in records]
        self._log_dialog(
            f"Stock Log — {code}",
            ["Date", "Action", "Reference", "Qty In", "Qty Out",
             "Old Stock", "New Stock", "Updated By", "Notes"],
            rows,
        )

    def _show_supplier_profile(self, code):
        suppliers = get_product_suppliers(self.db_name, code)
        if not suppliers:
            QMessageBox.information(
                self, "Supplier Profile",
                "No supplier is linked to this product yet.")
            return
        rows = [[
            supplier.get("code") or supplier.get("supplier_code"),
            supplier.get("name"), supplier.get("contact_person"),
            supplier.get("phone") or supplier.get("mobile_number"),
            supplier.get("email"), supplier.get("city"),
            supplier.get("payment_terms"),
            f"₹{float(supplier.get('unit_price') or 0):,.2f}",
            "Primary" if supplier.get("is_primary") else "Linked",
        ] for supplier in suppliers]
        self._log_dialog(
            f"Supplier Profile — {code}",
            ["Code", "Supplier", "Contact", "Phone", "Email", "City",
             "Payment Terms", "Last Price", "Link"],
            rows,
        )

    def _confirm_delete(self, item_code):
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete / Inactive Product")
        msg.setText(
            f"Choose how to remove <b>{item_code}</b> from daily selling.")
        inactive_btn = msg.addButton(
            "Set Inactive", QMessageBox.ButtonRole.ActionRole)
        delete_btn = msg.addButton(
            "Soft Delete", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() == inactive_btn:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    "UPDATE products SET status='Inactive',updated_at=?,updated_by=? "
                    "WHERE item_code=?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     self.current_user, item_code),
                )
            self._load_table()
        elif msg.clickedButton() == delete_btn:
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
        apply_app_icon(self)
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




