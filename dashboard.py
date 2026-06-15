"""
dashboard.py  —  Evo Aura  •  Professional Dashboard
=====================================================
Standalone version — connect to new_claude.py later.
Run directly:  python dashboard.py
"""

import sys
import sqlite3
from datetime import datetime, date, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QStackedWidget,
    QSizePolicy, QInputDialog, QLineEdit,
    QMessageBox, QApplication
)
from PyQt5.QtGui  import QFont, QColor, QPainter, QBrush
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve


# ─────────────────────────────────────────────────────────────
#  DESIGN TOKENS
# ─────────────────────────────────────────────────────────────

C_PRIMARY    = "#1a7fe8"
C_PRIMARY_D  = "#1565c0"
C_PRIMARY_L  = "#eef5ff"
C_ACCENT     = "#00c896"
C_WARN       = "#f59e0b"
C_DANGER     = "#ef4444"
C_SIDEBAR    = "#0f172a"
C_SIDEBAR_H  = "#1e293b"
C_BG         = "#f1f5f9"
C_CARD       = "#ffffff"
C_BORDER     = "#e2e8f0"
C_TEXT       = "#1e293b"
C_TEXT_MUTED = "#64748b"

FONT_BODY = "Segoe UI"
FONT_MONO = "Consolas"

SIDEBAR_EXPANDED  = 300
SIDEBAR_COLLAPSED = 70

_SECTION_ICONS = {
    "Sales":     "🧾",
    "Inventory": "📦",
    "Customers": "👥",
    "Finance":   "💰",
    "Reports":   "📊",
    "Settings":  "⚙️",
}

NAV_ITEMS = [
    ("", [
        ("\U0001f3e0", "Dashboard",       "home"),
    ]),
    ("Sales", [
        ("\U0001f9fe", "New Sale",         "sale"),
        ("\U0001f501", "Returns",          "returns"),
        ("\U0001f4cb", "Bill View",        "bill_view"),
    ]),
    ("Inventory", [
        ("\U0001f4e6", "Products",         "products"),
        ("\U0001f6d2", "Purchase Orders",  "purchase_orders"),
        ("\U0001f69a", "Suppliers",        "suppliers"),
        ("\u26a0\ufe0f", "Low Stock",      "low_stock"),
    ]),
    ("Customers", [
        ("\U0001f465", "Customers",        "customers"),
        ("\U0001f4b3", "Credit Mgmt",      "credit"),
        ("\U0001f31f", "Loyalty",          "loyalty"),
    ]),
    ("Finance", [
        ("\U0001f4b0", "P & L Summary",    "pl_summary"),
        ("\U0001f4b8", "Expense Tracking", "expenses"),
        ("\U0001f9fe", "GST Breakdown",    "gst"),
        ("\U0001f4c8", "Cash Flow",        "cashflow"),
    ]),
    ("Reports", [
        ("\U0001f4ca", "Day Book",         "day_book"),
        ("\U0001f4d1", "Stock Report",     "stock_report"),
        ("\U0001f4c9", "Trial Balance",    "trial_balance"),
        ("\U0001f4e4", "Export",           "export"),
    ]),
    ("Settings", [
        ("\U0001f3e2", "Company",          "company_settings"),
        ("\U0001f464", "Users & Roles",    "users"),
        ("\U0001f512", "Security",         "security"),
        ("\U0001f5c3\ufe0f", "Audit Log",  "audit_log"),
    ]),
]

PAGE_META = {
    "home":             ("Dashboard",          "🏠", ""),
    "sale":             ("New Sale",           "🧾", "Create a new sales invoice"),
    "returns":          ("Returns",            "🔁", "Process product returns & credit notes"),
    "bill_view":        ("Bill View",          "📋", "Browse and search all invoices"),
    "products":         ("Products",           "📦", "Manage your product catalogue"),
    "purchase_orders":  ("Purchase Orders",    "🛒", "Raise and track supplier POs"),
    "suppliers":        ("Suppliers",          "🚚", "Vendor list and ledger"),
    "low_stock":        ("Low Stock Alerts",   "⚠️",  "Products below reorder level"),
    "customers":        ("Customers",          "👥", "Customer ledger & history"),
    "credit":           ("Credit Management",  "💳", "Credit limits & outstanding dues"),
    "loyalty":          ("Loyalty Program",    "🌟", "Reward frequent buyers"),
    "pl_summary":       ("P & L Summary",      "💰", "Revenue vs Expenses overview"),
    "expenses":         ("Expense Tracking",   "💸", "Log and categorise business expenses"),
    "gst":              ("GST Breakdown",      "🧾", "CGST / SGST / IGST per invoice"),
    "cashflow":         ("Cash Flow Timeline", "📈", "Monthly cash in / out"),
    "day_book":         ("Day Book",           "📊", "Daily cash book summary"),
    "stock_report":     ("Stock Valuation",    "📑", "Current inventory value"),
    "trial_balance":    ("Trial Balance",      "📉", "Debit / Credit ledger"),
    "export":           ("Export Reports",     "📤", "Excel / Tally export for all reports"),
    "company_settings": ("Company Settings",   "🏢", ""),
    "users":            ("Users & Roles",      "👤", "Staff accounts, roles, permissions"),
    "security":         ("Security",           "🔒", "2FA & audit trail"),
    "audit_log":        ("Audit Log",          "🗃️", "Who changed what and when"),
}


# ─────────────────────────────────────────────────────────────
#  STUB HELPERS  (replaced when connected to new_claude.py)
# ─────────────────────────────────────────────────────────────

def load_company_info(db: str) -> dict:
    """
    Standalone fallback — tries company_info first (new_claude schema),
    then company_settings, returns safe defaults if neither exists.
    """
    queries = [
        ("SELECT logo, company_name, phone, address, gst, footer "
         "FROM company_info WHERE id=1",
         ["logo","company_name","phone","address","gst","footer"]),
        ("SELECT logo, company_name FROM company_settings LIMIT 1",
         ["logo","company_name"]),
    ]
    try:
        with sqlite3.connect(db) as c:
            for sql, cols in queries:
                try:
                    row = c.execute(sql).fetchone()
                    if row:
                        result = {k: (row[i] or "") for i, k in enumerate(cols)}
                        if "logo" not in result:
                            result["logo"] = b""
                        if not result.get("logo"):
                            result["logo"] = b""
                        return result
                except sqlite3.OperationalError:
                    continue
    except Exception:
        pass
    return {"company_name": "Evo Aura", "logo": b""}




def pixmap_from_blob(blob):
    from PyQt5.QtGui import QPixmap
    if not blob:
        return QPixmap()
    px = QPixmap()
    px.loadFromData(blob)
    return px


# ─────────────────────────────────────────────────────────────
#  LIVE STATS
# ─────────────────────────────────────────────────────────────

def _q(db, sql, params=()):
    try:
        with sqlite3.connect(db) as c:
            return c.execute(sql, params).fetchone()
    except Exception:
        return None


def load_dashboard_stats(db: str) -> dict:
    today       = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    yesterday   = (date.today() - timedelta(days=1)).isoformat()

    def safe(row, idx=0, default=0):
        return row[idx] if row and row[idx] is not None else default

    today_rev       = safe(_q(db, "SELECT SUM(grand_total) FROM invoices WHERE date(date)=?", (today,)))
    yest_rev        = safe(_q(db, "SELECT SUM(grand_total) FROM invoices WHERE date(date)=?", (yesterday,)))
    month_rev       = safe(_q(db, "SELECT SUM(grand_total) FROM invoices WHERE date(date)>=?", (month_start,)))
    today_inv       = safe(_q(db, "SELECT COUNT(*) FROM invoices WHERE date(date)=?", (today,)))
    total_inv       = safe(_q(db, "SELECT COUNT(*) FROM invoices"))
    total_products  = safe(_q(db, "SELECT COUNT(*) FROM products WHERE status='Active'"))
    low_stock_count = safe(_q(db,
        "SELECT COUNT(*) FROM products WHERE status='Active' AND stock<=reorder_level AND reorder_level>0"))
    out_of_stock    = safe(_q(db, "SELECT COUNT(*) FROM products WHERE status='Active' AND stock=0"))

    try:
        with sqlite3.connect(db) as c:
            recent = c.execute(
                "SELECT invoice_id, date, grand_total FROM invoices ORDER BY date DESC LIMIT 6"
            ).fetchall()
    except Exception:
        recent = []

    try:
        with sqlite3.connect(db) as c:
            top_products = c.execute(
                """SELECT ii.product_name, SUM(ii.quantity) as qty, SUM(ii.total) as rev
                   FROM invoice_items ii
                   JOIN invoices inv ON ii.invoice_id=inv.invoice_id
                   WHERE date(inv.date)=?
                   GROUP BY ii.product_name ORDER BY rev DESC LIMIT 5""",
                (today,)
            ).fetchall()
    except Exception:
        top_products = []

    trend = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        r = safe(_q(db, "SELECT SUM(grand_total) FROM invoices WHERE date(date)=?", (d,)))
        trend.append((d, float(r)))

    rev_delta_pct = ((today_rev - yest_rev) / yest_rev * 100) if yest_rev > 0 else 0.0

    return {
        "today_rev": float(today_rev), "month_rev": float(month_rev),
        "today_inv": int(today_inv),   "total_inv": int(total_inv),
        "total_products": int(total_products),
        "low_stock": int(low_stock_count), "out_of_stock": int(out_of_stock),
        "rev_delta_pct": rev_delta_pct,
        "recent_invoices": recent, "top_products": top_products, "trend": trend,
    }


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _lbl(text, size=13, bold=False, color=C_TEXT, align=Qt.AlignLeft):
    l = QLabel(text)
    l.setFont(QFont(FONT_BODY, size, QFont.Bold if bold else QFont.Normal))
    l.setStyleSheet(f"color:{color}; background:transparent;")
    l.setAlignment(align)
    return l


def _divider():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"background:{C_BORDER}; border:none; max-height:1px;")
    return f


def _clear_layout(lay):
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().setParent(None)
        elif item.layout():
            _clear_layout(item.layout())


# ─────────────────────────────────────────────────────────────
#  KPI CARD
# ─────────────────────────────────────────────────────────────

class KpiCard(QFrame):
    def __init__(self, icon, title, value, delta=None,
                 delta_positive=True, accent=C_PRIMARY):
        super().__init__()
        self.setObjectName("kpi")
        self.setFixedHeight(110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QFrame#kpi {{
                background:{C_CARD}; border:1px solid {C_BORDER};
                border-radius:14px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)

        il = QLabel(icon)
        il.setFixedSize(48, 48)
        il.setAlignment(Qt.AlignCenter)
        il.setStyleSheet(f"background:{accent}22; border-radius:12px; font-size:22px; color:{accent};")
        lay.addWidget(il)

        tc = QVBoxLayout()
        tc.setSpacing(2)
        t = QLabel(title)
        t.setFont(QFont(FONT_BODY, 11))
        t.setStyleSheet(f"color:{C_TEXT_MUTED}; background:transparent;")
        v = QLabel(str(value))
        v.setFont(QFont(FONT_BODY, 22, QFont.Bold))
        v.setStyleSheet(f"color:{C_TEXT}; background:transparent;")
        tc.addWidget(t)
        tc.addWidget(v)
        lay.addLayout(tc)
        lay.addStretch()

        if delta is not None:
            sign  = "▲" if delta_positive else "▼"
            col   = C_ACCENT if delta_positive else C_DANGER
            dl    = QLabel(f"{sign} {delta}")
            dl.setFont(QFont(FONT_BODY, 10, QFont.Bold))
            dl.setStyleSheet(f"background:{col}22; color:{col}; border-radius:8px; padding:3px 8px;")
            dc = QVBoxLayout()
            dc.addWidget(dl, alignment=Qt.AlignTop | Qt.AlignRight)
            dc.addStretch()
            lay.addLayout(dc)


# ─────────────────────────────────────────────────────────────
#  SPARK BAR
# ─────────────────────────────────────────────────────────────

class SparkBar(QWidget):
    def __init__(self, trend):
        super().__init__()
        self.trend = trend
        self.setFixedHeight(44)
        self.setMinimumWidth(140)

    def paintEvent(self, _):
        if not self.trend:
            return
        vals = [v for _, v in self.trend]
        mx   = max(vals) if max(vals) > 0 else 1
        p    = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, n = self.width(), self.height(), len(vals)
        bw = max(4, (w - (n - 1) * 3) // n)
        for i, v in enumerate(vals):
            bh  = max(4, int((v / mx) * (h - 6)))
            col = QColor(C_PRIMARY) if i < n - 1 else QColor(C_ACCENT)
            p.setBrush(QBrush(col))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(i * (bw + 3), h - bh, bw, bh, 3, 3)
        p.end()


# ─────────────────────────────────────────────────────────────
#  HOME PAGE
# ─────────────────────────────────────────────────────────────

class HomePage(QWidget):
    def __init__(self, db_name, company_name, logo_pixmap, username,
                 open_billing_cb, open_products_cb):
        super().__init__()
        self.db_name          = db_name
        self.open_billing_cb  = open_billing_cb
        self.open_products_cb = open_products_cb
        self.setStyleSheet(f"background:{C_BG};")

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self._root = QVBoxLayout(inner)
        self._root.setContentsMargins(28, 24, 28, 28)
        self._root.setSpacing(22)

        self._root.addWidget(self._build_banner(company_name, logo_pixmap, username))

        self._kpi_row = QHBoxLayout()
        self._kpi_row.setSpacing(14)
        self._root.addLayout(self._kpi_row)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        self._trend_card = self._build_trend_card()
        mid.addWidget(self._trend_card, 3)
        mid.addWidget(self._build_quick_actions(), 2)
        self._root.addLayout(mid)

        bot = QHBoxLayout()
        bot.setSpacing(14)
        self._recent_card = self._build_recent_card()
        bot.addWidget(self._recent_card, 3)
        self._top_card = self._build_top_products_card()
        bot.addWidget(self._top_card, 2)
        self._root.addLayout(bot)

        self._root.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(60_000)

    def _build_banner(self, company_name, logo_pixmap, username):
        banner = QFrame()
        banner.setFixedHeight(100)
        banner.setStyleSheet(f"""
            QFrame {{
                background   : qlineargradient(x1:0,y1:0,x2:1,y2:0,
                               stop:0 {C_PRIMARY}, stop:1 #0ea5e9);
                border-radius: 16px;
            }}
        """)
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(16)

        if logo_pixmap and not logo_pixmap.isNull():
            lbl = QLabel()
            lbl.setFixedSize(64, 64)
            lbl.setPixmap(logo_pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lbl.setStyleSheet("background:white; border-radius:10px; padding:3px;")
            lay.addWidget(lbl)

        col   = QVBoxLayout()
        col.setSpacing(2)
        hour  = datetime.now().hour
        greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        col.addWidget(_lbl(f"{greet}, {username} 👋", 11, color="#bfdbfe"))
        col.addWidget(_lbl(company_name, 20, bold=True, color="#ffffff"))
        col.addWidget(_lbl(datetime.now().strftime("%d %b %Y  •  %H:%M"), 10, color="#93c5fd"))
        lay.addLayout(col)
        lay.addStretch()

        self._clock = QLabel()
        self._clock.setFont(QFont(FONT_MONO, 24, QFont.Bold))
        self._clock.setStyleSheet("color:white; background:transparent;")
        lay.addWidget(self._clock)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()
        return banner

    def _tick_clock(self):
        self._clock.setText(datetime.now().strftime("%H:%M:%S"))

    def _build_trend_card(self):
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_CARD};border:1px solid {C_BORDER};border-radius:14px;}}")
        self._trend_layout = QVBoxLayout(card)
        self._trend_layout.setContentsMargins(20, 16, 20, 16)
        self._trend_layout.setSpacing(8)
        return card

    def _rebuild_trend(self, stats):
        lay = self._trend_layout
        _clear_layout(lay)
        hdr = QHBoxLayout()
        hdr.addWidget(_lbl("7-Day Revenue Trend", 13, bold=True))
        hdr.addStretch()
        hdr.addWidget(_lbl(f"₹ {sum(v for _,v in stats['trend']):,.0f}", 13, bold=True, color=C_PRIMARY))
        lay.addLayout(hdr)
        lay.addWidget(_divider())
        lay.addWidget(SparkBar(stats["trend"]))
        day_row = QHBoxLayout()
        day_row.setSpacing(0)
        for d, _ in stats["trend"]:
            try:
                name = datetime.strptime(d, "%Y-%m-%d").strftime("%a")
            except Exception:
                name = ""
            dl = QLabel(name)
            dl.setAlignment(Qt.AlignCenter)
            dl.setFont(QFont(FONT_BODY, 8))
            dl.setStyleSheet(f"color:{C_TEXT_MUTED}; background:transparent;")
            day_row.addWidget(dl)
        lay.addLayout(day_row)
        lay.addStretch()

    def _build_quick_actions(self):
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_CARD};border:1px solid {C_BORDER};border-radius:14px;}}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(_lbl("Quick Actions", 13, bold=True))
        lay.addWidget(_divider())
        for label, color, cb in [
            ("🧾  New Sale",       C_PRIMARY, self.open_billing_cb),
            ("📦  Add Product",    "#7c3aed",  self.open_products_cb),
            ("🔁  Process Return", C_WARN,     lambda: None),
            ("📊  View Reports",   C_ACCENT,   lambda: None),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton{{background:{color}18;color:{color};
                    border:1px solid {color}44;border-radius:8px;
                    font-size:13px;font-weight:600;text-align:left;padding:0 14px;}}
                QPushButton:hover{{background:{color}30;border:1px solid {color}88;}}
            """)
            btn.clicked.connect(cb)
            lay.addWidget(btn)
        lay.addStretch()
        return card

    def _build_recent_card(self):
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_CARD};border:1px solid {C_BORDER};border-radius:14px;}}")
        self._recent_layout = QVBoxLayout(card)
        self._recent_layout.setContentsMargins(20, 16, 20, 16)
        self._recent_layout.setSpacing(6)
        return card

    def _rebuild_recent(self, stats):
        lay = self._recent_layout
        _clear_layout(lay)
        hdr = QHBoxLayout()
        hdr.addWidget(_lbl("Recent Invoices", 13, bold=True))
        hdr.addStretch()
        hdr.addWidget(_lbl(f"Total: {stats['total_inv']}", 11, color=C_TEXT_MUTED))
        lay.addLayout(hdr)
        lay.addWidget(_divider())
        if not stats["recent_invoices"]:
            lay.addWidget(_lbl("No invoices yet.", 12, color=C_TEXT_MUTED, align=Qt.AlignCenter))
        else:
            hr = QHBoxLayout()
            for txt, s in [("Invoice", 2), ("Date", 2), ("Amount", 1)]:
                hr.addWidget(_lbl(txt, 10, bold=True, color=C_TEXT_MUTED), s)
            lay.addLayout(hr)
            for inv_id, dt, total in stats["recent_invoices"]:
                row = QFrame()
                row.setFixedHeight(36)
                row.setStyleSheet(f"""
                    QFrame{{background:transparent;border-radius:6px;}}
                    QFrame:hover{{background:{C_PRIMARY_L};}}
                """)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.setSpacing(0)
                try:
                    dt_fmt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S").strftime("%d %b %H:%M")
                except Exception:
                    dt_fmt = dt or ""
                id_l = _lbl(inv_id, 12, color=C_PRIMARY)
                dt_l = _lbl(dt_fmt, 11, color=C_TEXT_MUTED)
                am_l = _lbl(f"₹{float(total or 0):,.2f}", 12, bold=True)
                am_l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                rl.addWidget(id_l, 2)
                rl.addWidget(dt_l, 2)
                rl.addWidget(am_l, 1)
                lay.addWidget(row)
        lay.addStretch()

    def _build_top_products_card(self):
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_CARD};border:1px solid {C_BORDER};border-radius:14px;}}")
        self._top_layout = QVBoxLayout(card)
        self._top_layout.setContentsMargins(20, 16, 20, 16)
        self._top_layout.setSpacing(8)
        return card

    def _rebuild_top(self, stats):
        lay = self._top_layout
        _clear_layout(lay)
        lay.addWidget(_lbl("Top Products Today", 13, bold=True))
        lay.addWidget(_divider())
        if not stats["top_products"]:
            lay.addWidget(_lbl("No sales today yet.", 12, color=C_TEXT_MUTED, align=Qt.AlignCenter))
        else:
            colors  = [C_PRIMARY, C_ACCENT, C_WARN, "#a855f7", "#ec4899"]
            max_rev = stats["top_products"][0][2] or 1
            for i, (name, qty, rev) in enumerate(stats["top_products"], 1):
                rw = QWidget()
                rw.setStyleSheet("background:transparent;")
                rl = QVBoxLayout(rw)
                rl.setContentsMargins(0, 2, 0, 2)
                rl.setSpacing(3)
                tr = QHBoxLayout()
                tr.addWidget(_lbl(f"{i}. {name}", 12))
                tr.addStretch()
                tr.addWidget(_lbl(f"₹{rev:,.0f}", 12, bold=True, color=C_PRIMARY))
                rl.addLayout(tr)
                bg = QFrame()
                bg.setFixedHeight(4)
                bg.setStyleSheet("background:#e2e8f0; border-radius:2px;")
                rl.addWidget(bg)
                pct  = min(int((rev / max(max_rev, 1)) * 100), 100)
                fill = QFrame(bg)
                fill.setFixedHeight(4)
                fill.setStyleSheet(f"background:{colors[(i-1)%len(colors)]}; border-radius:2px;")
                fill.setFixedWidth(max(4, pct * 2))
                lay.addWidget(rw)
        lay.addStretch()

    def _rebuild_kpis(self, stats):
        lay = self._kpi_row
        _clear_layout(lay)
        delta_str = f"{abs(stats['rev_delta_pct']):.1f}% vs yesterday"
        pos       = stats["rev_delta_pct"] >= 0
        for icon, title, val, delta, dp, acc in [
            ("💰", "Today's Revenue",    f"₹{stats['today_rev']:,.0f}", delta_str, pos, C_PRIMARY),
            ("📅", "Month Revenue",      f"₹{stats['month_rev']:,.0f}", None, True, C_ACCENT),
            ("🧾", "Today's Invoices",   str(stats["today_inv"]), f"{stats['total_inv']} total", True, "#7c3aed"),
            ("📦", "Active Products",    str(stats["total_products"]), None, True, "#0ea5e9"),
            ("⚠️", "Low / Out of Stock", f"{stats['low_stock']} / {stats['out_of_stock']}",
             "needs attention" if stats["low_stock"] > 0 else "all good",
             stats["low_stock"] == 0, C_WARN),
        ]:
            lay.addWidget(KpiCard(icon, title, val, delta, dp, acc))

    def refresh(self):
        stats = load_dashboard_stats(self.db_name)
        self._rebuild_kpis(stats)
        self._rebuild_trend(stats)
        self._rebuild_recent(stats)
        self._rebuild_top(stats)


# ─────────────────────────────────────────────────────────────
#  COMING SOON PAGE
# ─────────────────────────────────────────────────────────────

class ComingSoonPage(QWidget):
    def __init__(self, icon, title, subtitle=""):
        super().__init__()
        self.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)

        e = QLabel(icon)
        e.setFont(QFont(FONT_BODY, 52))
        e.setAlignment(Qt.AlignCenter)
        e.setStyleSheet("background:transparent;")
        lay.addWidget(e)

        lay.addWidget(_lbl(title, 22, bold=True, align=Qt.AlignCenter))
        if subtitle:
            lay.addWidget(_lbl(subtitle, 13, color=C_TEXT_MUTED, align=Qt.AlignCenter))

        badge = QLabel("🚀  Coming Soon")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"""
            background:{C_PRIMARY}18; color:{C_PRIMARY};
            border:1px solid {C_PRIMARY}44; border-radius:20px;
            padding:6px 20px; font-size:13px; font-weight:700;
        """)
        lay.addWidget(badge, alignment=Qt.AlignCenter)


# ─────────────────────────────────────────────────────────────
#  NAV BUTTON
# ─────────────────────────────────────────────────────────────

class _NavButton(QPushButton):
    def __init__(self, icon, label, active=False):
        super().__init__()
        self._icon  = icon
        self._label = label
        self.setCheckable(True)
        self.setChecked(active)
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QPushButton {{
                text-align    : left;
                padding       : 0 14px 0 42px;
                border        : none;
                border-radius : 8px;
                font-size     : 13px;
                font-weight   : 400;
                color         : #94a3b8;
                background    : transparent;
            }}
            QPushButton:hover {{
                background : #1e293b;
                color      : #e2e8f0;
            }}
            QPushButton:checked {{
                background   : {C_PRIMARY}22;
                color        : {C_PRIMARY};
                font-weight  : 600;
                border-left  : 3px solid {C_PRIMARY};
                padding-left : 39px;
            }}
        """)
        self.set_expanded(True)

    def set_expanded(self, expanded: bool):
        if expanded:
            self.setText(f"  {self._icon}   {self._label}")
            self.setToolTip("")
        else:
            self.setText(f"  {self._icon}")
            self.setToolTip(self._label)


# ─────────────────────────────────────────────────────────────
#  FLYOUT POPUP
# ─────────────────────────────────────────────────────────────

class _FlyoutMenu(QFrame):
    """
    Floating panel shown to the right of a collapsed sidebar
    group icon on hover. Fixes:
      - QPoint now imported at top level
      - active state uses a SINGLE global key, not per-button setChecked
    """

    def __init__(self, parent_window, title, items, on_nav,
                 get_active_key_fn):
        # parent_window = top-level QWidget so flyout floats above everything
        super().__init__(parent_window,
                         Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._on_nav          = on_nav
        self._get_active_key  = get_active_key_fn   # callable → current active key
        self._item_buttons    = {}                   # key → QPushButton

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(150)
        self._hide_timer.timeout.connect(self.hide)

        self.setStyleSheet("""
            QFrame {
                background    : #1a2744;
                border        : 1px solid #2d3f5e;
                border-radius : 12px;
            }
        """)
        self.setFixedWidth(220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(2)

        if title:
            tl = QLabel(f"  {title.upper()}")
            tl.setFont(QFont(FONT_BODY, 9, QFont.Bold))
            tl.setStyleSheet(
                "color:#64748b; background:transparent; "
                "padding:2px 8px 6px 8px; letter-spacing:1.2px;")
            lay.addWidget(tl)
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background:#2d3f5e; border:none; margin:0 4px 4px 4px;")
            lay.addWidget(sep)

        for icon, label, key in items:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align    : left;
                    padding       : 0 12px;
                    border        : none;
                    border-radius : 8px;
                    font-size     : 13px;
                    font-weight   : 400;
                    color         : #94a3b8;
                    background    : transparent;
                }}
                QPushButton:hover {{
                    background : #243352;
                    color      : #e2e8f0;
                }}
                QPushButton:checked {{
                    background  : {C_PRIMARY}22;
                    color       : {C_PRIMARY};
                    font-weight : 600;
                    border-left : 3px solid {C_PRIMARY};
                    padding-left: 9px;
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._on_item(k))
            lay.addWidget(btn)
            self._item_buttons[key] = btn

    def _on_item(self, key):
        self.hide()
        self._on_nav(key)

    def refresh_active(self):
        """Sync checked state with the real global active key."""
        active = self._get_active_key()
        for key, btn in self._item_buttons.items():
            btn.setChecked(key == active)

    def show_beside(self, trigger_widget: QWidget):
        self._hide_timer.stop()
        self.refresh_active()                              # ← fix double-highlight
        gp = trigger_widget.mapToGlobal(QPoint(0, 0))     # QPoint now at top-level
        self.move(gp.x() + trigger_widget.width() + 4,
                  gp.y() - 10)
        self.adjustSize()
        self.raise_()
        self.show()

    def keep_open(self):
        self._hide_timer.stop()

    def schedule_hide(self):
        self._hide_timer.start()

    def enterEvent(self, e):
        self._hide_timer.stop()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hide_timer.start()
        super().leaveEvent(e)


# ─────────────────────────────────────────────────────────────
#  NAV GROUP
# ─────────────────────────────────────────────────────────────

class NavGroupWidget(QWidget):
    def __init__(self, title, items, buttons_dict, on_nav,
                 active_key, start_expanded=False, get_active_key_fn=None):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self._group_collapsed  = not start_expanded
        self._sidebar_expanded = True
        self._title            = title
        self._items            = items
        self._on_nav           = on_nav
        self._buttons_dict     = buttons_dict
        self._get_active_key   = get_active_key_fn or (lambda: active_key)
        self._flyout           = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Section header ────────────────────────────────────
        if title:
            self._hdr_btn = QPushButton()
            self._hdr_btn.setFixedHeight(42)
            self._hdr_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._hdr_btn.setCursor(Qt.PointingHandCursor)
            self._hdr_btn.setStyleSheet(f"""
                QPushButton {{
                    text-align    : left;
                    padding       : 0 14px;
                    border        : none;
                    border-radius : 8px;
                    font-size     : 13px;
                    font-weight   : 600;
                    color         : #cbd5e1;
                    background    : transparent;
                }}
                QPushButton:hover {{
                    background : #1e293b;
                    color      : #f1f5f9;
                }}
            """)
            self._hdr_btn.clicked.connect(self._toggle_group)
            self._hdr_btn.installEventFilter(self)
            root.addWidget(self._hdr_btn)
        else:
            self._hdr_btn = None

        # ── Items container ───────────────────────────────────
        self._items_widget = QWidget()
        self._items_widget.setStyleSheet("background:transparent;")
        items_lay = QVBoxLayout(self._items_widget)
        items_lay.setContentsMargins(0, 0, 0, 4)
        items_lay.setSpacing(1)

        for icon, label, key in items:
            btn = _NavButton(icon, label, active=(key == active_key))
            btn.clicked.connect(lambda _, k=key: on_nav(k))
            items_lay.addWidget(btn)
            buttons_dict[key] = btn

        root.addWidget(self._items_widget)

        if title:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background:#1e293b; border:none; margin:4px 8px;")
            root.addWidget(sep)

        self._items_widget.setVisible(start_expanded)
        self._update_header(expanded=start_expanded)

    # ── Flyout (lazy, created once) ───────────────────────────

    def _get_flyout(self):
        if self._flyout is None:
            # walk up to top-level window so flyout is truly floating
            win = self.window()
            self._flyout = _FlyoutMenu(
                parent_window    = win,
                title            = self._title,
                items            = self._items,
                on_nav           = self._on_nav,
                get_active_key_fn= self._get_active_key,
            )
        return self._flyout

    # ── Event filter — hover triggers flyout in collapsed mode ─

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj is self._hdr_btn and not self._sidebar_expanded:
            if event.type() == QEvent.Enter:
                self._get_flyout().show_beside(self._hdr_btn)
            elif event.type() == QEvent.Leave:
                self._get_flyout().schedule_hide()
        return super().eventFilter(obj, event)

    def _toggle_group(self):
        if not self._sidebar_expanded:
            return
        self._group_collapsed = not self._group_collapsed
        self._items_widget.setVisible(not self._group_collapsed)
        self._update_header(expanded=not self._group_collapsed)

    def _update_header(self, expanded: bool):
        if self._hdr_btn is None:
            return
        sec_icon = _SECTION_ICONS.get(self._title, "•")
        if self._sidebar_expanded:
            chevron = "▾" if expanded else "▸"
            self._hdr_btn.setText(f"  {sec_icon}   {self._title}   {chevron}")
        else:
            self._hdr_btn.setText(f"  {sec_icon}")

    def set_sidebar_expanded(self, sidebar_expanded: bool):
        self._sidebar_expanded = sidebar_expanded
        if self._hdr_btn:
            self._update_header(expanded=not self._group_collapsed)
        # collapsed → hide child items (only section icon shows)
        # expanded  → restore group's own collapsed/expanded state
        self._items_widget.setVisible(
            False if not sidebar_expanded else not self._group_collapsed)
        if self._flyout:
            self._flyout.hide()

    def update_flyout_active(self):
        """Called by Sidebar.set_active() to refresh flyout checked state."""
        if self._flyout:
            self._flyout.refresh_active()


# ─────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────

class Sidebar(QFrame):

    EXPANDED_W  = SIDEBAR_EXPANDED
    COLLAPSED_W = SIDEBAR_COLLAPSED

    def __init__(self, on_navigate):
        super().__init__()
        self.on_navigate  = on_navigate
        self._buttons     = {}   # key → _NavButton  (expanded sidebar)
        self._groups      = []
        self._active_key  = "home"
        self._is_expanded = True

        self.setFixedWidth(self.EXPANDED_W)
        self.setStyleSheet(f"background:{C_SIDEBAR}; border:none;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 16, 10, 16)
        outer.setSpacing(0)

        # ── Brand ─────────────────────────────────────────────
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(8, 0, 0, 0)
        brand_row.setSpacing(10)
        self._brand_icon = QLabel("\u2736")
        self._brand_icon.setStyleSheet(
            f"color:{C_PRIMARY}; font-size:24px; background:transparent;")
        self._brand_name = QLabel("Evo Aura")
        self._brand_name.setFont(QFont(FONT_BODY, 15, QFont.Bold))
        self._brand_name.setStyleSheet("color:white; background:transparent;")
        brand_row.addWidget(self._brand_icon)
        brand_row.addWidget(self._brand_name)
        brand_row.addStretch()
        outer.addLayout(brand_row)
        outer.addSpacing(6)

        brand_sep = QFrame()
        brand_sep.setFixedHeight(1)
        brand_sep.setStyleSheet("background:#1e293b; border:none; margin:6px 0;")
        outer.addWidget(brand_sep)
        outer.addSpacing(6)

        # ── Scrollable nav ─────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent; border:none;")

        nav_widget = QWidget()
        nav_widget.setStyleSheet("background:transparent;")
        nav_lay = QVBoxLayout(nav_widget)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(2)
        nav_lay.setAlignment(Qt.AlignTop)

        for i, (section_title, items) in enumerate(NAV_ITEMS):
            group = NavGroupWidget(
                title            = section_title,
                items            = items,
                buttons_dict     = self._buttons,
                on_nav           = self._nav,
                active_key       = "home",
                start_expanded   = (i == 0),
                get_active_key_fn= self._get_active_key,
            )
            nav_lay.addWidget(group)
            self._groups.append(group)

        scroll.setWidget(nav_widget)
        outer.addWidget(scroll, 1)

        # ── Bottom ─────────────────────────────────────────────
        outer.addWidget(_divider())
        outer.addSpacing(8)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(6, 0, 6, 0)
        bottom_row.setSpacing(10)
        avatar = QLabel("\u2736")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background:{C_PRIMARY}33; border-radius:17px;
            font-size:16px; color:{C_PRIMARY};
        """)
        self._ver_lbl = QLabel("Evo Aura  v1.0")
        self._ver_lbl.setFont(QFont(FONT_BODY, 9))
        self._ver_lbl.setStyleSheet("color:#475569; background:transparent;")
        bottom_row.addWidget(avatar)
        bottom_row.addWidget(self._ver_lbl)
        bottom_row.addStretch()
        outer.addLayout(bottom_row)

        QTimer.singleShot(0, lambda: self._apply_button_mode(True))

    def _get_active_key(self) -> str:
        return self._active_key

    # ── Toggle ────────────────────────────────────────────────

    def toggle(self):
        self._is_expanded = not self._is_expanded
        target = self.EXPANDED_W if self._is_expanded else self.COLLAPSED_W
        for prop in (b"minimumWidth", b"maximumWidth"):
            anim = QPropertyAnimation(self, prop, self)
            anim.setDuration(240)
            anim.setStartValue(self.width())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QPropertyAnimation.DeleteWhenStopped)
        QTimer.singleShot(40, lambda: self._apply_button_mode(self._is_expanded))

    def _apply_button_mode(self, expanded: bool):
        self._brand_name.setVisible(expanded)
        self._ver_lbl.setVisible(expanded)
        for btn in self._buttons.values():
            btn.set_expanded(expanded)
        for grp in self._groups:
            grp.set_sidebar_expanded(expanded)

    # ── Navigation ────────────────────────────────────────────

    def _nav(self, key):
        # deactivate old, activate new — ONE button only
        if self._active_key in self._buttons:
            self._buttons[self._active_key].setChecked(False)
        self._active_key = key
        if key in self._buttons:
            self._buttons[key].setChecked(True)
        # refresh any open flyout so it also shows the right active state
        for grp in self._groups:
            grp.update_flyout_active()
        self.on_navigate(key)

    def set_active(self, key: str):
        """Update highlight WITHOUT triggering navigation (avoids recursion)."""
        if self._active_key in self._buttons:
            self._buttons[self._active_key].setChecked(False)
        self._active_key = key
        if key in self._buttons:
            self._buttons[key].setChecked(True)
        for grp in self._groups:
            grp.update_flyout_active()


# ─────────────────────────────────────────────────────────────
#  TOP BAR
# ─────────────────────────────────────────────────────────────

class TopBar(QFrame):
    def __init__(self, username, on_settings, on_user_security,
                 on_logout, on_toggle=None):
        super().__init__()
        self.setFixedHeight(60)
        self.setStyleSheet(f"""
            QFrame {{
                background    : {C_CARD};
                border-bottom : 1px solid {C_BORDER};
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 20, 0)
        lay.setSpacing(10)

        toggle_btn = QPushButton("☰")
        toggle_btn.setFixedSize(38, 38)
        toggle_btn.setCursor(Qt.PointingHandCursor)
        toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_BG}; border:1px solid {C_BORDER};
                border-radius:10px; font-size:18px; color:{C_TEXT};
            }}
            QPushButton:hover {{
                background:{C_PRIMARY_L}; color:{C_PRIMARY};
                border-color:{C_PRIMARY};
            }}
            QPushButton:pressed {{ background:{C_PRIMARY}22; }}
        """)
        toggle_btn.setToolTip("Toggle sidebar  (Ctrl+\\)")
        if on_toggle:
            toggle_btn.clicked.connect(on_toggle)
        lay.addWidget(toggle_btn)
        lay.addSpacing(4)

        self.page_title = QLabel("Dashboard")
        self.page_title.setFont(QFont(FONT_BODY, 15, QFont.Bold))
        self.page_title.setStyleSheet(f"color:{C_TEXT}; background:transparent;")
        lay.addWidget(self.page_title)
        lay.addStretch()

        hint = QLabel("🔍  Quick search  (coming soon)")
        hint.setStyleSheet(f"""
            color:{C_TEXT_MUTED}; background:{C_BG};
            border:1px solid {C_BORDER}; border-radius:8px;
            padding:4px 14px; font-size:12px;
        """)
        hint.setFixedHeight(32)
        hint.setMinimumWidth(240)
        lay.addWidget(hint)
        lay.addSpacing(8)

        user_btn = QPushButton(f"👤  {username}")
        user_btn.setCursor(Qt.PointingHandCursor)
        user_btn.setFixedHeight(32)
        user_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                font-size:13px; color:{C_TEXT}; padding:0 8px;
            }}
            QPushButton:hover {{
                background:{C_PRIMARY_L}; border-radius:8px; color:{C_PRIMARY};
            }}
        """)
        user_btn.clicked.connect(on_user_security)
        lay.addWidget(user_btn)

        set_btn = QPushButton("⚙️")
        set_btn.setFixedSize(32, 32)
        set_btn.setCursor(Qt.PointingHandCursor)
        set_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_BG}; border:1px solid {C_BORDER};
                border-radius:8px; font-size:15px; color:{C_TEXT_MUTED};
            }}
            QPushButton:hover {{ background:{C_PRIMARY_L}; color:{C_PRIMARY}; }}
        """)
        set_btn.setToolTip("Company Settings")
        set_btn.clicked.connect(on_settings)
        lay.addWidget(set_btn)

        lg_btn = QPushButton("Logout")
        lg_btn.setFixedSize(72, 32)
        lg_btn.setCursor(Qt.PointingHandCursor)
        lg_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_DANGER}; color:white; border:none;
                border-radius:8px; font-size:12px; font-weight:700;
            }}
            QPushButton:hover {{ background:#dc2626; }}
        """)
        lg_btn.clicked.connect(on_logout)
        lay.addWidget(lg_btn)

    def set_title(self, title: str):
        self.page_title.setText(title)


# ─────────────────────────────────────────────────────────────
#  DASHBOARD  (main window widget)
# ─────────────────────────────────────────────────────────────

class Dashboard(QWidget):
    """
    Standalone — run directly or import from new_claude.py.
    To connect new_claude helpers, replace the stub functions
    load_company_info / pixmap_from_blob at the top of this file.
    """

    def __init__(self, db_name: str, username: str = "User"):
        super().__init__()
        self.db_name  = db_name
        self.username = username

        # ── Try to import real helpers; fall back to stubs ────
        try:
            from new_claude import (
                load_company_info   as _lci,
                pixmap_from_blob    as _pfb,
                CompanySettings     as _CS,
                get_user_otp_data   as _guod,
                verify_otp          as _votp,
                generate_qr         as _gqr,
                QRDisplay           as _QRD,
            )
            self._load_company_info = _lci
            self._pixmap_from_blob  = _pfb
            self._CompanySettings   = _CS
            self._get_user_otp_data = _guod
            self._verify_otp        = _votp
            self._generate_qr       = _gqr
            self._QRDisplay         = _QRD
        except ImportError:
            self._load_company_info = load_company_info
            self._pixmap_from_blob  = pixmap_from_blob
            self._CompanySettings   = None
            self._get_user_otp_data = lambda db, u: (None, [])
            self._verify_otp        = lambda s, o: False
            self._generate_qr       = lambda s, u: ""
            self._QRDisplay         = None

        try:
            company = self._load_company_info(db_name)
        except Exception:
            company = {}
        company_name = company.get("company_name") or "Evo Aura"
        logo_pixmap  = self._pixmap_from_blob(company.get("logo") or b"")


        self.setWindowTitle("Evo Aura — " + company_name)
        self.showMaximized()
        self.setStyleSheet(f"background:{C_BG};")

        # ── Layout: sidebar | content ─────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(on_navigate=self._navigate)
        root.addWidget(self.sidebar)

        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(0)

        self.topbar = TopBar(
            username         = username,
            on_settings      = self._open_settings,
            on_user_security = lambda: self._open_user_security(username),
            on_logout        = self.close,
            on_toggle        = self.sidebar.toggle,
        )
        content_col.addWidget(self.topbar)

        self.stack = QStackedWidget()
        content_col.addWidget(self.stack, 1)
        root.addLayout(content_col, 1)

        # ── Pages ─────────────────────────────────────────────
        self._pages = {}

        home = HomePage(
            db_name          = db_name,
            company_name     = company_name,
            logo_pixmap      = logo_pixmap,
            username         = username,
            open_billing_cb  = lambda: self._navigate("sale"),
            open_products_cb = lambda: self._navigate("products"),
        )
        self._register_page("home", home)

        # lazy placeholders for real pages
        self._pages["sale"]     = None
        self._pages["products"] = None

        # all remaining pages → Coming Soon
        for key, meta in PAGE_META.items():
            if key not in self._pages:
                self._register_page(key, ComingSoonPage(meta[1], meta[0], meta[2]))

        self._navigate("home")

    # ── Page registration ─────────────────────────────────────

    def _register_page(self, key: str, widget: QWidget):
        self._pages[key] = widget
        if widget is not None:
            self.stack.addWidget(widget)

    # ── Navigation ────────────────────────────────────────────

    def _navigate(self, key: str):
        if key == "sale":
            self._open_billing()
            return
        if key == "products":
            self._open_products()
            return
        if key == "company_settings":
            self._open_settings()
            return

        page = self._pages.get(key)
        if page is None:
            return

        self.stack.setCurrentWidget(page)
        meta = PAGE_META.get(key, (key.replace("_", " ").title(), "", ""))
        self.topbar.set_title(meta[0])
        self.sidebar.set_active(key)

        if key == "home" and isinstance(page, HomePage):
            page.refresh()

    # ── Billing page ──────────────────────────────────────────

    def _open_billing(self):
        try:
            from billing_page import BillingPage
        except ImportError:
            QMessageBox.information(
                self, "Coming Soon",
                "The Billing module (billing_page.py) is not yet installed.\n"
                "Please add billing_page.py to the project folder."
            )
            self.sidebar.set_active("home")
            return

        existing = self._pages.get("sale")
        if existing is not None:
            self.stack.setCurrentWidget(existing)
            self.topbar.set_title("New Sale")
            self.sidebar.set_active("sale")
            return

        company = self._load_company_info(self.db_name)
        page    = BillingPage(
            self.db_name,
            company_name = company.get("company_name", ""),
            on_back      = lambda: self._navigate("home"),
        )
        old = self._pages.get("sale")
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()

        self._pages["sale"] = page
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)
        self.topbar.set_title("New Sale")
        self.sidebar.set_active("sale")

    # ── Products page ─────────────────────────────────────────

    def _open_products(self):
        try:
            from product_page import ProductPage
        except ImportError:
            QMessageBox.information(
                self, "Coming Soon",
                "The Products module (product_page.py) is not yet installed.\n"
                "Please add product_page.py to the project folder."
            )
            self.sidebar.set_active("home")
            return

        existing = self._pages.get("products")
        if existing is not None:
            self.stack.setCurrentWidget(existing)
            try:
                existing.list_widget.refresh()
            except Exception:
                pass
            self.topbar.set_title("Products")
            self.sidebar.set_active("products")
            return

        self.topbar.set_title("Products")
        self.sidebar.set_active("products")
        QApplication.processEvents()

        company = self._load_company_info(self.db_name)

        def _on_products_back():
            pg = self._pages.get("products")
            if pg is not None:
                try:
                    pg._show_list()
                except Exception:
                    pass
            self.topbar.set_title("Products")
            self.sidebar.set_active("products")

        page = ProductPage(
            self.db_name,
            company_name = company.get("company_name", ""),
            on_back      = _on_products_back,
            current_user = self.username,
        )
        old_pg = self._pages.get("products")
        if old_pg is not None:
            self.stack.removeWidget(old_pg)
            old_pg.deleteLater()

        self._pages["products"] = page
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)

    # ── Settings ──────────────────────────────────────────────

    def _open_settings(self):
        if self._CompanySettings is None:
            QMessageBox.information(
                self, "Coming Soon",
                "Company Settings will be available once connected to new_claude.py."
            )
            return
        self.settings_win = self._CompanySettings(self.db_name)
        self.settings_win.show()

    # ── User security / OTP ───────────────────────────────────

    def _open_user_security(self, username: str):
        if self._QRDisplay is None:
            QMessageBox.information(
                self, "Coming Soon",
                "User security will be available once connected to new_claude.py."
            )
            return

        otp, ok = QInputDialog.getText(
            self, "Verify Identity",
            "Enter your 6-digit OTP:", QLineEdit.Normal
        )
        if not ok or not otp:
            return
        if len(otp) != 6 or not otp.isdigit():
            QMessageBox.warning(self, "Error", "Enter a valid 6-digit code.")
            return

        secret, recovery_codes = self._get_user_otp_data(self.db_name, username)
        if secret is None:
            QMessageBox.warning(self, "Error", "User not found.")
            return
        if not self._verify_otp(secret, otp):
            QMessageBox.warning(self, "Error", "Invalid OTP ❌")
            return

        qr_path      = self._generate_qr(secret, username)
        self.qr_view = self._QRDisplay(secret, qr_path, recovery_codes)
        self.qr_view.show()


# ─────────────────────────────────────────────────────────────
#  STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Use a real DB path if you have one, otherwise runs with empty data
    DB = "billing.db"

    win = Dashboard(db_name=DB, username="Admin")
    win.show()
    sys.exit(app.exec_())
