"""
supplier_page.py  —  Evo Aura  •  Supplier Management
======================================================
Apple-theme, PyQt6, SQLite
Mirrors product_page.py layout exactly:
  SupplierPage
    ├── SupplierListWidget  (list + search + top bar)
    └── _SlidePanel         (overlay)
          └── SupplierFormWidget   (Add/Edit tabs)
          └── SupplierDetailWidget (Click → inventory view)
"""

import sqlite3, datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QGridLayout, QTabWidget, QSizePolicy, QComboBox,
    QAbstractItemView, QApplication, QSpinBox, QDoubleSpinBox,
    QStackedWidget, QMessageBox, QDateEdit, QTextEdit,
)
from PyQt6.QtCore  import Qt, QTimer, QDate, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui   import QFont, QColor
from input_behavior import ensure_global_input_guard

# ── mirror product_page color tokens ───────────────────────────────────────────
try:
    from product_page import C, _F, FIELD_SS, LABEL_SS, SEC_HDR_SS, _NO_ARROW, ToggleSwitch
    from product_page import _apply_combo_delegate
    from product_page import init_product_table
except ImportError:
    # Fallback standalone tokens
    class _C(dict):
        def __missing__(self, k): return "#888888"
    C = _C(
        bg_light="#F5F5F7", bg_white="#FFFFFF", bg_panel="#F2F2F7",
        bg="#F5F5F7", border="#D2D2D7", text="#1D1D1F", text2="#6E6E73",
        text3="#A1A1A6", accent="#FA2D48", accent_dark="#C81F36",
        blue="#1A73E8", blue_tint="#EEF5FF", success="#27AE60",
        warning="#E67E22", hover_bg="#E5E5EA", section_hdr="#1D1D1F",
    )
    def _F(size=13, bold=False):
        f = QFont(); f.setPointSize(size)
        if bold: f.setBold(True)
        return f
    FIELD_SS  = ""
    LABEL_SS  = f"font-size:12px;color:#6E6E73;background:transparent;border:none;"
    SEC_HDR_SS= f"font-size:14px;font-weight:700;color:#1D1D1F;background:transparent;border:none;"
    _NO_ARROW = ""
    ToggleSwitch = None
    def _apply_combo_delegate(cb): pass
    def init_product_table(db, user): pass

# ─────────────────────────────────────────────────────────────────────────────
#  DB HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _q(db, sql, params=()):
    try:
        with sqlite3.connect(db) as conn:
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as e:
        print("DB:", e); return []

def _qone(db, sql, params=()):
    r = _q(db, sql, params); return r[0] if r else {}

def _run(db, sql, params=()):
    try:
        with sqlite3.connect(db) as conn:
            conn.execute(sql, params); conn.commit(); return True
    except Exception as e:
        print("DB write:", e); return False

def init_supplier_tables(db):
    """Ensure all supplier-related tables exist."""
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS suppliers (
            code             TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            gstin            TEXT DEFAULT '',
            contact_person   TEXT DEFAULT '',
            phone            TEXT DEFAULT '',
            email            TEXT DEFAULT '',
            address          TEXT DEFAULT '',
            city             TEXT DEFAULT '',
            state            TEXT DEFAULT '',
            pincode          TEXT DEFAULT '',
            payment_terms_days INTEGER DEFAULT 30,
            credit_limit     REAL DEFAULT 0,
            current_balance  REAL DEFAULT 0,
            status           TEXT DEFAULT 'Active',
            notes            TEXT DEFAULT '',
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by       TEXT DEFAULT 'system'
        );

        CREATE TABLE IF NOT EXISTS product_suppliers (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code         TEXT NOT NULL,
            supplier_code        TEXT NOT NULL,
            supplier_product_code TEXT DEFAULT '',
            unit_price           REAL DEFAULT 0,
            moq                  INTEGER DEFAULT 1,
            pack_size            INTEGER DEFAULT 1,
            lead_time_days       INTEGER DEFAULT 0,
            is_primary           INTEGER DEFAULT 0,
            last_ordered_date    TEXT DEFAULT '',
            UNIQUE(product_code, supplier_code),
            FOREIGN KEY(supplier_code) REFERENCES suppliers(code)
        );

        CREATE TABLE IF NOT EXISTS batches (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code     TEXT NOT NULL,
            supplier_code    TEXT DEFAULT '',
            batch_no         TEXT NOT NULL,
            qty              INTEGER DEFAULT 0,
            sold_qty         INTEGER DEFAULT 0,
            manufacture_date TEXT DEFAULT '',
            expiry_date      TEXT DEFAULT '',
            purchase_price   REAL DEFAULT 0,
            mrp              REAL DEFAULT 0,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by       TEXT DEFAULT 'system'
        );
        """)
        # Migration: add missing columns
        for col, defn in [
            ("city","TEXT DEFAULT ''"), ("state","TEXT DEFAULT ''"),
            ("pincode","TEXT DEFAULT ''"), ("contact_person","TEXT DEFAULT ''"),
            ("credit_limit","REAL DEFAULT 0"), ("notes","TEXT DEFAULT ''"),
            ("payment_terms_days","INTEGER DEFAULT 30"),
            ("current_balance","REAL DEFAULT 0"),
            ("status","TEXT DEFAULT 'Active'"),
            ("created_by","TEXT DEFAULT 'system'"),
        ]:
            try: conn.execute(f"ALTER TABLE suppliers ADD COLUMN {col} {defn}")
            except: pass
        for col, defn in [
            ("sold_qty","INTEGER DEFAULT 0"), ("mrp","REAL DEFAULT 0"),
            ("supplier_code","TEXT DEFAULT ''"),
            ("batch_no","TEXT DEFAULT ''"),
            ("manufacture_date","TEXT DEFAULT ''"),
            ("created_at","TEXT DEFAULT ''"),
        ]:
            try: conn.execute(f"ALTER TABLE batches ADD COLUMN {col} {defn}")
            except: pass
        try:
            conn.execute(
                "UPDATE batches SET batch_no=batch_number "
                "WHERE (batch_no IS NULL OR batch_no='') AND batch_number IS NOT NULL"
            )
        except Exception:
            pass
        try:
            conn.execute(
                "UPDATE batches SET manufacture_date=mfg_date "
                "WHERE (manufacture_date IS NULL OR manufacture_date='') AND mfg_date IS NOT NULL"
            )
        except Exception:
            pass
        try:
            conn.execute(
                "UPDATE batches SET created_at=received_date "
                "WHERE (created_at IS NULL OR created_at='') AND received_date IS NOT NULL"
            )
        except Exception:
            pass

def get_suppliers(db, search=""):
    like = f"%{search}%"
    return _q(db, """
        SELECT s.*,
               COUNT(DISTINCT COALESCE(ps.product_code, p.item_code)) AS total_products,
               COALESCE(SUM(b.qty - COALESCE(b.sold_qty,0)),0)  AS total_stock,
               COALESCE(SUM(b.qty * b.purchase_price),0)         AS stock_value,
               MAX(ps.last_ordered_date)               AS last_order
        FROM suppliers s
        LEFT JOIN product_suppliers ps ON ps.supplier_code = s.code
        LEFT JOIN products p ON lower(p.supplier_name) = lower(s.name)
                            AND NOT EXISTS (
                                SELECT 1 FROM product_suppliers ps2
                                WHERE ps2.product_code = p.item_code
                            )
        LEFT JOIN batches b ON b.supplier_code = s.code
        WHERE s.name LIKE ? OR s.code LIKE ? OR s.phone LIKE ?
              OR s.gstin LIKE ? OR s.city LIKE ?
        GROUP BY s.code
        ORDER BY s.name
    """, (like,)*5)

def save_supplier(db, data: dict, user="system"):
    init_supplier_tables(db)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    import time
    code = data.get("code") or ("SUP" + str(int(time.time()))[-7:])
    try:
        with sqlite3.connect(db) as conn:
            values = (
                data.get("name",""), data.get("gstin",""),
                data.get("contact_person",""), data.get("phone",""),
                data.get("email",""), data.get("address",""),
                data.get("city",""), data.get("state",""),
                data.get("pincode",""),
                int(data.get("payment_terms_days",30) or 30),
                float(data.get("credit_limit",0) or 0),
                data.get("status","Active"), data.get("notes",""),
            )
            exists = conn.execute(
                "SELECT 1 FROM suppliers WHERE code=? LIMIT 1", (code,)
            ).fetchone()
            if exists:
                conn.execute("""
                    UPDATE suppliers SET
                        name=?, gstin=?, contact_person=?, phone=?, email=?,
                        address=?, city=?, state=?, pincode=?,
                        payment_terms_days=?, credit_limit=?, status=?, notes=?
                    WHERE code=?
                """, values + (code,))
            else:
                conn.execute("""
                    INSERT INTO suppliers(code,name,gstin,contact_person,phone,email,
                        address,city,state,pincode,payment_terms_days,credit_limit,
                        status,notes,created_at,created_by)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (code,) + values + (now, user))
            conn.commit()
        return code
    except Exception as e:
        print("save_supplier:", e); return None

def get_supplier_inventory(db, sup_code):
    """All products + their batches for this supplier."""
    sup = _qone(db, "SELECT name FROM suppliers WHERE code=?", (sup_code,))
    sup_name = sup.get("name", "")
    products = _q(db, """
        SELECT ps.product_code, p.name AS product_name,
               ps.supplier_product_code AS sup_sku,
               ps.unit_price, ps.moq, ps.lead_time_days, ps.is_primary,
               ps.last_ordered_date,
               COALESCE(SUM(b.qty - COALESCE(b.sold_qty,0)), 0) AS available_stock,
               COALESCE(SUM(b.qty), 0)                           AS total_received,
               COALESCE(SUM(b.sold_qty), 0)                      AS total_sold
        FROM product_suppliers ps
        JOIN products p ON p.item_code = ps.product_code
        LEFT JOIN batches b ON b.product_code = ps.product_code
                           AND b.supplier_code = ?
        WHERE ps.supplier_code = ?
        GROUP BY ps.product_code
        ORDER BY p.name
    """, (sup_code, sup_code))

    for prod in products:
        prod["batches"] = _q(db, """
            SELECT batch_no, qty, COALESCE(sold_qty,0) AS sold_qty,
                   (qty - COALESCE(sold_qty,0)) AS available,
                   manufacture_date, expiry_date,
                   purchase_price, mrp, created_at
            FROM batches
            WHERE product_code=? AND supplier_code=?
            ORDER BY expiry_date ASC, created_at DESC
        """, (prod["product_code"], sup_code))

    linked_codes = {p.get("product_code") for p in products}
    if sup_name:
        legacy_products = _q(db, """
            SELECT p.item_code AS product_code, p.name AS product_name,
                   p.supplier_code AS sup_sku,
                   p.last_purchase_price AS unit_price,
                   1 AS moq,
                   p.lead_time_days AS lead_time_days,
                   0 AS is_primary,
                   '' AS last_ordered_date,
                   p.stock AS available_stock,
                   p.opening_stock AS total_received,
                   0 AS total_sold
            FROM products p
            WHERE lower(p.supplier_name) = lower(?)
            ORDER BY p.name
        """, (sup_name,))
        for prod in legacy_products:
            if prod.get("product_code") in linked_codes:
                continue
            prod["batches"] = []
            products.append(prod)
    return products

# ─────────────────────────────────────────────────────────────────────────────
#  SHARED STYLE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
_BTN_PRIMARY = f"""
    QPushButton {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {C['accent']}, stop:1 {C['accent_dark']});
        color: white; border: none; border-radius: 10px;
        font-size: 13px; font-weight: 700; padding: 0 18px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {C['accent_dark']}, stop:1 {C['accent']});
    }}
"""

_TABLE_SS = f"""
QTableWidget {{
    background: {C['bg_white']}; border: none;
    gridline-color: {C['border']}; font-size: 13px; color: {C['text']};
    selection-background-color: {C['blue_tint']};
    selection-color: {C['text']}; outline: none;
}}
QTableWidget::item {{ padding: 10px 12px; border-bottom: 1px solid {C['border']}; }}
QTableWidget::item:selected {{ background: {C['blue_tint']}; }}
QTableWidget::item:hover {{ background: {C['hover_bg']}; }}
QHeaderView::section {{
    background: {C['bg_panel']}; color: {C['text2']};
    font-size: 11px; font-weight: 700; padding: 8px 12px;
    border: none; border-bottom: 1.5px solid {C['border']};
    text-transform: uppercase; letter-spacing: 0.5px;
}}
"""

def _sep_line():
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background:{C['border']};border:none;max-height:1px;")
    return f

def _card_frame():
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{C['bg_white']};border:1px solid {C['border']};"
        f"border-radius:12px;}}")
    return f

def _section_lbl(text, icon=""):
    l = QLabel(f"{icon}  {text}" if icon else text)
    l.setStyleSheet(SEC_HDR_SS); return l

def _field_lbl(text):
    l = QLabel(text); l.setStyleSheet(LABEL_SS); return l

def _expiry_color(expiry_str):
    """Return color based on expiry proximity."""
    if not expiry_str or expiry_str == "—": return C['text2']
    try:
        exp = datetime.datetime.strptime(expiry_str[:10], "%Y-%m-%d").date()
        today = datetime.date.today()
        days = (exp - today).days
        if days < 0:   return "#dc2626"   # expired
        if days < 30:  return "#d97706"   # expiring soon
        if days < 90:  return "#ca8a04"   # within 3 months
        return C['success']
    except: return C['text2']

# ─────────────────────────────────────────────────────────────────────────────
#  SLIDE PANEL  (same as product_page._SlidePanel)
# ─────────────────────────────────────────────────────────────────────────────
class _SlidePanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setVisible(False)
        self._open = False
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _clear_anim_finished(self):
        try:
            self._anim.finished.disconnect()
        except TypeError:
            pass

    def resize_to_parent(self):
        p = self.parent()
        if p: self.setGeometry(0, 0, p.width(), p.height())

    def slide_in(self):
        self._clear_anim_finished()
        self._open = True
        self.resize_to_parent(); self.setVisible(True); self.raise_()
        p = self.parent(); W = p.width() if p else 1200; H = p.height() if p else 800
        self._anim.setStartValue(QRect(W, 0, W, H))
        self._anim.setEndValue(QRect(0, 0, W, H))
        self._anim.start()

    def slide_out(self):
        if not self._open and not self.isVisible():
            return
        self._clear_anim_finished()
        self._open = False
        p = self.parent(); W = p.width() if p else 1200; H = p.height() if p else 800
        self._anim.setStartValue(QRect(0, 0, W, H))
        self._anim.setEndValue(QRect(W, 0, W, H))
        self._anim.finished.connect(lambda: self.setVisible(False))
        self._anim.start()

# ─────────────────────────────────────────────────────────────────────────────
#  SUPPLIER DETAIL VIEW  (inventory breakdown when clicking a supplier)
# ─────────────────────────────────────────────────────────────────────────────
class SupplierDetailWidget(QWidget):
    """Shows supplier info + product inventory with batches & expiry."""
    back = pyqtSignal()

    def __init__(self, db_name, parent=None):
        super().__init__(parent)
        self.db_name = db_name
        self.setStyleSheet(f"background:{C['bg_light']};")

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────
        top = QFrame(); top.setFixedHeight(56)
        top.setStyleSheet("background:#f5f5f7;border-bottom:1px solid #d2d2d7;")
        tl = QHBoxLayout(top); tl.setContentsMargins(24,0,24,0); tl.setSpacing(12)

        back_btn = QPushButton("← Back")
        back_btn.setFixedSize(80, 30)
        back_btn.setStyleSheet("""
            QPushButton { background:rgba(0,0,0,0.06); color:#1d1d1f;
                border:1px solid rgba(0,0,0,0.12); border-radius:15px;
                font-size:13px; font-weight:500; }
            QPushButton:hover { background:rgba(0,0,0,0.10); }
        """)
        back_btn.clicked.connect(self.back)
        tl.addWidget(back_btn)

        self._top_title = QLabel("Supplier")
        self._top_title.setFont(_F(15, bold=True))
        self._top_title.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
        tl.addWidget(self._top_title); tl.addStretch()
        root.addWidget(top)

        # ── Scroll body ──────────────────────────────────────
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background:{C['bg_light']};")
        self._body = QWidget(); self._body.setStyleSheet(f"background:{C['bg_light']};")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(24,20,24,24); self._body_lay.setSpacing(16)
        scroll.setWidget(self._body)
        root.addWidget(scroll, 1)

    def load(self, sup_code, sup_name):
        self._top_title.setText(sup_name)
        # Clear
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        sup = _qone(self.db_name,
                    "SELECT * FROM suppliers WHERE code=?", (sup_code,))
        prods = get_supplier_inventory(self.db_name, sup_code)

        # ── Supplier info card ────────────────────────────────
        info_card = _card_frame()
        info_lay = QVBoxLayout(info_card)
        info_lay.setContentsMargins(20,16,20,16); info_lay.setSpacing(12)

        # Header row
        hdr = QHBoxLayout(); hdr.setSpacing(12)
        icon = QLabel("🏭")
        icon.setStyleSheet("font-size:28px;background:transparent;border:none;")
        name_col = QVBoxLayout(); name_col.setSpacing(2)
        n = QLabel(sup.get("name","—")); n.setFont(_F(16, bold=True))
        n.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
        c = QLabel(f"Code: {sup_code}  ·  {sup.get('gstin','') or 'No GSTIN'}")
        c.setStyleSheet(f"font-size:12px;color:{C['text3']};background:transparent;border:none;")
        name_col.addWidget(n); name_col.addWidget(c)
        hdr.addWidget(icon); hdr.addLayout(name_col); hdr.addStretch()

        status = sup.get("status","Active")
        st_lbl = QLabel(f"  {status}  ")
        bg = "#f0fdf4" if status=="Active" else "#fef2f2"
        fg = "#16a34a" if status=="Active" else "#dc2626"
        st_lbl.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:6px;"
            f"font-size:12px;font-weight:700;padding:4px 0;")
        hdr.addWidget(st_lbl)
        info_lay.addLayout(hdr)
        info_lay.addWidget(_sep_line())

        # Details grid
        dg = QGridLayout(); dg.setSpacing(0)
        dg.setColumnMinimumWidth(0, 140); dg.setColumnMinimumWidth(2, 140)
        ROW_SS = f"font-size:13px;color:{C['text']};background:transparent;border:none;padding:8px 0;border-bottom:1px solid {C['border']};"
        LBL_SS2 = f"font-size:12px;color:{C['text3']};background:transparent;border:none;padding:8px 0;border-bottom:1px solid {C['border']};"

        fields = [
            ("Contact", sup.get("contact_person","—") or "—"),
            ("Phone",   sup.get("phone","—") or "—"),
            ("Email",   sup.get("email","—") or "—"),
            ("Address", f"{sup.get('address','')} {sup.get('city','')} {sup.get('state','')} {sup.get('pincode','')}".strip() or "—"),
            ("Payment Terms", f"{sup.get('payment_terms_days',30) or 30} days"),
            ("Credit Limit",  f"₹{(sup.get('credit_limit') or 0):,.0f}"),
        ]
        for i, (k, v) in enumerate(fields):
            r, c_off = divmod(i, 2)
            kl = QLabel(k); kl.setStyleSheet(LBL_SS2)
            vl = QLabel(str(v)); vl.setStyleSheet(ROW_SS); vl.setWordWrap(True)
            dg.addWidget(kl, r, c_off*2)
            dg.addWidget(vl, r, c_off*2+1)
        info_lay.addLayout(dg)

        # Stat pills
        total_stock = sum(p.get("available_stock",0) or 0 for p in prods)
        total_val   = sum((p.get("available_stock",0) or 0) * (p.get("unit_price",0) or 0) for p in prods)
        pills_row   = QHBoxLayout(); pills_row.setSpacing(10)

        def _pill(icon_t, label, val, color):
            pf = QFrame()
            pf.setStyleSheet(
                f"QFrame{{background:{C['bg_panel']};border:1px solid {C['border']};"
                f"border-radius:8px;}}")
            pl = QVBoxLayout(pf); pl.setContentsMargins(12,8,12,8); pl.setSpacing(2)
            vl2 = QLabel(str(val)); vl2.setFont(_F(16,bold=True))
            vl2.setStyleSheet(f"color:{color};background:transparent;border:none;")
            ll2 = QLabel(f"{icon_t} {label}")
            ll2.setStyleSheet(f"font-size:10px;color:{C['text3']};background:transparent;border:none;")
            pl.addWidget(vl2); pl.addWidget(ll2)
            return pf

        pills_row.addWidget(_pill("📦","Products", len(prods), C['blue']))
        pills_row.addWidget(_pill("🗃️","Total Stock", total_stock, C['success']))
        pills_row.addWidget(_pill("💰","Stock Value", f"₹{total_val:,.0f}", C['warning']))
        info_lay.addLayout(pills_row)
        self._body_lay.addWidget(info_card)

        # ── Inventory section ─────────────────────────────────
        if not prods:
            empty = QLabel("No products linked to this supplier yet.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"font-size:14px;color:{C['text3']};background:transparent;border:none;padding:40px;")
            self._body_lay.addWidget(empty)
            return

        inv_title = _section_lbl("Linked Products", "📊")
        self._body_lay.addWidget(inv_title)

        table_card = _card_frame()
        tc_lay = QVBoxLayout(table_card)
        tc_lay.setContentsMargins(16, 14, 16, 16)
        tc_lay.setSpacing(10)

        table = QTableWidget(len(prods), 11)
        table.setHorizontalHeaderLabels([
            "Product Code", "Product", "Primary", "Supplier SKU",
            "Available", "Received", "Sold", "Last Price",
            "MOQ", "Lead", "Last Order"
        ])
        table.setStyleSheet(_TABLE_SS)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for r, prod in enumerate(prods):
            table.setRowHeight(r, 42)
            avail = prod.get("available_stock", 0) or 0
            values = [
                prod.get("product_code", "") or "",
                prod.get("product_name", "") or "",
                "Yes" if prod.get("is_primary") else "",
                prod.get("sup_sku", "") or "",
                str(avail),
                str(prod.get("total_received", 0) or 0),
                str(prod.get("total_sold", 0) or 0),
                f"₹{(prod.get('unit_price') or 0):,.2f}",
                str(prod.get("moq", 1) or 1),
                f"{prod.get('lead_time_days') or 0}d",
                (prod.get("last_ordered_date", "") or "")[:10] or "—",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if c in (4, 5, 6, 8):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 2 and value:
                    item.setForeground(QColor(C["success"]))
                if c == 4:
                    item.setForeground(QColor(C["success"] if avail > 0 else C["accent"]))
                if c == 7:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r, c, item)

        table.setFixedHeight(min(44 * len(prods) + 46, 420))
        tc_lay.addWidget(table)
        self._body_lay.addWidget(table_card)
        self._body_lay.addStretch()
        return

        for prod in prods:
            pcard = _card_frame()
            pl = QVBoxLayout(pcard); pl.setContentsMargins(16,14,16,14); pl.setSpacing(10)

            # Product header
            ph = QHBoxLayout(); ph.setSpacing(10)
            pn = QLabel(prod.get("product_name","—")); pn.setFont(_F(13,bold=True))
            pn.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
            ph.addWidget(pn)
            if prod.get("is_primary"):
                pb = QLabel("  ★ Primary  ")
                pb.setStyleSheet("background:#f0fdf4;color:#16a34a;border-radius:5px;"
                                 "font-size:11px;font-weight:700;padding:2px 0;")
                ph.addWidget(pb)
            ph.addStretch()
            pc = QLabel(prod.get("product_code",""))
            pc.setStyleSheet(f"font-size:11px;color:{C['text3']};background:transparent;border:none;")
            ph.addWidget(pc)
            pl.addLayout(ph)

            # Stock summary row
            sr = QHBoxLayout(); sr.setSpacing(20)
            def _sm(lbl, val, color=None):
                sw2 = QVBoxLayout(); sw2.setSpacing(1)
                sv2 = QLabel(str(val)); sv2.setFont(_F(15,bold=True))
                sv2.setStyleSheet(f"color:{color or C['text']};background:transparent;border:none;")
                sl2 = QLabel(lbl); sl2.setStyleSheet(f"font-size:10px;color:{C['text3']};background:transparent;border:none;")
                sw2.addWidget(sv2); sw2.addWidget(sl2)
                w2 = QWidget(); w2.setLayout(sw2); return w2

            avail = prod.get("available_stock",0) or 0
            total_r = prod.get("total_received",0) or 0
            total_s = prod.get("total_sold",0) or 0
            color_a = C['success'] if avail > 0 else C['accent']

            sr.addWidget(_sm("Available", avail, color_a))
            sr.addWidget(_sm("Total Received", total_r, C['blue']))
            sr.addWidget(_sm("Sold", total_s, C['text2']))
            sr.addWidget(_sm("Last Price", f"₹{(prod.get('unit_price') or 0):.2f}"))
            sr.addWidget(_sm("Lead Time", f"{prod.get('lead_time_days') or 0}d"))
            if prod.get("sup_sku"):
                sr.addWidget(_sm("Sup SKU", prod["sup_sku"]))
            sr.addStretch()
            pl.addLayout(sr)

            # Batch table
            batches = prod.get("batches",[])
            if batches:
                pl.addWidget(_sep_line())
                bl = QLabel(f"Batches ({len(batches)})")
                bl.setStyleSheet(f"font-size:11px;font-weight:700;color:{C['text2']};background:transparent;border:none;")
                pl.addWidget(bl)

                bt = QTableWidget(len(batches), 7)
                bt.setHorizontalHeaderLabels(
                    ["Batch No","Qty","Sold","Available","Mfg Date","Expiry","Price"])
                bt.setStyleSheet(_TABLE_SS)
                bt.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                bt.verticalHeader().setVisible(False)
                bt.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
                bt.horizontalHeader().setStretchLastSection(True)
                bt.setFixedHeight(min(44*len(batches)+44, 220))
                bt.setShowGrid(True)
                bt.setFocusPolicy(Qt.FocusPolicy.NoFocus)

                today = datetime.date.today()
                for ri, b in enumerate(batches):
                    bt.setRowHeight(ri, 44)
                    exp_str = (b.get("expiry_date","") or "")[:10]
                    exp_color = _expiry_color(exp_str)

                    vals = [
                        b.get("batch_no","—"),
                        str(b.get("qty",0)),
                        str(b.get("sold_qty",0)),
                        str(b.get("available",0)),
                        (b.get("manufacture_date","")[:10] or "—"),
                        exp_str or "—",
                        f"₹{(b.get('purchase_price') or 0):.2f}",
                    ]
                    for ci, val in enumerate(vals):
                        item = QTableWidgetItem(val)
                        color = exp_color if ci == 5 else C['text']
                        item.setForeground(QColor(color))
                        if ci == 5 and exp_str:
                            try:
                                exp = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
                                days_left = (exp - today).days
                                if days_left < 0:
                                    item.setBackground(QColor("#fef2f2"))
                                    item.setText(f"⚠ {exp_str} (Expired)")
                                elif days_left < 30:
                                    item.setBackground(QColor("#fffbeb"))
                                    item.setText(f"⚡ {exp_str} ({days_left}d)")
                            except: pass
                        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                        bt.setItem(ri, ci, item)
                pl.addWidget(bt)
            else:
                no_batch = QLabel("No batch records yet.")
                no_batch.setStyleSheet(f"font-size:12px;color:{C['text3']};background:transparent;border:none;")
                pl.addWidget(no_batch)

            self._body_lay.addWidget(pcard)

        self._body_lay.addStretch()


# ─────────────────────────────────────────────────────────────────────────────
#  SUPPLIER FORM  (Add / Edit)
# ─────────────────────────────────────────────────────────────────────────────
class SupplierFormWidget(QWidget):
    saved  = pyqtSignal(str)   # emits supplier code
    cancel = pyqtSignal()

    def __init__(self, db_name, current_user="Admin", parent=None):
        super().__init__(parent)
        ensure_global_input_guard()
        self.db_name      = db_name
        self.current_user = current_user
        self._edit_code   = None
        self.setStyleSheet(f"background:{C['bg_light']};" + FIELD_SS)

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────
        top = QFrame(); top.setFixedHeight(56)
        top.setStyleSheet("background:#f5f5f7;border-bottom:1px solid #d2d2d7;")
        tl = QHBoxLayout(top); tl.setContentsMargins(24,0,24,0); tl.setSpacing(12)
        self._form_title = QLabel("Add Supplier")
        self._form_title.setFont(_F(15,bold=True))
        self._form_title.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
        tl.addWidget(self._form_title); tl.addStretch()

        cancel_btn = QPushButton("Cancel"); cancel_btn.setFixedHeight(32)
        cancel_btn.setStyleSheet(
            f"QPushButton{{background:rgba(0,0,0,0.06);color:{C['text']};"
            f"border:1px solid rgba(0,0,0,0.12);border-radius:10px;"
            f"font-size:13px;font-weight:500;padding:0 16px;}}"
            f"QPushButton:hover{{background:rgba(0,0,0,0.10);}}")
        cancel_btn.clicked.connect(self.cancel)

        save_btn = QPushButton("Save Supplier"); save_btn.setFixedHeight(34)
        save_btn.setStyleSheet(_BTN_PRIMARY)
        save_btn.clicked.connect(self._save)

        tl.addWidget(cancel_btn); tl.addSpacing(8); tl.addWidget(save_btn)
        root.addWidget(top)

        # ── Scroll ───────────────────────────────────────────
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background:{C['bg_light']};")
        body = QWidget(); body.setStyleSheet(f"background:{C['bg_light']};")
        bl = QVBoxLayout(body); bl.setContentsMargins(24,20,24,24); bl.setSpacing(16)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        def _sec(title, icon):
            sec = QFrame()
            sec.setStyleSheet(
                f"QFrame{{background:{C['bg_white']};border:1px solid {C['border']};"
                f"border-radius:12px;}}")
            sl = QVBoxLayout(sec); sl.setContentsMargins(20,16,20,16); sl.setSpacing(12)
            hd = QLabel(f"{icon}  {title}"); hd.setStyleSheet(SEC_HDR_SS)
            sl.addWidget(hd); sl.addWidget(_sep_line())
            g = QGridLayout(); g.setHorizontalSpacing(12); g.setVerticalSpacing(10)
            g.setColumnMinimumWidth(0, 124)
            g.setColumnMinimumWidth(2, 124)
            g.setColumnStretch(1,1); g.setColumnStretch(3,1)
            sl.addLayout(g)
            return sec, g

        def _normalize_field(widget):
            widget.setFixedHeight(38)
            widget.setMinimumWidth(260)
            widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            existing = widget.styleSheet()
            if isinstance(widget, (QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
                widget.setStyleSheet(FIELD_SS + existing)

        def _add(g, r, c, label, widget, span=1, hint="", req=False):
            _normalize_field(widget)
            lbl_text = f"{label} {'*' if req else ''}"
            lbl = QLabel(lbl_text); lbl.setStyleSheet(LABEL_SS)
            lbl.setMinimumWidth(118)
            g.addWidget(lbl, r, c*2)
            if hint:
                wrap = QWidget()
                wrap.setStyleSheet("background:transparent;border:none;")
                wl = QVBoxLayout(wrap); wl.setContentsMargins(0,0,0,0); wl.setSpacing(2)
                wl.addWidget(widget)
                hl = QLabel(hint)
                hl.setStyleSheet(
                    f"font-size:10px;color:{C['text3']};"
                    f"background:transparent;border:none;padding:0;margin:0;"
                )
                wl.addWidget(hl)
                g.addWidget(wrap, r, c*2+1, 1, span*2-1)
            else:
                g.addWidget(widget, r, c*2+1, 1, span*2-1)

        def _le(ph=""): e = QLineEdit(); e.setPlaceholderText(ph); e.setFixedHeight(38); return e
        def _sp(suf="",max_v=999999):
            s = QDoubleSpinBox() if "." in suf or "₹" in suf else QSpinBox()
            s.setRange(0,max_v); s.setSuffix(suf); s.setFixedHeight(38)
            s.setStyleSheet(_NO_ARROW); return s

        # ── Section 1: Basic Info ─────────────────────────────
        sec1, g1 = _sec("Basic Information", "🏭")
        self.f_name    = _le("e.g. Raymond Ltd"); self.f_code = _le("e.g. SUP0001")
        self.f_contact = _le("Contact person name")
        self.f_status  = QComboBox(); self.f_status.addItems(["Active","Inactive","Blacklisted"])
        self.f_status.setFixedHeight(38)
        _apply_combo_delegate(self.f_status)
        _add(g1, 0, 0, "Supplier Name", self.f_name, req=True)
        _add(g1, 0, 1, "Status",        self.f_status)
        _add(g1, 1, 0, "Supplier Code", self.f_code, hint="Leave blank to auto-generate on save")
        _add(g1, 1, 1, "Contact Person",self.f_contact)
        bl.addWidget(sec1)

        # ── Section 2: Contact ────────────────────────────────
        sec2, g2 = _sec("Contact Details", "📞")
        self.f_phone = _le("+91 98765 43210")
        self.f_email = _le("supplier@example.com")
        self.f_gstin = _le("29AAAAA0000A1Z5")
        _add(g2, 0, 0, "Phone", self.f_phone)
        _add(g2, 0, 1, "Email", self.f_email)
        _add(g2, 1, 0, "GSTIN", self.f_gstin, span=2,
             hint="For GSTR-2A reconciliation")
        bl.addWidget(sec2)

        # ── Section 3: Address ────────────────────────────────
        sec3, g3 = _sec("Address", "📍")
        self.f_address = _le("Street / Area")
        self.f_city    = _le("City")
        self.f_state   = _le("State")
        self.f_pincode = _le("PIN Code")
        _add(g3, 0, 0, "Address", self.f_address, span=2)
        _add(g3, 1, 0, "City",    self.f_city)
        _add(g3, 1, 1, "State",   self.f_state)
        _add(g3, 2, 0, "Pincode", self.f_pincode)
        bl.addWidget(sec3)

        # ── Section 4: Terms ──────────────────────────────────
        sec4, g4 = _sec("Payment & Terms", "💳")
        self.f_terms  = QSpinBox(); self.f_terms.setRange(0,365); self.f_terms.setSuffix(" days"); self.f_terms.setFixedHeight(38); self.f_terms.setStyleSheet(_NO_ARROW)
        self.f_credit = QDoubleSpinBox(); self.f_credit.setRange(0,99999999); self.f_credit.setPrefix("₹ "); self.f_credit.setFixedHeight(38); self.f_credit.setStyleSheet(_NO_ARROW)
        self.f_notes  = QTextEdit(); self.f_notes.setFixedHeight(68); self.f_notes.setPlaceholderText("Additional notes about this supplier…")
        self.f_notes.setStyleSheet(FIELD_SS)
        _add(g4, 0, 0, "Payment Terms", self.f_terms)
        _add(g4, 0, 1, "Credit Limit",  self.f_credit)
        lbl_notes = QLabel("Notes"); lbl_notes.setStyleSheet(LABEL_SS)
        g4.addWidget(lbl_notes, 1, 0)
        g4.addWidget(self.f_notes, 1, 1, 1, 3)
        bl.addWidget(sec4)
        bl.addStretch()

    def load_for_add(self):
        self._edit_code = None
        self._form_title.setText("Add Supplier")
        self.f_name.clear(); self.f_code.clear(); self.f_contact.clear()
        self.f_phone.clear(); self.f_email.clear(); self.f_gstin.clear()
        self.f_address.clear(); self.f_city.clear(); self.f_state.clear()
        self.f_pincode.clear(); self.f_terms.setValue(30)
        self.f_credit.setValue(0); self.f_notes.clear()
        self.f_status.setCurrentIndex(0)

    def load_for_edit(self, code):
        self._edit_code = code
        self._form_title.setText("Edit Supplier")
        row = _qone(self.db_name, "SELECT * FROM suppliers WHERE code=?", (code,))
        if not row: return
        self.f_name.setText(row.get("name",""))
        self.f_code.setText(row.get("code",""))
        self.f_contact.setText(row.get("contact_person",""))
        self.f_phone.setText(row.get("phone",""))
        self.f_email.setText(row.get("email",""))
        self.f_gstin.setText(row.get("gstin",""))
        self.f_address.setText(row.get("address",""))
        self.f_city.setText(row.get("city",""))
        self.f_state.setText(row.get("state",""))
        self.f_pincode.setText(row.get("pincode",""))
        self.f_terms.setValue(int(row.get("payment_terms_days",30) or 30))
        self.f_credit.setValue(float(row.get("credit_limit",0) or 0))
        self.f_notes.setPlainText(row.get("notes",""))
        idx = self.f_status.findText(row.get("status","Active"))
        if idx >= 0: self.f_status.setCurrentIndex(idx)

    def _save(self):
        name = self.f_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Required", "Supplier Name is required.")
            return
        data = dict(
            code            = self.f_code.text().strip() or self._edit_code,
            name            = name,
            gstin           = self.f_gstin.text().strip(),
            contact_person  = self.f_contact.text().strip(),
            phone           = self.f_phone.text().strip(),
            email           = self.f_email.text().strip(),
            address         = self.f_address.text().strip(),
            city            = self.f_city.text().strip(),
            state           = self.f_state.text().strip(),
            pincode         = self.f_pincode.text().strip(),
            payment_terms_days = self.f_terms.value(),
            credit_limit    = self.f_credit.value(),
            status          = self.f_status.currentText(),
            notes           = self.f_notes.toPlainText().strip(),
        )
        code = save_supplier(self.db_name, data, self.current_user)
        if code:
            self.saved.emit(code)
        else:
            QMessageBox.critical(self, "Error", "Could not save supplier.")


# ─────────────────────────────────────────────────────────────────────────────
#  SUPPLIER LIST WIDGET
# ─────────────────────────────────────────────────────────────────────────────
class SupplierListWidget(QWidget):
    def __init__(self, db_name, on_add, on_edit, on_view, company_name="", parent=None):
        super().__init__(parent)
        self.db_name = db_name
        self._on_edit = on_edit
        self._on_view = on_view
        self._rows    = []

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.setStyleSheet(f"background:{C['bg_light']};")

        # ── Top bar ──────────────────────────────────────────
        top = QFrame(); top.setFixedHeight(56)
        top.setStyleSheet("background:#f5f5f7;border-bottom:1px solid #d2d2d7;")
        tl = QHBoxLayout(top); tl.setContentsMargins(24,0,24,0); tl.setSpacing(12)
        tl.addStretch()

        add_btn = QPushButton("＋  Add Supplier")
        add_btn.setFixedHeight(38); add_btn.setMinimumWidth(148)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(_BTN_PRIMARY)
        add_btn.clicked.connect(on_add)
        tl.addWidget(add_btn)
        root.addWidget(top)

        # ── Content ──────────────────────────────────────────
        content = QWidget(); content.setStyleSheet(f"background:{C['bg_light']};")
        cl = QVBoxLayout(content); cl.setContentsMargins(24,16,24,16); cl.setSpacing(12)

        # Search
        sw = QFrame()
        sw.setStyleSheet(
            f"QFrame{{background:{C['bg_white']};border:1.5px solid {C['border']};border-radius:12px;}}")
        sl = QHBoxLayout(sw); sl.setContentsMargins(12,0,12,0); sl.setSpacing(8)
        sl.addWidget(QLabel("🔍", styleSheet="font-size:14px;background:transparent;border:none;"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name, code, phone, GSTIN, city…")
        self._search.setFixedHeight(38)
        self._search.setStyleSheet(f"QLineEdit{{border:none;background:transparent;font-size:13px;color:{C['text']};}}")
        self._search.textChanged.connect(self._load)
        sl.addWidget(self._search, 1)
        cl.addWidget(sw)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Supplier", "GSTIN", "Contact", "Phone",
            "Products", "Stock", "Last Order", "Status"
        ])
        self._table.setStyleSheet(_TABLE_SS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.itemDoubleClicked.connect(self._on_double_click)
        cl.addWidget(self._table, 1)

        # Bottom count + action hint
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"font-size:11px;color:{C['text3']};background:transparent;border:none;")
        hint = QLabel("Double-click a supplier to view inventory  ·  Right-click to edit")
        hint.setStyleSheet(f"font-size:11px;color:{C['text3']};background:transparent;border:none;")
        bot = QHBoxLayout()
        bot.addWidget(self._count_lbl); bot.addStretch(); bot.addWidget(hint)
        cl.addLayout(bot)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self._load()

    def _load(self):
        search = self._search.text().strip() if hasattr(self,'_search') else ""
        self._rows = get_suppliers(self.db_name, search)
        self._table.setRowCount(len(self._rows))

        for i, r in enumerate(self._rows):
            self._table.setRowHeight(i, 52)

            # Supplier name + city
            name_w = QWidget(); nl = QVBoxLayout(name_w)
            nl.setContentsMargins(12,4,4,4); nl.setSpacing(1)
            n = QLabel(r.get("name","—")); n.setFont(_F(13,bold=True))
            n.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
            c2 = QLabel(f"{r.get('code','')}  {('· '+r['city']) if r.get('city') else ''}".strip())
            c2.setStyleSheet(f"font-size:10px;color:{C['text3']};background:transparent;border:none;")
            nl.addWidget(n); nl.addWidget(c2)
            self._table.setCellWidget(i, 0, name_w)

            for j, val in enumerate([
                r.get("gstin","—") or "—",
                r.get("contact_person","—") or "—",
                r.get("phone","—") or "—",
                str(r.get("total_products",0) or 0),
                str(r.get("total_stock",0) or 0),
                (r.get("last_order","")[:10] if r.get("last_order") else "—"),
            ], 1):
                item = QTableWidgetItem(val)
                item.setForeground(QColor(C['text2']))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(i, j, item)

            # Status badge
            status = r.get("status","Active")
            bg = "#f0fdf4" if status=="Active" else "#fef2f2"
            fg = "#16a34a" if status=="Active" else "#dc2626"
            st_w = QWidget(); stl = QHBoxLayout(st_w); stl.setContentsMargins(8,0,4,0)
            sb = QLabel(f"  {status}  ")
            sb.setStyleSheet(f"background:{bg};color:{fg};border-radius:5px;font-size:11px;font-weight:700;padding:2px 0;")
            stl.addWidget(sb); stl.addStretch()
            self._table.setCellWidget(i, 7, st_w)

        self._count_lbl.setText(
            f"{len(self._rows)} supplier{'s' if len(self._rows)!=1 else ''}"
            + (f"  ·  \"{self._search.text().strip()}\"" if self._search.text().strip() else ""))

    def _on_double_click(self, item):
        row = item.row()
        if 0 <= row < len(self._rows):
            r = self._rows[row]
            self._on_view(r["code"], r.get("name",""))


# ─────────────────────────────────────────────────────────────────────────────
#  SUPPLIER PAGE  (top-level, matches ProductPage pattern)
# ─────────────────────────────────────────────────────────────────────────────
class SupplierPage(QWidget):
    def __init__(self, db_name, company_name="", on_back=None,
                 current_user="Admin", parent=None):
        super().__init__(parent)
        self.db_name      = db_name
        self.current_user = current_user
        self.setStyleSheet(f"background:{C['bg_light']};")

        init_supplier_tables(db_name)

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Stack: list | detail ──────────────────────────────
        self._stack = QStackedWidget()

        # Supplier list
        self._list = SupplierListWidget(
            db_name      = db_name,
            on_add       = self._open_add,
            on_edit      = self._open_edit,
            on_view      = self._open_detail,
            company_name = company_name,
            parent       = self,
        )
        self._stack.addWidget(self._list)   # idx 0

        # Detail (inventory view)
        self._detail = SupplierDetailWidget(db_name, self)
        self._detail.back.connect(self._back_to_list)
        self._stack.addWidget(self._detail) # idx 1

        root.addWidget(self._stack)

        # ── Slide panel for Add/Edit form ─────────────────────
        self._panel = _SlidePanel(self)
        self._form  = None
        QTimer.singleShot(0, self._build_form_deferred)

    def _build_form_deferred(self):
        self._form = SupplierFormWidget(self.db_name, self.current_user, self._panel)
        fl = QVBoxLayout(self._panel); fl.setContentsMargins(0,0,0,0); fl.setSpacing(0)
        fl.addWidget(self._form)
        self._form.cancel.connect(self._panel.slide_out)
        self._form.saved.connect(self._on_saved)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._panel.resize_to_parent()

    def _open_add(self):
        if not self._form:
            QTimer.singleShot(50, self._open_add); return
        self._form.load_for_add()
        self._panel.slide_in()

    def _open_edit(self, code):
        if not self._form:
            QTimer.singleShot(50, lambda: self._open_edit(code)); return
        self._form.load_for_edit(code)
        self._panel.slide_in()

    def _open_detail(self, sup_code, sup_name):
        self._detail.load(sup_code, sup_name)
        self._stack.setCurrentIndex(1)

    def _back_to_list(self):
        self._list._load()
        self._stack.setCurrentIndex(0)

    def _on_saved(self, code):
        self._panel.slide_out()
        self._list._load()
