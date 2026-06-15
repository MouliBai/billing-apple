"""
billing_page.py  —  Evo Aura  •  POS Billing
=============================================
Fast keyboard-first billing:
  • Product search (name / alias / barcode / code) with live dropdown
  • Barcode scanner support (fast-type + Enter)
  • Inline editable qty / price / discount per row
  • Duplicate scan → increments qty on existing row
  • Customer search with walk-in default
  • Bill-level discount + round-off
  • Payment: Cash / Card / UPI / Split
  • Cash change calculator
  • Hold bill (up to 5 simultaneous held bills)
  • F2 = search  F4 = payment  F8 = hold  F10 = print+save  Esc = clear row
  • Thermal print preview (80 mm)
  • Invoice table + invoice_items table auto-created
"""

import sys
import os
import sqlite3
import json
from datetime import datetime, date
from functools import partial

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QMessageBox, QShortcut,
    QGridLayout, QComboBox, QAbstractItemView,
    QListWidget, QListWidgetItem, QSplitter,
    QScrollArea, QDialog, QTextEdit, QStackedWidget,
    QDoubleSpinBox, QSpinBox, QApplication, QSizePolicy,
    QCompleter, QAbstractItemView as QAIView
)
from PyQt5.QtGui  import (
    QFont, QColor, QBrush, QPixmap, QKeySequence,
    QTextDocument, QTextCursor
)
from PyQt5.QtCore import Qt, QTimer, QStringListModel, pyqtSignal, QThread

# ─────────────────────────────────────────────────────────
#  DESIGN TOKENS  (same as dashboard / product_page)
# ─────────────────────────────────────────────────────────
PRIMARY  = "#1a7fe8"
DANGER   = "#ef4444"
SUCCESS  = "#10b981"
WARNING  = "#f59e0b"
BG_LIGHT = "#f1f5f9"
WHITE    = "#ffffff"
BORDER   = "#e2e8f0"
TEXT     = "#1e293b"
MUTED    = "#64748b"
FONT     = "Segoe UI"

FIELD_SS = (
    "QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox{"
    "border:1px solid #cbd5e1;border-radius:7px;"
    "padding:5px 10px;font-size:13px;"
    "background:white;color:#1e293b;min-height:32px;}"
    "QLineEdit:focus,QComboBox:focus{"
    "border:1.5px solid #1a7fe8;background:#f8fbff;}"
)

def _btn(bg, fg="#fff", hover=None, radius=8, h=36):
    hov = hover or bg
    return (f"QPushButton{{background:{bg};color:{fg};border:none;"
            f"border-radius:{radius}px;font-size:13px;font-weight:700;"
            f"padding:0 14px;min-height:{h}px;}}"
            f"QPushButton:hover{{background:{hov};}}"
            f"QPushButton:pressed{{opacity:0.85;}}")

def _card(radius=12):
    return (f"background:{WHITE};border:1px solid {BORDER};"
            f"border-radius:{radius}px;")


# ─────────────────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────────────────

def init_billing_tables(db):
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id    TEXT PRIMARY KEY,
                date          TEXT,
                customer_name TEXT DEFAULT 'Walk-in',
                customer_phone TEXT DEFAULT '',
                subtotal      REAL DEFAULT 0,
                discount_amt  REAL DEFAULT 0,
                tax_amt       REAL DEFAULT 0,
                round_off     REAL DEFAULT 0,
                grand_total   REAL DEFAULT 0,
                payment_mode  TEXT DEFAULT 'Cash',
                amount_paid   REAL DEFAULT 0,
                change_amt    REAL DEFAULT 0,
                notes         TEXT DEFAULT '',
                created_by    TEXT DEFAULT 'Admin',
                status        TEXT DEFAULT 'Paid'
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id    TEXT,
                product_code  TEXT,
                product_name  TEXT,
                unit          TEXT DEFAULT '',
                qty           REAL DEFAULT 1,
                mrp           REAL DEFAULT 0,
                price         REAL DEFAULT 0,
                discount_pct  REAL DEFAULT 0,
                gst_rate      TEXT DEFAULT '0%',
                tax_amt       REAL DEFAULT 0,
                total         REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS customers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT,
                phone         TEXT UNIQUE,
                address       TEXT DEFAULT '',
                balance       REAL DEFAULT 0,
                loyalty_pts   INTEGER DEFAULT 0,
                created_at    TEXT DEFAULT ''
            );
        """)


def get_next_invoice_id(db):
    today  = date.today()
    prefix = f"INV-{str(today.year)[2:]}{str(today.month).zfill(2)}-"
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT invoice_id FROM invoices WHERE invoice_id LIKE ? "
            "ORDER BY invoice_id DESC LIMIT 1",
            (prefix + "%",)
        ).fetchone()
    if row:
        try:
            num = int(row[0].split("-")[-1]) + 1
        except Exception:
            num = 1
    else:
        num = 1
    return f"{prefix}{str(num).zfill(4)}"


def search_products(db, query, limit=10):
    """Search by name, alias, barcode, item_code. Returns list of dicts."""
    q = f"%{query}%"
    try:
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                """SELECT item_code, name, unit, selling_price, mrp,
                          gst_rate, stock, min_selling_price, purchase_price,
                          alias_names, barcode
                   FROM products
                   WHERE is_deleted=0 AND status='Active'
                     AND (name LIKE ? OR alias_names LIKE ?
                          OR barcode LIKE ? OR item_code LIKE ?)
                   ORDER BY name LIMIT ?""",
                (q, q, q, q, limit)
            ).fetchall()
    except Exception:
        return []
    keys = ["item_code","name","unit","selling_price","mrp","gst_rate",
            "stock","min_selling_price","purchase_price","alias_names","barcode"]
    return [dict(zip(keys, r)) for r in rows]


def search_customers(db, query):
    q = f"%{query}%"
    try:
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT name, phone, balance, loyalty_pts FROM customers "
                "WHERE name LIKE ? OR phone LIKE ? ORDER BY name LIMIT 8",
                (q, q)
            ).fetchall()
        return rows
    except Exception:
        return []


def save_invoice(db, inv_id, customer_name, customer_phone,
                 items, discount_amt, round_off,
                 payment_mode, amount_paid, notes, created_by):
    """Save invoice + items + update stock."""
    now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subtotal  = sum(r["price"] * r["qty"] for r in items)
    tax_amt   = sum(r["tax_amt"] for r in items)
    grand_total = subtotal + tax_amt - discount_amt + round_off
    change_amt  = max(0, amount_paid - grand_total)

    with sqlite3.connect(db) as conn:
        conn.execute(
            """INSERT INTO invoices
               (invoice_id,date,customer_name,customer_phone,
                subtotal,discount_amt,tax_amt,round_off,grand_total,
                payment_mode,amount_paid,change_amt,notes,created_by,status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Paid')""",
            (inv_id, now, customer_name, customer_phone,
             subtotal, discount_amt, tax_amt, round_off, grand_total,
             payment_mode, amount_paid, change_amt, notes, created_by)
        )
        for it in items:
            conn.execute(
                """INSERT INTO invoice_items
                   (invoice_id,product_code,product_name,unit,qty,
                    mrp,price,discount_pct,gst_rate,tax_amt,total)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (inv_id, it["item_code"], it["name"], it.get("unit",""),
                 it["qty"], it.get("mrp",0), it["price"],
                 it.get("discount_pct",0), it.get("gst_rate","0%"),
                 it["tax_amt"], it["price"]*it["qty"] - it["tax_amt"])
            )
            # update product stock
            conn.execute(
                "UPDATE products SET stock=MAX(0,stock-?), "
                "total_qty_sold=total_qty_sold+?, "
                "total_revenue=total_revenue+?, "
                "sale_count=sale_count+1, "
                "last_sold_date=? "
                "WHERE item_code=?",
                (it["qty"], it["qty"],
                 it["price"]*it["qty"], now, it["item_code"])
            )
    return grand_total, change_amt


def load_company_info(db):
    try:
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT logo,company_name,phone,address,gst,footer "
                "FROM company_info WHERE id=1"
            ).fetchone()
        if row:
            return {"logo":row[0],"company_name":row[1] or "",
                    "phone":row[2] or "","address":row[3] or "",
                    "gst":row[4] or "","footer":row[5] or ""}
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────────────────────
#  PRODUCT SEARCH DROPDOWN
# ─────────────────────────────────────────────────────────

class ProductDropdown(QListWidget):
    product_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QListWidget {{
                background:{WHITE}; border:1.5px solid {PRIMARY};
                border-radius:10px; font-size:13px; outline:none;
            }}
            QListWidget::item {{
                padding:8px 14px; color:{TEXT}; border-bottom:1px solid {BORDER};
            }}
            QListWidget::item:selected {{
                background:{PRIMARY}; color:white;
            }}
            QListWidget::item:hover {{
                background:#eef5ff; color:{PRIMARY};
            }}
        """)
        self._data = []
        self.itemClicked.connect(self._on_click)

    def show_results(self, results, anchor_widget):
        self._data = results
        self.clear()
        if not results:
            self.hide(); return

        for p in results:
            stock = p.get("stock", 0)
            stock_color = DANGER if stock == 0 else (WARNING if stock < 5 else SUCCESS)
            text = (f"{p['name']}  "
                    f"[{p['item_code']}]  "
                    f"₹{float(p['selling_price']):.2f}  "
                    f"Stock:{stock}")
            item = QListWidgetItem(text)
            item.setForeground(QColor(DANGER if stock == 0 else TEXT))
            self.addItem(item)

        # position below anchor
        pos    = anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft())
        width  = max(anchor_widget.width(), 480)
        height = min(len(results) * 38 + 8, 300)
        self.setGeometry(pos.x(), pos.y(), width, height)
        self.show()
        self.setCurrentRow(0)

    def _on_click(self, item):
        idx = self.row(item)
        if 0 <= idx < len(self._data):
            self.product_selected.emit(self._data[idx])
        self.hide()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.currentItem()
            if item:
                self._on_click(item)
        elif e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


# ─────────────────────────────────────────────────────────
#  BILL ITEMS TABLE
# ─────────────────────────────────────────────────────────

class BillTable(QTableWidget):
    totals_changed = pyqtSignal()

    COLS = ["#", "Product", "Unit", "Qty", "MRP ₹", "Price ₹", "Disc%", "GST", "Total ₹", ""]
    C_SL, C_NAME, C_UNIT, C_QTY, C_MRP, C_PRICE, C_DISC, C_GST, C_TOTAL, C_DEL = range(10)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(self.C_NAME, QHeaderView.Stretch)
        for c, w in [(self.C_SL,36),(self.C_UNIT,52),(self.C_QTY,62),
                     (self.C_MRP,86),(self.C_PRICE,86),(self.C_DISC,58),
                     (self.C_GST,54),(self.C_TOTAL,95),(self.C_DEL,36)]:
            self.setColumnWidth(c, w)
            hdr.setSectionResizeMode(c, QHeaderView.Fixed)

        self.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:none;
                gridline-color:#f0f4f8; font-size:13px;
                outline:none;
            }}
            QHeaderView::section {{
                background:#f8fafc; font-weight:700; padding:7px 4px;
                border:none; border-bottom:2px solid {BORDER};
                color:#475569; font-size:12px;
            }}
            QTableWidget::item {{ padding:4px 6px; color:{TEXT}; }}
            QTableWidget::item:selected {{
                background:#eef5ff; color:{TEXT};
            }}
            QTableWidget::item:alternate {{ background:#fafbfc; }}
        """)

        self._items = []          # list of dicts — source of truth
        self.itemChanged.connect(self._on_item_changed)
        self._updating = False

    # ── Public API ────────────────────────────────────────

    def add_product(self, p: dict):
        """Add product or increment qty if already in bill."""
        code = p["item_code"]
        for i, it in enumerate(self._items):
            if it["item_code"] == code:
                it["qty"] += 1
                self._recalc_row(i)
                self.totals_changed.emit()
                return

        gst_pct = self._parse_gst(p.get("gst_rate","0%"))
        price   = float(p.get("selling_price", 0))
        qty     = 1
        tax_amt = round(price * qty * gst_pct / 100, 2)

        item = {
            "item_code":    code,
            "name":         p.get("name",""),
            "unit":         p.get("unit",""),
            "qty":          qty,
            "mrp":          float(p.get("mrp", price)),
            "price":        price,
            "discount_pct": 0.0,
            "gst_rate":     p.get("gst_rate","0%"),
            "gst_pct":      gst_pct,
            "tax_amt":      tax_amt,
            "min_price":    float(p.get("min_selling_price", 0)),
            "stock":        int(p.get("stock", 0)),
        }
        self._items.append(item)
        self._insert_row(len(self._items) - 1)
        self.totals_changed.emit()
        # scroll to new row
        self.scrollToBottom()

    def get_items(self):
        return list(self._items)

    def clear_bill(self):
        self._items.clear()
        self._updating = True
        self.setRowCount(0)
        self._updating = False
        self.totals_changed.emit()

    def get_subtotal(self):
        return sum(it["price"] * it["qty"] for it in self._items)

    def get_tax_total(self):
        return sum(it["tax_amt"] for it in self._items)

    # ── Internal rendering ────────────────────────────────

    def _parse_gst(self, gst_str):
        try:
            return float(str(gst_str).replace("%","").strip())
        except Exception:
            return 0.0

    def _insert_row(self, idx):
        self._updating = True
        r = self.rowCount()
        self.insertRow(r)
        self.setRowHeight(r, 40)
        self._fill_row(r, idx)
        self._updating = False

    def _fill_row(self, r, idx):
        it = self._items[idx]

        def ro(txt, align=Qt.AlignCenter):
            wi = QTableWidgetItem(str(txt))
            wi.setTextAlignment(align)
            wi.setFlags(wi.flags() & ~Qt.ItemIsEditable)
            return wi

        def ed(txt, align=Qt.AlignCenter):
            wi = QTableWidgetItem(str(txt))
            wi.setTextAlignment(align)
            wi.setFlags(wi.flags() | Qt.ItemIsEditable)
            return wi

        self.setItem(r, self.C_SL,    ro(idx+1))
        self.setItem(r, self.C_NAME,  ro(it["name"], Qt.AlignLeft | Qt.AlignVCenter))
        self.setItem(r, self.C_UNIT,  ro(it["unit"]))
        self.setItem(r, self.C_QTY,   ed(it["qty"]))
        self.setItem(r, self.C_MRP,   ro(f"{it['mrp']:.2f}"))
        self.setItem(r, self.C_PRICE, ed(f"{it['price']:.2f}"))
        self.setItem(r, self.C_DISC,  ed(f"{it['discount_pct']:.1f}"))
        self.setItem(r, self.C_GST,   ro(it["gst_rate"]))

        total = it["price"] * it["qty"]
        ti = ro(f"{total:.2f}", Qt.AlignRight | Qt.AlignVCenter)
        ti.setFont(QFont(FONT, 13, QFont.Bold))
        self.setItem(r, self.C_TOTAL, ti)

        # highlight below min price
        if it["min_price"] > 0 and it["price"] < it["min_price"]:
            for c in range(self.C_DEL):
                w = self.item(r, c)
                if w:
                    w.setBackground(QBrush(QColor("#fff0f0")))

        # delete button cell — use a small label trick
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(28, 28)
        del_btn.setStyleSheet(
            f"QPushButton{{background:#fee2e2;color:{DANGER};border:none;"
            f"border-radius:6px;font-weight:700;font-size:13px;}}"
            f"QPushButton:hover{{background:#fecaca;}}"
        )
        del_btn.clicked.connect(partial(self._delete_row, idx))
        cell = QWidget()
        cl   = QHBoxLayout(cell)
        cl.setContentsMargins(4,4,4,4)
        cl.addWidget(del_btn)
        self.setCellWidget(r, self.C_DEL, cell)

    def _recalc_row(self, idx):
        if idx >= self.rowCount():
            return
        self._updating = True
        it  = self._items[idx]
        r   = idx
        gst = it["gst_pct"]
        net = it["price"] * it["qty"]
        it["tax_amt"] = round(net * gst / 100, 2)

        self.item(r, self.C_QTY).setText(str(it["qty"]))
        self.item(r, self.C_PRICE).setText(f"{it['price']:.2f}")
        self.item(r, self.C_DISC).setText(f"{it['discount_pct']:.1f}")

        total_item = self.item(r, self.C_TOTAL)
        if total_item:
            total_item.setText(f"{net:.2f}")

        # color row if below min
        bg = QBrush(QColor("#fff0f0")) if (it["min_price"] > 0 and it["price"] < it["min_price"]) else QBrush()
        for c in range(self.C_DEL):
            w = self.item(r, c)
            if w:
                w.setBackground(bg)

        self._updating = False

    def _delete_row(self, idx):
        if idx < len(self._items):
            self._items.pop(idx)
            self.removeRow(idx)
            # renumber
            self._updating = True
            for r in range(self.rowCount()):
                sl = self.item(r, self.C_SL)
                if sl:
                    sl.setText(str(r+1))
                # rewire delete button
                del_btn = QPushButton("✕")
                del_btn.setFixedSize(28, 28)
                del_btn.setStyleSheet(
                    f"QPushButton{{background:#fee2e2;color:{DANGER};border:none;"
                    f"border-radius:6px;font-weight:700;font-size:13px;}}"
                    f"QPushButton:hover{{background:#fecaca;}}"
                )
                del_btn.clicked.connect(partial(self._delete_row, r))
                cell = QWidget(); cl = QHBoxLayout(cell)
                cl.setContentsMargins(4,4,4,4); cl.addWidget(del_btn)
                self.setCellWidget(r, self.C_DEL, cell)
            self._updating = False
            self.totals_changed.emit()

    def _on_item_changed(self, item):
        if self._updating:
            return
        r   = item.row()
        c   = item.column()
        if r >= len(self._items):
            return
        it  = self._items[r]
        txt = item.text().strip()

        try:
            if c == self.C_QTY:
                val = float(txt)
                if val <= 0:
                    raise ValueError
                it["qty"] = val
                self._recalc_row(r)
                self.totals_changed.emit()

            elif c == self.C_PRICE:
                val = float(txt)
                if val < 0:
                    raise ValueError
                it["price"] = val
                self._recalc_row(r)
                self.totals_changed.emit()

            elif c == self.C_DISC:
                val = max(0, min(100, float(txt)))
                it["discount_pct"] = val
                mrp   = it["mrp"]
                if mrp > 0:
                    it["price"] = round(mrp * (1 - val/100), 2)
                self._recalc_row(r)
                self.totals_changed.emit()

        except ValueError:
            # restore previous value
            self._recalc_row(r)


# ─────────────────────────────────────────────────────────
#  PRINT PREVIEW DIALOG
# ─────────────────────────────────────────────────────────

class PrintPreviewDialog(QDialog):
    def __init__(self, html: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Print Preview — Thermal Receipt")
        self.setFixedSize(400, 620)
        self.setStyleSheet(f"background:{BG_LIGHT};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background:white; border:1px solid #e2e8f0; border-radius:8px;")

        self._view = QTextEdit()
        self._view.setReadOnly(True)
        self._view.setHtml(html)
        self._view.setStyleSheet("background:white; border:none; font-family:Courier New; font-size:12px;")
        scroll.setWidget(self._view)
        lay.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(_btn("#e2e8f0", TEXT))
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)


# ─────────────────────────────────────────────────────────
#  HELD BILLS DIALOG
# ─────────────────────────────────────────────────────────

class HeldBillsDialog(QDialog):
    bill_selected = pyqtSignal(int)   # emits index into held list

    def __init__(self, held: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Held Bills")
        self.setFixedSize(480, 320)
        self.setStyleSheet(f"background:{BG_LIGHT};")
        self._held = held

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Select a held bill to resume:",
                             styleSheet=f"font-size:14px;font-weight:700;color:{TEXT};"))

        for i, bill in enumerate(held):
            row = QFrame()
            row.setStyleSheet(f"background:{WHITE};border:1px solid {BORDER};border-radius:8px;")
            rl  = QHBoxLayout(row); rl.setContentsMargins(14,8,14,8)
            info = QLabel(
                f"<b>Bill #{i+1}</b>  —  "
                f"{bill['customer']}  |  "
                f"{len(bill['items'])} items  |  "
                f"₹{bill['total']:.2f}"
            )
            info.setStyleSheet(f"font-size:13px;color:{TEXT};background:transparent;")
            resume = QPushButton("Resume")
            resume.setFixedSize(80,30)
            resume.setStyleSheet(_btn(PRIMARY, h=30))
            resume.clicked.connect(partial(self._pick, i))
            rl.addWidget(info,1); rl.addWidget(resume)
            lay.addWidget(row)

        lay.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(34)
        cancel.setStyleSheet(_btn("#e2e8f0", TEXT))
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel)

    def _pick(self, i):
        self.bill_selected.emit(i)
        self.accept()


# ─────────────────────────────────────────────────────────
#  MAIN BILLING PAGE
# ─────────────────────────────────────────────────────────

class BillingPage(QWidget):
    def __init__(self, db_name, company_name="", on_back=None,
                 current_user="Admin"):
        super().__init__()
        self.db_name      = db_name
        self.company_name = company_name
        self.on_back      = on_back
        self.current_user = current_user
        self._held_bills  = []      # list of snapshots
        self._search_timer = QTimer(); self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        self._dropdown    = ProductDropdown(self)
        self._dropdown.product_selected.connect(self._add_product)
        self._dropdown.hide()

        init_billing_tables(db_name)
        self._company   = load_company_info(db_name)
        self._invoice_id = get_next_invoice_id(db_name)

        self._build_ui()
        self._setup_shortcuts()
        self._update_totals()

    # ─────────────────────────────────────────────────────
    #  UI BUILD
    # ─────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"background:{BG_LIGHT};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────
        root.addWidget(self._build_topbar())

        # ── Body: left panel + center table + right summary ──
        body = QHBoxLayout()
        body.setContentsMargins(14, 10, 14, 10)
        body.setSpacing(12)

        body.addWidget(self._build_left_panel(),  0)
        body.addWidget(self._build_center_panel(), 1)
        body.addWidget(self._build_right_panel(),  0)

        root.addLayout(body, 1)

    # ── Top bar ───────────────────────────────────────────

    def _build_topbar(self):
        bar = QFrame()
        bar.setFixedHeight(58)
        bar.setStyleSheet(
            f"background:{WHITE};border-bottom:1px solid {BORDER};"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(10)

        # Invoice number badge
        inv_badge = QFrame()
        inv_badge.setStyleSheet(
            f"background:{PRIMARY}18;border:1px solid {PRIMARY}44;"
            f"border-radius:8px;padding:0 4px;"
        )
        ib_lay = QHBoxLayout(inv_badge)
        ib_lay.setContentsMargins(10, 0, 10, 0)
        self.lbl_inv_id = QLabel(self._invoice_id)
        self.lbl_inv_id.setFont(QFont(FONT, 13, QFont.Bold))
        self.lbl_inv_id.setStyleSheet(f"color:{PRIMARY};background:transparent;")
        ib_lay.addWidget(QLabel("🧾", styleSheet="font-size:15px;background:transparent;"))
        ib_lay.addWidget(self.lbl_inv_id)
        lay.addWidget(inv_badge)

        # Date/time
        self._lbl_clock = QLabel()
        self._lbl_clock.setStyleSheet(f"color:{MUTED};font-size:12px;background:transparent;")
        self._tick()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick)
        self._clock_timer.start(1000)
        lay.addWidget(self._lbl_clock)

        lay.addStretch()

        # Hold bill counter badge
        self._hold_badge = QLabel("")
        self._hold_badge.setStyleSheet(
            f"background:{WARNING}22;color:{WARNING};border:1px solid {WARNING}55;"
            f"border-radius:8px;padding:3px 10px;font-size:12px;font-weight:700;"
        )
        self._hold_badge.setVisible(False)
        lay.addWidget(self._hold_badge)

        # Shortcut hint
        hint = QLabel("F2 Search  F4 Pay  F8 Hold  F10 Save")
        hint.setStyleSheet(f"color:{MUTED};font-size:11px;background:transparent;")
        lay.addWidget(hint)

        # New bill button
        new_btn = QPushButton("＋ New Bill")
        new_btn.setFixedHeight(34)
        new_btn.setStyleSheet(_btn("#eef5ff", PRIMARY, "#ddeeff"))
        new_btn.clicked.connect(self._new_bill)
        lay.addWidget(new_btn)

        return bar

    def _tick(self):
        self._lbl_clock.setText(datetime.now().strftime("%d %b %Y  •  %H:%M:%S"))

    # ── Left panel: customer ──────────────────────────────

    def _build_left_panel(self):
        panel = QFrame()
        panel.setFixedWidth(240)
        panel.setStyleSheet(_card(12))
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        lay.addWidget(QLabel("👤  Customer",
            styleSheet=f"font-size:13px;font-weight:700;color:{TEXT};"))

        # Customer search
        self.cust_search = QLineEdit()
        self.cust_search.setPlaceholderText("Name / Phone…")
        self.cust_search.setStyleSheet(FIELD_SS)
        self.cust_search.textChanged.connect(self._search_customer)
        lay.addWidget(self.cust_search)

        # Customer results list
        self._cust_list = QListWidget()
        self._cust_list.setFixedHeight(110)
        self._cust_list.setStyleSheet(
            f"QListWidget{{background:{BG_LIGHT};border:1px solid {BORDER};"
            f"border-radius:7px;font-size:12px;}}"
            f"QListWidget::item{{padding:5px 8px;color:{TEXT};}}"
            f"QListWidget::item:selected{{background:{PRIMARY};color:white;}}"
        )
        self._cust_list.itemClicked.connect(self._select_customer)
        lay.addWidget(self._cust_list)

        # Walk-in default
        self._cust_name  = "Walk-in"
        self._cust_phone = ""

        self._cust_card = QFrame()
        self._cust_card.setStyleSheet(
            f"background:{BG_LIGHT};border:1px solid {BORDER};border-radius:8px;"
        )
        cc_lay = QVBoxLayout(self._cust_card)
        cc_lay.setContentsMargins(10, 8, 10, 8); cc_lay.setSpacing(3)
        self.lbl_cust_name  = QLabel("👤  Walk-in Customer")
        self.lbl_cust_name.setStyleSheet(f"font-size:12px;font-weight:700;color:{TEXT};background:transparent;")
        self.lbl_cust_phone = QLabel("")
        self.lbl_cust_phone.setStyleSheet(f"font-size:11px;color:{MUTED};background:transparent;")
        self.lbl_cust_bal   = QLabel("")
        self.lbl_cust_bal.setStyleSheet(f"font-size:11px;color:{DANGER};background:transparent;")
        cc_lay.addWidget(self.lbl_cust_name)
        cc_lay.addWidget(self.lbl_cust_phone)
        cc_lay.addWidget(self.lbl_cust_bal)
        lay.addWidget(self._cust_card)

        # Separator
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{BORDER};max-height:1px;border:none;")
        lay.addWidget(sep)

        # Notes
        lay.addWidget(QLabel("📝  Notes",
            styleSheet=f"font-size:12px;font-weight:600;color:{MUTED};"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional note for this bill…")
        self.notes_edit.setFixedHeight(72)
        self.notes_edit.setStyleSheet(
            f"border:1px solid {BORDER};border-radius:7px;"
            f"font-size:12px;padding:6px;background:{WHITE};"
        )
        lay.addWidget(self.notes_edit)

        lay.addStretch()
        return panel

    # ── Center panel: search + table ─────────────────────

    def _build_center_panel(self):
        panel = QFrame()
        panel.setStyleSheet(f"background:transparent;")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # Product search bar
        search_frame = QFrame()
        search_frame.setStyleSheet(_card(10))
        sf_lay = QHBoxLayout(search_frame)
        sf_lay.setContentsMargins(10, 8, 10, 8)
        sf_lay.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size:18px;background:transparent;")
        sf_lay.addWidget(search_icon)

        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText(
            "Search product — name / code / barcode / alias  (F2)"
        )
        self.product_search.setStyleSheet(
            f"border:none;font-size:14px;color:{TEXT};background:transparent;"
            f"padding:4px 0;"
        )
        self.product_search.textChanged.connect(self._on_search_changed)
        self.product_search.returnPressed.connect(self._search_enter)
        sf_lay.addWidget(self.product_search, 1)

        clr = QPushButton("✕")
        clr.setFixedSize(28, 28)
        clr.setStyleSheet(
            f"QPushButton{{background:{BG_LIGHT};color:{MUTED};border:none;"
            f"border-radius:6px;font-size:13px;}}"
            f"QPushButton:hover{{background:#e2e8f0;color:{TEXT};}}"
        )
        clr.clicked.connect(lambda: self.product_search.clear())
        sf_lay.addWidget(clr)
        lay.addWidget(search_frame)

        # Items table
        self.bill_table = BillTable()
        self.bill_table.totals_changed.connect(self._update_totals)
        lay.addWidget(self.bill_table, 1)

        # Item count bar
        self._item_count_lbl = QLabel("0 items")
        self._item_count_lbl.setStyleSheet(
            f"font-size:12px;color:{MUTED};padding:2px 0;"
        )
        lay.addWidget(self._item_count_lbl)

        return panel

    # ── Right panel: summary + payment ───────────────────

    def _build_right_panel(self):
        panel = QFrame()
        panel.setFixedWidth(270)
        panel.setStyleSheet(_card(12))
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # ── Totals section ────────────────────────────────
        lay.addWidget(QLabel("💰  Bill Summary",
            styleSheet=f"font-size:13px;font-weight:700;color:{TEXT};"))

        def _row(lbl_text, val_widget, bold=False):
            r = QHBoxLayout(); r.setSpacing(4)
            l = QLabel(lbl_text)
            l.setStyleSheet(
                f"font-size:{'13px' if bold else '12px'};"
                f"font-weight:{'700' if bold else '400'};"
                f"color:{TEXT};background:transparent;"
            )
            r.addWidget(l); r.addStretch(); r.addWidget(val_widget)
            return r

        def _val(bold=False, color=TEXT):
            l = QLabel("₹ 0.00")
            l.setStyleSheet(
                f"font-size:{'13px' if bold else '12px'};"
                f"font-weight:{'700' if bold else '400'};"
                f"color:{color};background:transparent;"
            )
            l.setAlignment(Qt.AlignRight)
            return l

        self.lbl_subtotal  = _val()
        self.lbl_tax       = _val()
        self.lbl_disc_disp = _val(color=DANGER)
        self.lbl_roundoff  = _val(color=MUTED)
        self.lbl_grand     = _val(bold=True, color=PRIMARY)
        self.lbl_grand.setFont(QFont(FONT, 18, QFont.Bold))

        lay.addLayout(_row("Subtotal",    self.lbl_subtotal))
        lay.addLayout(_row("GST",         self.lbl_tax))
        lay.addLayout(_row("Discount",    self.lbl_disc_disp))
        lay.addLayout(_row("Round-off",   self.lbl_roundoff))

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{BORDER};max-height:1px;border:none;")
        lay.addWidget(sep)

        lay.addLayout(_row("GRAND TOTAL", self.lbl_grand, bold=True))

        # Bill discount input
        disc_row = QHBoxLayout()
        disc_row.addWidget(QLabel("Bill Disc ₹",
            styleSheet=f"font-size:12px;color:{MUTED};background:transparent;"))
        self.disc_spin = QDoubleSpinBox()
        self.disc_spin.setRange(0, 999999)
        self.disc_spin.setDecimals(2)
        self.disc_spin.setFixedWidth(90)
        self.disc_spin.setStyleSheet(FIELD_SS)
        self.disc_spin.valueChanged.connect(self._update_totals)
        disc_row.addStretch()
        disc_row.addWidget(self.disc_spin)
        lay.addLayout(disc_row)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background:{BORDER};max-height:1px;border:none;")
        lay.addWidget(sep2)

        # ── Payment section ───────────────────────────────
        lay.addWidget(QLabel("💳  Payment",
            styleSheet=f"font-size:13px;font-weight:700;color:{TEXT};"))

        # Payment mode buttons
        mode_row = QHBoxLayout(); mode_row.setSpacing(6)
        self._pay_btns = {}
        for mode, color in [("Cash",PRIMARY),("Card","#7c3aed"),
                             ("UPI",SUCCESS),("Split",WARNING)]:
            b = QPushButton(mode)
            b.setFixedHeight(32)
            b.setCheckable(True)
            b.setStyleSheet(
                f"QPushButton{{background:{color}22;color:{color};"
                f"border:1.5px solid {color}44;border-radius:7px;"
                f"font-size:12px;font-weight:700;}}"
                f"QPushButton:checked{{background:{color};color:white;"
                f"border:1.5px solid {color};}}"
                f"QPushButton:hover{{background:{color}33;}}"
            )
            b.clicked.connect(partial(self._set_payment_mode, mode))
            mode_row.addWidget(b)
            self._pay_btns[mode] = b
        lay.addLayout(mode_row)
        self._payment_mode = "Cash"
        self._pay_btns["Cash"].setChecked(True)

        # Amount paid / reference
        paid_row = QHBoxLayout(); paid_row.setSpacing(6)
        self.lbl_paid_label = QLabel("Amount Received ₹")
        self.lbl_paid_label.setStyleSheet(
            f"font-size:12px;color:{MUTED};background:transparent;"
        )
        paid_row.addWidget(self.lbl_paid_label)
        self.paid_spin = QDoubleSpinBox()
        self.paid_spin.setRange(0, 9999999)
        self.paid_spin.setDecimals(2)
        self.paid_spin.setFixedWidth(100)
        self.paid_spin.setStyleSheet(FIELD_SS)
        self.paid_spin.valueChanged.connect(self._update_change)
        paid_row.addWidget(self.paid_spin)
        lay.addLayout(paid_row)

        # Change display
        self.lbl_change = QLabel("Change  ₹ 0.00")
        self.lbl_change.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{SUCCESS};"
            f"background:{SUCCESS}18;border-radius:7px;padding:6px 10px;"
        )
        self.lbl_change.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_change)

        # UPI ref (hidden by default)
        self.upi_ref = QLineEdit()
        self.upi_ref.setPlaceholderText("UPI / Card ref no.")
        self.upi_ref.setStyleSheet(FIELD_SS)
        self.upi_ref.setVisible(False)
        lay.addWidget(self.upi_ref)

        lay.addStretch()

        sep3 = QFrame(); sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(f"background:{BORDER};max-height:1px;border:none;")
        lay.addWidget(sep3)

        # ── Action buttons ────────────────────────────────
        save_btn = QPushButton("🖨️  Print & Save  (F10)")
        save_btn.setFixedHeight(42)
        save_btn.setStyleSheet(_btn(PRIMARY, h=42))
        save_btn.setFont(QFont(FONT, 13, QFont.Bold))
        save_btn.clicked.connect(self._print_and_save)
        lay.addWidget(save_btn)

        save_only = QPushButton("💾  Save Only")
        save_only.setFixedHeight(36)
        save_only.setStyleSheet(_btn("#eef5ff", PRIMARY, "#ddeeff"))
        save_only.clicked.connect(self._save_only)
        lay.addWidget(save_only)

        hold_btn = QPushButton("⏸  Hold Bill  (F8)")
        hold_btn.setFixedHeight(36)
        hold_btn.setStyleSheet(_btn("#fef3c7", "#b45309", "#fde68a"))
        hold_btn.clicked.connect(self._hold_bill)
        lay.addWidget(hold_btn)

        resume_btn = QPushButton("▶  Resume Held")
        resume_btn.setFixedHeight(34)
        resume_btn.setStyleSheet(_btn("#f1f5f9", MUTED, "#e2e8f0"))
        resume_btn.clicked.connect(self._resume_held)
        lay.addWidget(resume_btn)

        return panel

    # ─────────────────────────────────────────────────────
    #  KEYBOARD SHORTCUTS
    # ─────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F2"),  self).activated.connect(
            lambda: self.product_search.setFocus())
        QShortcut(QKeySequence("F4"),  self).activated.connect(
            lambda: self.paid_spin.setFocus())
        QShortcut(QKeySequence("F8"),  self).activated.connect(self._hold_bill)
        QShortcut(QKeySequence("F10"), self).activated.connect(self._print_and_save)
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self._dropdown.hide)

    # ─────────────────────────────────────────────────────
    #  PRODUCT SEARCH
    # ─────────────────────────────────────────────────────

    def _on_search_changed(self, text):
        self._dropdown.hide()
        if len(text.strip()) >= 1:
            self._search_timer.start(180)   # debounce 180 ms
        else:
            self._search_timer.stop()

    def _do_search(self):
        query = self.product_search.text().strip()
        if not query:
            return
        results = search_products(self.db_name, query)
        self._dropdown.show_results(results, self.product_search)
        self._dropdown.setFocus()

    def _search_enter(self):
        """Enter on search bar — if dropdown visible pick first, else search."""
        if self._dropdown.isVisible():
            items = self._dropdown._data
            if items:
                self._add_product(items[0])
                self._dropdown.hide()
        else:
            self._do_search()

    def _add_product(self, p: dict):
        self.bill_table.add_product(p)
        self.product_search.clear()
        self.product_search.setFocus()
        self._dropdown.hide()

    # ─────────────────────────────────────────────────────
    #  CUSTOMER SEARCH
    # ─────────────────────────────────────────────────────

    def _search_customer(self, text):
        self._cust_list.clear()
        if len(text.strip()) < 1:
            return
        rows = search_customers(self.db_name, text)
        for name, phone, bal, pts in rows:
            item = QListWidgetItem(f"{name}  •  {phone}")
            item.setData(Qt.UserRole, (name, phone, bal, pts))
            self._cust_list.addItem(item)

    def _select_customer(self, item):
        data = item.data(Qt.UserRole)
        if data:
            name, phone, bal, pts = data
            self._cust_name  = name
            self._cust_phone = phone
            self.lbl_cust_name.setText(f"👤  {name}")
            self.lbl_cust_phone.setText(f"📞  {phone}")
            self.lbl_cust_bal.setText(
                f"Balance: ₹{bal:.2f}" if bal > 0 else ""
            )
            self.cust_search.clear()
            self._cust_list.clear()

    # ─────────────────────────────────────────────────────
    #  TOTALS
    # ─────────────────────────────────────────────────────

    def _update_totals(self):
        items    = self.bill_table.get_items()
        subtotal = self.bill_table.get_subtotal()
        tax      = self.bill_table.get_tax_total()
        disc     = self.disc_spin.value()
        raw      = subtotal + tax - disc
        rounded  = round(raw)
        roff     = round(rounded - raw, 2)
        grand    = rounded

        self.lbl_subtotal.setText(f"₹ {subtotal:.2f}")
        self.lbl_tax.setText(f"₹ {tax:.2f}")
        self.lbl_disc_disp.setText(f"- ₹ {disc:.2f}")
        self.lbl_roundoff.setText(f"₹ {roff:+.2f}")
        self.lbl_grand.setText(f"₹ {grand:.2f}")

        count = len(items)
        self._item_count_lbl.setText(
            f"{count} item{'s' if count != 1 else ''}"
        )
        self._update_change()

    def _update_change(self):
        try:
            grand = float(self.lbl_grand.text().replace("₹","").strip())
        except Exception:
            grand = 0
        paid  = self.paid_spin.value()
        change = max(0, paid - grand)
        self.lbl_change.setText(f"Change  ₹ {change:.2f}")
        color = SUCCESS if change >= 0 else DANGER
        self.lbl_change.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{color};"
            f"background:{color}18;border-radius:7px;padding:6px 10px;"
        )

    def _grand_total(self):
        try:
            return float(self.lbl_grand.text().replace("₹","").strip())
        except Exception:
            return 0.0

    # ─────────────────────────────────────────────────────
    #  PAYMENT MODE
    # ─────────────────────────────────────────────────────

    def _set_payment_mode(self, mode):
        self._payment_mode = mode
        for m, b in self._pay_btns.items():
            b.setChecked(m == mode)
        self.upi_ref.setVisible(mode in ("Card","UPI","Split"))
        self.lbl_paid_label.setText(
            "Amount Received ₹" if mode == "Cash" else "Amount ₹"
        )
        if mode in ("Card","UPI"):
            self.paid_spin.setValue(self._grand_total())

    # ─────────────────────────────────────────────────────
    #  HOLD / RESUME
    # ─────────────────────────────────────────────────────

    def _hold_bill(self):
        items = self.bill_table.get_items()
        if not items:
            QMessageBox.information(self, "Hold", "Nothing to hold — bill is empty.")
            return
        snapshot = {
            "items":    items,
            "customer": self._cust_name,
            "phone":    self._cust_phone,
            "disc":     self.disc_spin.value(),
            "total":    self._grand_total(),
            "notes":    self.notes_edit.toPlainText(),
        }
        self._held_bills.append(snapshot)
        self._new_bill(show_msg=False)
        self._refresh_hold_badge()
        QMessageBox.information(self, "Bill Held",
            f"Bill #{len(self._held_bills)} held.\nStart a new bill.")

    def _resume_held(self):
        if not self._held_bills:
            QMessageBox.information(self, "No Held Bills",
                "No bills are currently on hold.")
            return
        dlg = HeldBillsDialog(self._held_bills, self)
        dlg.bill_selected.connect(self._restore_bill)
        dlg.exec_()

    def _restore_bill(self, idx):
        if idx >= len(self._held_bills):
            return
        snap = self._held_bills.pop(idx)
        self._new_bill(show_msg=False)
        for it in snap["items"]:
            self.bill_table.add_product(it)
        self._cust_name  = snap["customer"]
        self._cust_phone = snap["phone"]
        self.lbl_cust_name.setText(f"👤  {snap['customer']}")
        self.disc_spin.setValue(snap["disc"])
        self.notes_edit.setPlainText(snap["notes"])
        self._refresh_hold_badge()

    def _refresh_hold_badge(self):
        n = len(self._held_bills)
        self._hold_badge.setVisible(n > 0)
        self._hold_badge.setText(f"⏸  {n} held")

    # ─────────────────────────────────────────────────────
    #  SAVE / PRINT
    # ─────────────────────────────────────────────────────

    def _validate(self):
        if not self.bill_table.get_items():
            QMessageBox.warning(self, "Empty Bill",
                "Add at least one product before saving.")
            return False
        return True

    def _save_only(self):
        if not self._validate():
            return
        self._do_save()
        QMessageBox.information(self, "Saved", f"Invoice {self._invoice_id} saved.")
        self._new_bill()

    def _print_and_save(self):
        if not self._validate():
            return
        grand, change = self._do_save()
        html = self._build_receipt_html(grand, change)
        dlg  = PrintPreviewDialog(html, self)
        dlg.exec_()
        self._new_bill()

    def _do_save(self):
        items   = self.bill_table.get_items()
        disc    = self.disc_spin.value()
        paid    = self.paid_spin.value()
        notes   = self.notes_edit.toPlainText()
        grand, change = save_invoice(
            self.db_name,
            self._invoice_id,
            self._cust_name,
            self._cust_phone,
            items,
            disc,
            0.0,   # round_off (already baked into grand)
            self._payment_mode,
            paid,
            notes,
            self.current_user,
        )
        return grand, change

    # ─────────────────────────────────────────────────────
    #  NEW BILL RESET
    # ─────────────────────────────────────────────────────

    def _new_bill(self, show_msg=True):
        self.bill_table.clear_bill()
        self.disc_spin.setValue(0)
        self.paid_spin.setValue(0)
        self.notes_edit.clear()
        self.cust_search.clear()
        self._cust_list.clear()
        self._cust_name  = "Walk-in"
        self._cust_phone = ""
        self.lbl_cust_name.setText("👤  Walk-in Customer")
        self.lbl_cust_phone.setText("")
        self.lbl_cust_bal.setText("")
        self.upi_ref.clear()
        self._set_payment_mode("Cash")
        self._invoice_id = get_next_invoice_id(self.db_name)
        self.lbl_inv_id.setText(self._invoice_id)
        self._update_totals()
        self.product_search.setFocus()

    # ─────────────────────────────────────────────────────
    #  RECEIPT HTML (thermal 80 mm style)
    # ─────────────────────────────────────────────────────

    def _build_receipt_html(self, grand, change):
        co   = self._company
        name = co.get("company_name", self.company_name)
        addr = co.get("address","")
        phone= co.get("phone","")
        gst  = co.get("gst","")
        foot = co.get("footer","")
        now  = datetime.now().strftime("%d-%m-%Y  %H:%M")
        items= self.bill_table.get_items()

        rows = ""
        for it in items:
            total = it["price"] * it["qty"]
            rows += (
                f"<tr>"
                f"<td style='padding:3px 2px'>{it['name']}</td>"
                f"<td align='center'>{it['qty']}</td>"
                f"<td align='right'>₹{it['price']:.2f}</td>"
                f"<td align='right'>₹{total:.2f}</td>"
                f"</tr>"
            )

        subtotal = self.bill_table.get_subtotal()
        tax      = self.bill_table.get_tax_total()
        disc     = self.disc_spin.value()
        paid     = self.paid_spin.value()

        gst_row = f"<tr><td>GST</td><td colspan='3' align='right'>₹{tax:.2f}</td></tr>" if tax > 0 else ""
        disc_row= f"<tr><td>Discount</td><td colspan='3' align='right'>-₹{disc:.2f}</td></tr>" if disc > 0 else ""
        chng_row= f"<tr><td><b>Change</b></td><td colspan='3' align='right'><b>₹{change:.2f}</b></td></tr>" if change > 0 else ""

        html = f"""
        <html><body style='font-family:Courier New;font-size:12px;
               width:280px;margin:0 auto;'>
          <div align='center'>
            <h2 style='margin:4px 0'>{name}</h2>
            <div>{addr}</div>
            <div>📞 {phone}</div>
            {"<div>GST: "+gst+"</div>" if gst else ""}
          </div>
          <hr/>
          <div>Invoice: <b>{self._invoice_id}</b></div>
          <div>Date: {now}</div>
          <div>Customer: {self._cust_name}</div>
          <hr/>
          <table width='100%' cellspacing='0'>
            <tr style='border-bottom:1px solid #000'>
              <th align='left'>Item</th>
              <th>Qty</th><th>Rate</th><th>Amt</th>
            </tr>
            {rows}
            <tr><td colspan='4'><hr/></td></tr>
            <tr><td>Subtotal</td>
                <td colspan='3' align='right'>₹{subtotal:.2f}</td></tr>
            {gst_row}
            {disc_row}
            <tr><td colspan='4'><hr/></td></tr>
            <tr><td><b>TOTAL</b></td>
                <td colspan='3' align='right'><b>₹{grand:.2f}</b></td></tr>
            <tr><td>Paid ({self._payment_mode})</td>
                <td colspan='3' align='right'>₹{paid:.2f}</td></tr>
            {chng_row}
          </table>
          <hr/>
          <div align='center' style='font-size:11px'>
            {foot if foot else "Thank you for shopping with us!"}
          </div>
          <div align='center' style='font-size:10px;color:gray'>
            Powered by Evo Aura
          </div>
        </body></html>
        """
        return html


# ─────────────────────────────────────────────────────────
#  STANDALONE TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import glob
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    db_files = glob.glob("*.db")
    DB = db_files[0] if db_files else "evo_aura.db"

    company_name = "Evo Aura"
    try:
        from new_claude import load_company_info as _lci, init_db
        init_db(DB)
        info = _lci(DB)
        if info.get("company_name"):
            company_name = info["company_name"]
    except Exception:
        pass

    win = BillingPage(DB, company_name=company_name, current_user="Admin")
    win.setWindowTitle(f"Billing — {company_name}")
    win.resize(1280, 800)
    win.show()
    sys.exit(app.exec_())