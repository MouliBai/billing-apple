"""
EvoAura Desktop  —  PyQt6  |  SQLite  |  pyotp  |  qrcode
══════════════════════════════════════════════════════════════
EXACT BOOT FLOW:
  Start
    └─ DB file exists?
        ├─ NO  → AskDBName → MasterAuth → CompanySetup → Signup → QR → Login
        └─ YES → Users exist?
                  ├─ NO  → Signup → QR → Login
                  └─ YES → Login → OTP → Dashboard (embedded Sidebar)

Master TOTP secret: KRSXG5DSNFXGOIDB
Dependencies: PyQt6  pyotp  qrcode[pil]  Pillow
"""

import sys, os, sqlite3, hashlib, secrets, json, io, base64
import pyotp, qrcode
from PIL import Image

# Silence the UpdateLayeredWindowIndirect compositor warning on Windows
os.environ["QT_LOGGING_RULES"] = "qt.qpa.drawing=false"

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QComboBox, QCheckBox, QFileDialog, QFrame,
    QSizePolicy, QScrollArea, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui  import QFont, QColor, QPalette, QPixmap, QImage

from sidebar import Sidebar
from product_page import ProductPage
from input_behavior import ensure_global_input_guard

# ──────────────────────────────────────────────────────────────
#  MASTER SECRET
# ──────────────────────────────────────────────────────────────
MASTER_SECRET = "KRSXG5DSNFXGOIDB"

# ──────────────────────────────────────────────────────────────
#  DESIGN TOKENS  —  SINGLE SOURCE OF TRUTH FOR ALL COLOURS
#
#  Every colour used anywhere in this file (and in sidebar.py) is
#  listed here with a comment describing where it appears.
#  sidebar.py reads its own local C dict that mirrors these values.
# ──────────────────────────────────────────────────────────────
C = dict(
    # ── Backgrounds ───────────────────────────────────────────
    bg_white     = "#FFFFFF",   # page bg, input bg, toast bg, card bg in right panel
    bg_light     = "#F5F5F7",   # auth split bg, scrollable view bg
    bg_panel     = "#F2F2F7",   # right panel bg; also sidebar_bg in sidebar.py
    bg_card      = "#FAFAFA",   # feature cards, recovery code chips

    # ── Accent — EvoAura brand red/pink ───────────────────────
    accent       = "#FA2D48",   # primary accent: buttons, active nav, badges, borders
    accent_dark  = "#C81F36",   # gradient end for buttons / avatar
    accent_tint  = "rgba(250,45,72,0.08)",   # very soft accent fill (badges, icons bg)
    accent_tint2 = "rgba(250,45,72,0.10)",   # active nav item bg
    accent_tint3 = "rgba(250,45,72,0.04)",   # card hover fill
    accent_border= "rgba(250,45,72,0.22)",   # soft accent border (badges, brand row)
    accent_border2= "rgba(250,45,72,0.25)",  # card hover border
    accent_border3= "rgba(250,45,72,0.26)",  # sign-out button border

    # ── Semantic colours ──────────────────────────────────────
    success      = "#27ae60",   # strong password, success toast border, success button
    success_dark = "#1e8449",   # success button gradient end
    warning      = "#e67e22",   # warn toast border, warn button
    warning_dark = "#ca6f1e",   # warn button gradient end
    blue         = "#2980b9",   # info toast border, 2FA notice text/border
    blue_tint    = "rgba(41,128,185,0.08)",  # 2FA notice background
    blue_border  = "rgba(41,128,185,0.22)",  # 2FA notice border

    # ── Text ──────────────────────────────────────────────────
    text         = "#1D1D1F",   # primary text everywhere; also text_primary in sidebar
    text2        = "#6E6E73",   # secondary / muted labels; also text_secondary in sidebar
    text3        = "#A1A1A6",   # hint / disabled text; also text_disabled in sidebar

    # ── Inputs & borders ──────────────────────────────────────
    input_bg     = "#FFFFFF",   # input field background; also flyout_bg in sidebar
    border       = "#D2D2D7",   # input borders, dividers, card borders
    hover_bg     = "#E5E5EA",   # hover state on buttons and nav items

    # ── Gradient button variants (hex only, no #) ─────────────
    # used directly in GB._G dict below
    # primary : accent / accent_dark
    # secondary: 6E6E73 / 4a4a4f
    # success  : 27ae60 / 1e8449
    # warn     : e67e22 / ca6f1e
)

APP_SS = f"""
QWidget     {{ background:transparent; color:{C['text']};
              font-family:'-apple-system','Segoe UI',Arial,sans-serif; font-size:13px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{
    background:{C['bg_light']}; width:5px; border-radius:2px;
}}
QScrollBar::handle:vertical {{
    background:{C['text3']}; border-radius:2px; min-height:20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
"""


# ──────────────────────────────────────────────────────────────
#  DATABASE LAYER
# ──────────────────────────────────────────────────────────────
class DB:
    def __init__(self, path: str):
        self.path = path
        self.con  = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS company (
                id       INTEGER PRIMARY KEY,
                name     TEXT DEFAULT '',
                phone    TEXT DEFAULT '',
                address  TEXT DEFAULT '',
                gst      TEXT DEFAULT '',
                footer   TEXT DEFAULT '',
                logo_b64 TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                pw_hash       TEXT NOT NULL,
                totp_secret   TEXT NOT NULL,
                recovery_json TEXT NOT NULL DEFAULT '[]',
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # add role column if not present (migration for existing DBs)
        try:
            self.con.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        except Exception:
            pass
        self.con.commit()

    def company_exists(self) -> bool:
        row = self.con.execute("SELECT id FROM company LIMIT 1").fetchone()
        return row is not None

    def save_company(self, d: dict):
        self.con.execute("DELETE FROM company")
        self.con.execute(
            "INSERT INTO company (name,phone,address,gst,footer,logo_b64) "
            "VALUES (:name,:phone,:address,:gst,:footer,:logo_b64)", d)
        self.con.commit()

    def get_company(self) -> dict | None:
        r = self.con.execute("SELECT * FROM company LIMIT 1").fetchone()
        return dict(r) if r else None

    def update_company(self, d: dict):
        self.con.execute(
            "UPDATE company SET name=:name,phone=:phone,address=:address,"
            "gst=:gst,footer=:footer,logo_b64=:logo_b64 WHERE id=1", d)
        self.con.commit()

    def users_exist(self) -> bool:
        r = self.con.execute("SELECT id FROM users LIMIT 1").fetchone()
        return r is not None

    def create_user(self, username, pw_hash, totp_secret, recovery_json, role="user") -> bool:
        try:
            self.con.execute(
                "INSERT INTO users (username,pw_hash,totp_secret,recovery_json,role) "
                "VALUES (?,?,?,?,?)", (username, pw_hash, totp_secret, recovery_json, role))
            self.con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_admin(self) -> dict | None:
        r = self.con.execute(
            "SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
        return dict(r) if r else None

    def get_user(self, username) -> dict | None:
        r = self.con.execute(
            "SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(r) if r else None

    def list_usernames(self) -> list[str]:
        return [r[0] for r in self.con.execute(
            "SELECT username FROM users ORDER BY id").fetchall()]

    def consume_recovery(self, username: str, code: str) -> bool:
        u = self.get_user(username)
        if not u: return False
        codes = json.loads(u["recovery_json"])
        if code.upper() in [c.upper() for c in codes]:
            codes = [c for c in codes if c.upper() != code.upper()]
            self.con.execute(
                "UPDATE users SET recovery_json=? WHERE username=?",
                (json.dumps(codes), username))
            self.con.commit()
            return True
        return False

    def close(self):
        try: self.con.close()
        except Exception: pass


# ──────────────────────────────────────────────────────────────
#  UTILS
# ──────────────────────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def gen_recovery(n=8) -> list[str]:
    return [secrets.token_hex(4).upper() for _ in range(n)]

def totp_uri_pixmap(secret: str, username: str, issuer: str, size=190) -> QPixmap:
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
    img = qrcode.make(uri).resize((size, size), Image.NEAREST)
    buf = io.BytesIO(); img.save(buf, "PNG"); buf.seek(0)
    return QPixmap.fromImage(QImage.fromData(buf.read()))

def verify_master(code: str) -> bool:
    return pyotp.TOTP(MASTER_SECRET).verify(code.strip(), valid_window=1)

def verify_admin_totp(totp_secret: str, code: str) -> bool:
    return pyotp.TOTP(totp_secret).verify(code.strip(), valid_window=1)


# ──────────────────────────────────────────────────────────────
#  TINY UI HELPERS
# ──────────────────────────────────────────────────────────────
def F(sz=13, bold=False, mono=False) -> QFont:
    f = QFont("Courier New" if mono else "Segoe UI", sz)
    if bold: f.setWeight(QFont.Weight.Bold)
    return f

def L(text="", sz=13, col=None, bold=False,
      align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    w = QLabel(text)
    w.setFont(F(sz, bold))
    w.setStyleSheet(f"color:{col or C['text']};background:transparent;")
    w.setAlignment(align)
    w.setWordWrap(True)
    return w

def gap(h: int) -> QWidget:
    w = QWidget(); w.setFixedHeight(h)
    w.setStyleSheet("background:transparent;")
    return w

def hline() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(
        f"color:{C['border']};background:{C['border']};max-height:1px;")
    return f

def card_style(hover=False) -> str:
    base = (f"background:{C['bg_card']};border:1px solid {C['border']};"
            f"border-radius:10px;")
    return base + (
        f" background:{C['accent_tint3']};border:1px solid {C['accent_border2']};"
        if hover else ""
    )


# ──────────────────────────────────────────────────────────────
#  TOAST
# ──────────────────────────────────────────────────────────────
class Toast(QLabel):
    _P = {
        "success": (C["success"], "✓"),
        "error":   (C["accent"],  "✕"),
        "info":    (C["blue"],    "ℹ"),
        "warn":    (C["warning"], "⚠"),
    }

    def __init__(self, msg: str, kind="info", parent=None):
        super().__init__(parent)
        col, icon = self._P.get(kind, self._P["info"])
        self.setText(f"  {icon}   {msg}  ")
        self.setFont(F(12))
        self.setStyleSheet(
            f"QLabel{{background:{C['bg_white']};border:1.5px solid {col};"
            f"border-radius:10px;padding:10px 16px;color:{C['text']};}}")
        self.setFixedWidth(340)
        self.adjustSize()
        if parent:
            self.move(parent.width() - 355, 16)
            self.raise_()
            self.show()
        QTimer.singleShot(3500, self.deleteLater)


# ──────────────────────────────────────────────────────────────
#  STYLED INPUT
# ──────────────────────────────────────────────────────────────
class SI(QWidget):
    returnPressed = pyqtSignal()

    def __init__(self, label="", icon="", ph="", pw=False, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        self._lbl = None
        if label:
            self._lbl = QLabel(label.upper())
            self._lbl.setFont(F(9, bold=True))
            self._lbl.setStyleSheet(
                f"color:{C['text2']};letter-spacing:1.2px;background:transparent;")
            v.addWidget(self._lbl)

        self._box = QWidget()
        self._box.setStyleSheet(self._bs(False))
        rl = QHBoxLayout(self._box)
        rl.setContentsMargins(10, 0, 8, 0)
        rl.setSpacing(6)

        if icon:
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;border:none;")
            il.setFixedWidth(22)
            rl.addWidget(il)

        self.field = QLineEdit()
        self.field.setPlaceholderText(ph)
        self.field.setFont(F(13))
        if pw:
            self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setStyleSheet(
            f"QLineEdit{{background:transparent;border:none;"
            f"color:{C['text']};padding:10px 4px;}}"
            f"QLineEdit::placeholder{{color:{C['text3']};}}")
        self.field.returnPressed.connect(self.returnPressed)
        rl.addWidget(self.field)
        v.addWidget(self._box)

        self.field.focusInEvent  = self._fin
        self.field.focusOutEvent = self._fout

    def _bs(self, focused):
        c = C["accent"] if focused else C["border"]
        return (f"QWidget{{background:{C['input_bg']};border:1.5px solid {c};"
                f"border-radius:10px;}}")

    def _fin(self, e):
        self._box.setStyleSheet(self._bs(True))
        if self._lbl:
            self._lbl.setStyleSheet(
                f"color:{C['accent']};letter-spacing:1.2px;background:transparent;")
        QLineEdit.focusInEvent(self.field, e)

    def _fout(self, e):
        self._box.setStyleSheet(self._bs(False))
        if self._lbl:
            self._lbl.setStyleSheet(
                f"color:{C['text2']};letter-spacing:1.2px;background:transparent;")
        QLineEdit.focusOutEvent(self.field, e)

    def text(self)  -> str: return self.field.text()
    def clear(self):        self.field.clear()
    def set_pw(self, show):
        self.field.setEchoMode(
            QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password)


# ──────────────────────────────────────────────────────────────
#  GRADIENT BUTTON
# ──────────────────────────────────────────────────────────────
class GB(QPushButton):
    # c1/c2 are hex without '#'; matches C dict accent / accent_dark etc.
    _G = {
        "primary":   ("FA2D48", "C81F36"),  # C['accent'] / C['accent_dark']
        "secondary": ("6E6E73", "4a4a4f"),  # C['text2'] variants
        "success":   ("27ae60", "1e8449"),  # C['success'] / C['success_dark']
        "warn":      ("e67e22", "ca6f1e"),  # C['warning'] / C['warning_dark']
    }

    def __init__(self, text, v="primary", full=False, sm=False, parent=None):
        super().__init__(text, parent)
        c1, c2 = self._G.get(v, self._G["primary"])
        p  = "6px 14px" if sm else "11px 26px"
        sz = 11 if sm else 13
        self.setFont(F(sz, bold=True))
        if full:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QPushButton {{
                background : qlineargradient(
                    x1:0,y1:0,x2:1,y2:0,stop:0 #{c1},stop:1 #{c2});
                border        : none;
                border-radius : 10px;
                color         : white;
                padding       : {p};
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background : qlineargradient(
                    x1:0,y1:0,x2:1,y2:0,stop:0 #{c2},stop:1 #{c1});
            }}
            QPushButton:pressed  {{ opacity:0.8; }}
            QPushButton:disabled {{
                background:{C['border']}; color:{C['text3']};
            }}
        """)


# ──────────────────────────────────────────────────────────────
#  RIGHT PANEL  (context-aware, auth screens only)
# ──────────────────────────────────────────────────────────────
class RightPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background:{C['bg_panel']};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setStyleSheet("background:transparent;border:none;")
        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent;")
        self._vl = QVBoxLayout(self._inner)
        self._vl.setContentsMargins(34, 42, 34, 34)
        self._vl.setSpacing(0)

        self._build_brand()
        self._vl.addWidget(gap(20))
        self._vl.addWidget(hline())
        self._vl.addWidget(gap(18))

        self._dyn = QWidget()
        self._dyn.setStyleSheet("background:transparent;")
        self._dl  = QVBoxLayout(self._dyn)
        self._dl.setContentsMargins(0, 0, 0, 0)
        self._dl.setSpacing(0)
        self._vl.addWidget(self._dyn)
        self._vl.addStretch()

        self._vl.addWidget(gap(16))
        fl = QHBoxLayout()
        fl.setSpacing(12)
        for t in ["Privacy", "Terms", "Support"]:
            b = QPushButton(t)
            b.setStyleSheet(
                f"QPushButton{{color:{C['text3']};background:transparent;"
                f"border:none;font-size:10px;}}"
                f"QPushButton:hover{{color:{C['accent']};}}")
            fl.addWidget(b)
        fl.addStretch()
        self._vl.addLayout(fl)
        sc.setWidget(self._inner)
        outer.addWidget(sc)

        self.show_features()

    def _build_brand(self):
        badge = QLabel("⚡  EVO AURA")
        badge.setFont(F(13, bold=True))
        badge.setStyleSheet(
            f"color:{C['accent']};background:{C['accent_tint']};"
            f"border:1px solid {C['accent_border']};border-radius:16px;"
            f"padding:5px 16px;letter-spacing:2px;")
        badge.setFixedWidth(154)
        self._vl.addWidget(badge)
        self._vl.addWidget(gap(20))

        h = QLabel("The future of\nbusiness management")
        h.setFont(F(20, bold=True))
        h.setStyleSheet(f"color:{C['text']};background:transparent;")
        h.setWordWrap(True)
        self._vl.addWidget(h)
        self._vl.addWidget(gap(10))

        d = L("EvoAura — secure authentication, real-time analytics, "
              "and powerful company tooling in one elegant platform.",
              sz=11, col=C["text2"])
        self._vl.addWidget(d)

    def _clear(self):
        while self._dl.count():
            it = self._dl.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def show_features(self):
        self._clear()
        # ── EvoAura description ───────────────────────────────
        self._dl.addWidget(L(
            "Evo Aura Billing Software is an advanced, all-in-one business "
            "management solution designed to simplify billing, streamline "
            "operations, and deliver powerful insights for smarter decision-making.",
            sz=11, col=C["text2"]))
        self._dl.addWidget(gap(8))
        self._dl.addWidget(L(
            "With a clean, user-friendly interface and robust features, it enables "
            "businesses to handle invoicing, inventory, customer management, and GST "
            "compliance effortlessly — built for speed, accuracy, and seamless "
            "day-to-day operations.",
            sz=11, col=C["text2"]))
        self._dl.addWidget(gap(8))
        self._dl.addWidget(L(
            "At Evo Aura, we empower businesses with intelligent billing solutions "
            "that go beyond basic invoicing — integrating cutting-edge data analytics, "
            "real-time reporting, and automated GST breakdowns to give you complete "
            "control over your finances and operations.",
            sz=11, col=C["text2"]))
        self._dl.addWidget(gap(16))
        self._dl.addWidget(hline())
        self._dl.addWidget(gap(14))
        # ── Feature cards ─────────────────────────────────────
        for icon, title, desc in [
            ("🔐", "Bank-grade Security", "TOTP 2FA with pyotp — real-time verified"),
            ("⚡", "Lightning Fast",      "SQLite local storage — instant response"),
            ("📊", "Smart Dashboard",     "Real-time stats & business intelligence"),
            ("🏢", "Multi-tenant",        "Multiple company DBs from one install"),
            ("🧾", "GST Compliance",      "Automated GST breakdowns & reports"),
            ("📦", "Inventory Control",   "Smart stock tracking & low-stock alerts"),
        ]:
            c = QWidget()
            c.setStyleSheet(
                f"QWidget{{background:{C['bg_white']};"
                f"border:1px solid {C['border']};border-radius:10px;}}")
            cl = QHBoxLayout(c)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(10)
            il = QLabel(icon); il.setFont(F(16))
            il.setStyleSheet("background:transparent;border:none;")
            il.setFixedWidth(26)
            cl.addWidget(il, alignment=Qt.AlignmentFlag.AlignTop)
            tw = QWidget(); tw.setStyleSheet("background:transparent;border:none;")
            tl = QVBoxLayout(tw); tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(2)
            tl.addWidget(L(title, sz=11, bold=True))
            tl.addWidget(L(desc, sz=10, col=C["text2"]))
            cl.addWidget(tw)
            self._dl.addWidget(c)
            self._dl.addWidget(gap(8))

    def show_login_panel(self, usernames: list, db_name: str):
        self._clear()
        self._dl.addWidget(L("Registered Users", sz=11, bold=True, col=C["text2"]))
        self._dl.addWidget(gap(4))
        if db_name:
            db_l = QLabel(f"📂  {db_name}")
            db_l.setFont(F(10, mono=True))
            db_l.setStyleSheet(f"color:{C['accent']};background:transparent;")
            self._dl.addWidget(db_l)
            self._dl.addWidget(gap(10))
        if not usernames:
            self._dl.addWidget(
                L("No users yet — sign up first.", sz=11, col=C["text3"]))
        for u in usernames:
            row = QWidget()
            row.setStyleSheet(
                f"QWidget{{background:{C['bg_white']};"
                f"border:1px solid {C['border']};border-radius:8px;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 7, 10, 7)
            rl.setSpacing(10)
            av = QLabel(u[0].upper())
            av.setFixedSize(28, 28)
            av.setAlignment(Qt.AlignmentFlag.AlignCenter)
            av.setFont(F(11, bold=True))
            av.setStyleSheet(
                f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 {C['accent']},stop:1 {C['accent_dark']});"
                f"border-radius:14px;color:white;")
            rl.addWidget(av)
            rl.addWidget(L(u, sz=12))
            rl.addStretch()
            self._dl.addWidget(row)
            self._dl.addWidget(gap(6))

    def show_signup_panel(self, db_name: str):
        self._clear()
        if db_name:
            self._dl.addWidget(
                L("Joining Workspace", sz=11, bold=True, col=C["text2"]))
            self._dl.addWidget(gap(4))
            ws = QLabel(f"📂  {db_name}")
            ws.setFont(F(11, mono=True))
            ws.setStyleSheet(f"color:{C['accent']};background:transparent;")
            self._dl.addWidget(ws)
            self._dl.addWidget(gap(16))
        for icon, tip in [
            ("🔒", "Use a strong password — 12+ characters"),
            ("📱", "Install Google Authenticator or Authy first"),
            ("💾", "Store your 8 recovery codes somewhere safe"),
            ("🛡️", "Master code comes from your authenticator"),
        ]:
            row = QHBoxLayout(); row.setSpacing(10)
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;"); il.setFixedWidth(24)
            row.addWidget(il)
            row.addWidget(L(tip, sz=11, col=C["text2"]))
            row.addStretch()
            cw = QWidget(); cw.setStyleSheet("background:transparent;")
            cw.setLayout(row)
            self._dl.addWidget(cw)
            self._dl.addWidget(gap(9))

    def show_master_hint(self):
        self._clear()
        self._dl.addWidget(
            L("Master TOTP Setup", sz=11, bold=True, col=C["text2"]))
        self._dl.addWidget(gap(10))
        for icon, tip in [
            ("1️⃣", "Open Google Authenticator or Authy"),
            ("2️⃣", "Tap  +  → Enter setup key manually"),
            ("3️⃣", "Account name:  EvoAura Master"),
            ("4️⃣", "Enter the secret key provided to you"),
            ("5️⃣", "Type: TOTP  |  Time-based"),
            ("6️⃣", "Enter the 6-digit code shown in the app"),
        ]:
            row = QHBoxLayout(); row.setSpacing(10)
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;"); il.setFixedWidth(26)
            tl = L(tip, sz=11, col=C["text2"]); tl.setWordWrap(True)
            row.addWidget(il); row.addWidget(tl, 1); row.addStretch()
            cw = QWidget(); cw.setStyleSheet("background:transparent;")
            cw.setLayout(row)
            self._dl.addWidget(cw); self._dl.addWidget(gap(8))
        self._dl.addWidget(gap(6))
        # Contact card instead of revealing the secret
        contact = QWidget()
        contact.setStyleSheet(
            f"QWidget{{background:{C['blue_tint']};"
            f"border:1px solid {C['blue_border']};border-radius:8px;}}")
        ccl = QVBoxLayout(contact)
        ccl.setContentsMargins(12, 10, 12, 10); ccl.setSpacing(3)
        ccl.addWidget(L("🔑  Need the Master Key?", sz=11, bold=True, col=C["blue"]))
        ccl.addWidget(L("Contact your EvoAura representative:", sz=10, col=C["text2"]))
        ccl.addWidget(L("📧  evoaura.in@gmail.com", sz=10, col=C["blue"]))
        ccl.addWidget(L("💬  WhatsApp: +91 99944 84077", sz=10, col=C["blue"]))
        self._dl.addWidget(contact)

    def show_otp_hint(self, username: str):
        self._clear()
        self._dl.addWidget(L("Verifying 2FA", sz=11, bold=True, col=C["text2"]))
        self._dl.addWidget(gap(8))
        for icon, tip in [
            ("📱", "Open your authenticator app"),
            ("🔍", f"Find the entry for  {username}"),
            ("⌨️", "Enter the current 6-digit code"),
            ("⏱️", "Codes refresh every 30 seconds"),
            ("🆘", "No phone? use a recovery code instead"),
        ]:
            row = QHBoxLayout(); row.setSpacing(10)
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;"); il.setFixedWidth(24)
            row.addWidget(il)
            row.addWidget(L(tip, sz=11, col=C["text2"]))
            row.addStretch()
            cw = QWidget(); cw.setStyleSheet("background:transparent;")
            cw.setLayout(row)
            self._dl.addWidget(cw); self._dl.addWidget(gap(8))


# ──────────────────────────────────────────────────────────────
#  LEFT VIEW BASE  (scrollable panel)
# ──────────────────────────────────────────────────────────────
class LV(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"background:{C['bg_light']};border:none;")
        self._w = QWidget()
        self._w.setStyleSheet(f"background:{C['bg_light']};")
        self._l = QVBoxLayout(self._w)
        self._l.setContentsMargins(50, 46, 50, 46)
        self._l.setSpacing(0)
        self.setWidget(self._w)
        self.setMinimumWidth(380)

    @property
    def vl(self): return self._l


# ──────────────────────────────────────────────────────────────
#  VIEW 0  —  AskDBName
# ──────────────────────────────────────────────────────────────
class V_AskDB(LV):
    sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        vl = self.vl

        row = QHBoxLayout(); row.setSpacing(8)
        for n in range(1, 4):
            d = QLabel(str(n))
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setFixedSize(26, 26); d.setFont(F(10, bold=True))
            if n == 1:
                d.setStyleSheet(
                    f"background:{C['accent']};border-radius:13px;color:white;")
            else:
                d.setStyleSheet(
                    f"background:{C['bg_light']};border:1px solid {C['border']};"
                    f"border-radius:13px;color:{C['text3']};")
            row.addWidget(d)
            if n < 3:
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedWidth(22)
                sep.setStyleSheet(
                    f"color:{C['border']};background:{C['border']};max-height:1px;")
                row.addWidget(sep)
        row.addStretch()
        vl.addLayout(row); vl.addWidget(gap(28))

        vl.addWidget(L("Set up your workspace", sz=22, bold=True))
        vl.addWidget(gap(8))
        vl.addWidget(L(
            "Enter your company name to create a secure local database.\n"
            "This becomes your workspace identifier.", sz=13, col=C["text2"]))
        vl.addWidget(gap(28))

        self._inp = SI("Company / Database Name", "🏢", "e.g. TechCorp, MyShop, Acme")
        self._inp.returnPressed.connect(self._submit)
        vl.addWidget(self._inp); vl.addWidget(gap(6))
        self._hint = L("", sz=11, col=C["text3"])
        vl.addWidget(self._hint)
        self._inp.field.textChanged.connect(
            lambda t: self._hint.setText(
                f"Will create:  {t.strip().replace(' ','_')}.db" if t.strip() else ""))
        vl.addWidget(gap(24))

        btn = GB("Continue  →", full=True); btn.clicked.connect(self._submit)
        vl.addWidget(btn); vl.addStretch()

    def _submit(self):
        raw = self._inp.text().strip().replace(" ", "_")
        if not raw: return
        self.sig.emit(raw if raw.endswith(".db") else f"{raw}.db")


# ──────────────────────────────────────────────────────────────
#  VIEW 1  —  MasterAuth
# ──────────────────────────────────────────────────────────────
class V_MasterAuth(LV):
    sig_ok    = pyqtSignal()
    sig_toast = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        vl = self.vl

        icon = QLabel("🔐"); icon.setFont(F(26))
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"background:{C['accent_tint']};"
            f"border:2px solid {C['accent_border']};border-radius:28px;")
        vl.addWidget(icon); vl.addWidget(gap(18))

        vl.addWidget(L("Security Verification", sz=22, bold=True))
        vl.addWidget(gap(8))
        self._desc = L(
            "Enter your 6-digit master TOTP code to authorize\ncreation of this database.",
            sz=13, col=C["text2"])
        vl.addWidget(self._desc); vl.addWidget(gap(26))

        self._code = SI("Master TOTP Code", "🔑", "6-digit code from authenticator", pw=True)
        self._code.returnPressed.connect(self._verify)
        vl.addWidget(self._code); vl.addWidget(gap(24))

        btn = GB("Verify & Create Database", full=True); btn.clicked.connect(self._verify)
        vl.addWidget(btn); vl.addWidget(gap(14))
        vl.addWidget(L("Open your authenticator app and enter the 6-digit master code.",
                       sz=10, col=C["text3"]))
        vl.addStretch()

    def set_db(self, db):
        self._desc.setText(
            f"Enter your 6-digit master TOTP code to authorize\ncreation of  {db}")

    def _verify(self):
        if verify_master(self._code.text()):
            self.sig_toast.emit("Master verified — database created.", "success")
            self._code.clear()
            QTimer.singleShot(350, self.sig_ok.emit)
        else:
            self.sig_toast.emit("Invalid master code. Try again.", "error")
            self._code.clear()


# ──────────────────────────────────────────────────────────────
#  VIEW 2  —  CompanySettings
# ──────────────────────────────────────────────────────────────
class V_CompanySettings(LV):
    sig_save  = pyqtSignal()
    sig_toast = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._logo_b64 = ""
        vl = self.vl

        vl.addWidget(L("🏢  Company Settings", sz=21, bold=True))
        vl.addWidget(gap(6))
        vl.addWidget(L("Configure your company profile and branding.", sz=13, col=C["text2"]))
        vl.addWidget(gap(20))

        logo_card = QWidget()
        logo_card.setStyleSheet(
            f"QWidget{{background:{C['bg_light']};"
            f"border:1.5px dashed {C['border']};border-radius:12px;}}")
        lcl = QHBoxLayout(logo_card)
        lcl.setContentsMargins(14, 14, 14, 14); lcl.setSpacing(14)
        self._logo_lbl = QLabel("🏢"); self._logo_lbl.setFont(F(22))
        self._logo_lbl.setFixedSize(68, 68)
        self._logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_lbl.setStyleSheet(
            f"background:{C['border']};border:1px solid {C['border']};border-radius:8px;")
        lcl.addWidget(self._logo_lbl)
        col_w = QWidget(); col_w.setStyleSheet("background:transparent;border:none;")
        cl2 = QVBoxLayout(col_w); cl2.setContentsMargins(0, 0, 0, 0); cl2.setSpacing(8)
        cl2.addWidget(L("Company Logo", sz=12, bold=True))
        br = QHBoxLayout(); br.setSpacing(8)
        up = GB("Upload", "secondary", sm=True); up.clicked.connect(self._upload)
        self._rm = GB("Remove", "primary", sm=True); self._rm.clicked.connect(self._remove)
        self._rm.setVisible(False)
        br.addWidget(up); br.addWidget(self._rm); br.addStretch()
        cl2.addLayout(br); lcl.addWidget(col_w)
        vl.addWidget(logo_card); vl.addWidget(gap(16))

        self._cname = SI("Company Name", "🏢", "Your company name")
        self._phone = SI("Phone",        "📞", "+91 98765 43210")
        self._addr  = SI("Address",      "📍", "123 Business St, City")
        self._gst   = SI("GST Number",   "🧾", "22AAAAA0000A1Z5")
        for w in [self._cname, self._phone, self._addr, self._gst]:
            vl.addWidget(w); vl.addWidget(gap(10))

        vl.addWidget(L("FOOTER MESSAGE", sz=9, col=C["text2"]))
        vl.addWidget(gap(4))
        self._footer = QTextEdit()
        self._footer.setPlaceholderText("Invoice footer, terms, or notes…")
        self._footer.setMaximumHeight(68); self._footer.setFont(F(12))
        self._footer.setStyleSheet(
            f"QTextEdit{{background:{C['input_bg']};border:1.5px solid {C['border']};"
            f"border-radius:10px;padding:8px 12px;color:{C['text']};}}")
        vl.addWidget(self._footer); vl.addWidget(gap(22))

        btn = GB("Save & Continue  →", full=True); btn.clicked.connect(self._save)
        vl.addWidget(btn); vl.addStretch()

    def prefill(self, db_name: str):
        self._cname.field.setText(
            db_name.replace(".db", "").replace("_", " ").title())

    def _upload(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not p: return
        with open(p, "rb") as f: raw = f.read()
        self._logo_b64 = base64.b64encode(raw).decode()
        pix = QPixmap(p).scaled(
            68, 68,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        self._logo_lbl.setPixmap(pix); self._logo_lbl.setText("")
        self._rm.setVisible(True)

    def _remove(self):
        self._logo_b64 = ""
        self._logo_lbl.clear(); self._logo_lbl.setText("🏢")
        self._rm.setVisible(False)

    def get_data(self) -> dict:
        return dict(
            name=self._cname.text(), phone=self._phone.text(),
            address=self._addr.text(), gst=self._gst.text(),
            footer=self._footer.toPlainText(), logo_b64=self._logo_b64)

    def _save(self):
        if not self._cname.text().strip():
            self.sig_toast.emit("Company name is required.", "error"); return
        self.sig_toast.emit("Company settings saved!", "success")
        QTimer.singleShot(350, self.sig_save.emit)


# ──────────────────────────────────────────────────────────────
#  VIEW 3  —  Signup
#  Mode A (is_first=True):  ADMIN creation — username locked, master code required
#  Mode B (is_first=False): regular user  — free username,  admin TOTP required
# ──────────────────────────────────────────────────────────────
class V_Signup(LV):
    sig_ok    = pyqtSignal(str, str, str, str)   # username, totp_secret, recovery_json, role
    sig_login = pyqtSignal()
    sig_toast = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._is_first = True
        self._admin_totp_secret = ""
        vl = self.vl

        self._title_lbl = L("Create ADMIN Account", sz=22, bold=True)
        vl.addWidget(self._title_lbl)
        vl.addWidget(gap(6))
        self._ws = L("", sz=12, col=C["text2"]); vl.addWidget(self._ws)
        vl.addWidget(gap(10))

        # Mode notice banner
        self._notice = QWidget()
        self._notice.setStyleSheet(
            f"QWidget{{background:{C['accent_tint']};"
            f"border:1px solid {C['accent_border']};border-radius:10px;}}")
        nl = QVBoxLayout(self._notice)
        nl.setContentsMargins(14, 10, 14, 10); nl.setSpacing(2)
        self._notice_lbl = L("", sz=11, col=C["accent"])
        nl.addWidget(self._notice_lbl)
        vl.addWidget(self._notice); vl.addWidget(gap(18))

        # Locked ADMIN badge (shown in mode A)
        self._un_locked_row = QWidget()
        self._un_locked_row.setStyleSheet("background:transparent;")
        url = QVBoxLayout(self._un_locked_row)
        url.setContentsMargins(0, 0, 0, 0); url.setSpacing(4)
        lbl_un = QLabel("USERNAME")
        lbl_un.setFont(F(9, bold=True))
        lbl_un.setStyleSheet(f"color:{C['text2']};letter-spacing:1.2px;background:transparent;")
        url.addWidget(lbl_un)
        self._un_badge = QLabel("ADMIN")
        self._un_badge.setFont(F(14, bold=True))
        self._un_badge.setStyleSheet(
            f"color:{C['accent']};background:{C['accent_tint']};"
            f"border:1.5px solid {C['accent_border']};border-radius:10px;"
            f"padding:10px 14px;")
        url.addWidget(self._un_badge)
        vl.addWidget(self._un_locked_row); vl.addWidget(gap(10))

        # Free username field (shown in mode B)
        self._un = SI("Username", "👤", "Choose a username")
        self._un.setVisible(False)
        vl.addWidget(self._un); vl.addWidget(gap(10))

        self._pw  = SI("Password",         "🔒", "Strong password (12+ chars)", pw=True)
        self._cpw = SI("Confirm Password", "🔒", "Repeat password",             pw=True)
        for w in [self._pw, self._cpw]:
            vl.addWidget(w); vl.addWidget(gap(10))

        self._slab = L("", sz=10, col=C["text3"]); vl.addWidget(self._slab)
        self._bbg  = QWidget(); self._bbg.setFixedHeight(4)
        self._bbg.setStyleSheet(f"background:{C['border']};border-radius:2px;")
        self._bar  = QWidget(self._bbg); self._bar.setFixedHeight(4)
        self._bar.setStyleSheet(f"background:{C['accent']};border-radius:2px;")
        self._bar.setFixedWidth(0)
        vl.addWidget(self._bbg); vl.addWidget(gap(8))
        self._pw.field.textChanged.connect(self._strength)

        chk = QCheckBox("Show passwords")
        chk.setStyleSheet(f"color:{C['text2']};background:transparent;")
        chk.toggled.connect(lambda c: [self._pw.set_pw(c), self._cpw.set_pw(c)])
        vl.addWidget(chk); vl.addWidget(gap(8))
        vl.addWidget(hline()); vl.addWidget(gap(10))

        # Auth code field — label changes per mode
        self._ms = SI("", "🛡️", "6-digit code", pw=True)
        self._ms.returnPressed.connect(self._create)
        self._ms_label = QLabel("MASTER CODE")
        self._ms_label.setFont(F(9, bold=True))
        self._ms_label.setStyleSheet(
            f"color:{C['text2']};letter-spacing:1.2px;background:transparent;")
        vl.addWidget(self._ms_label); vl.addWidget(gap(4))
        vl.addWidget(self._ms)
        self._ms_hint = L("", sz=10, col=C["text3"])
        vl.addWidget(gap(4)); vl.addWidget(self._ms_hint)
        vl.addWidget(gap(20))

        self._btn = GB("Create ADMIN Account", full=True)
        self._btn.clicked.connect(self._create)
        vl.addWidget(self._btn); vl.addWidget(gap(16))

        fl = QHBoxLayout(); fl.addStretch()
        fl.addWidget(L("Already have an account? ", sz=12, col=C["text2"]))
        si_btn = QPushButton("Sign in →")
        si_btn.setStyleSheet(
            f"color:{C['accent']};background:transparent;border:none;"
            "font-size:12px;font-weight:600;")
        si_btn.clicked.connect(self.sig_login.emit)
        fl.addWidget(si_btn); fl.addStretch()
        vl.addLayout(fl); vl.addStretch()

        self.set_mode(True)   # default to ADMIN mode

    def set_mode(self, is_first: bool, admin_totp_secret: str = ""):
        self._is_first = is_first
        self._admin_totp_secret = admin_totp_secret
        if is_first:
            self._title_lbl.setText("Create ADMIN Account")
            self._notice_lbl.setText(
                "🔰  You are creating the ADMIN account.\n"
                "Username is fixed as 'ADMIN'. Set a strong password and enter the Master Code.")
            self._un_locked_row.setVisible(True)
            self._un.setVisible(False)
            self._ms_label.setText("MASTER CODE  (from your authenticator app)")
            self._ms.field.setPlaceholderText("6-digit master TOTP code")
            self._ms_hint.setText(
                "Don't have the master key?  Contact evoaura.in@gmail.com\n"
                "or WhatsApp +91 99944 84077")
            self._btn.setText("Create ADMIN Account")
        else:
            self._title_lbl.setText("Add New User")
            self._notice_lbl.setText(
                "🔑  Admin authorization required.\n"
                "Enter the ADMIN's current 6-digit authenticator code to create a new user.")
            self._un_locked_row.setVisible(False)
            self._un.setVisible(True)
            self._ms_label.setText("ADMIN SECRET CODE  (from ADMIN's authenticator app)")
            self._ms.field.setPlaceholderText("6-digit code from ADMIN's authenticator")
            self._ms_hint.setText("Ask the ADMIN to provide their current authenticator code.")
            self._btn.setText("Create User Account")

    def set_db(self, db: str):
        label = "Setting up workspace" if self._is_first else "Joining workspace"
        self._ws.setText(f"{label}:  {db}")

    def clear_fields(self):
        self._un.clear(); self._pw.clear()
        self._cpw.clear(); self._ms.clear()
        self._slab.setText(""); self._bar.setFixedWidth(0)

    def _strength(self, t: str):
        n = len(t)
        if not n:
            self._slab.setText(""); self._bar.setFixedWidth(0); return
        col = (C["success"] if n > 10 else
               C["accent"]  if n > 6  else C["accent"])
        txt = "Strong ✓" if n > 10 else ("Medium" if n > 6 else "Weak")
        self._slab.setText(f"Strength:  {txt}")
        self._bar.setStyleSheet(f"background:{col};border-radius:2px;")
        self._bar.setFixedWidth(int(self._bbg.width() * min(100, n * 9) / 100))

    def resizeEvent(self, e):
        super().resizeEvent(e); self._strength(self._pw.text())

    def _create(self):
        username = "ADMIN" if self._is_first else self._un.text().strip()
        pw  = self._pw.text()
        cp  = self._cpw.text()
        ms  = self._ms.text().strip()
        if self._is_first:
            if not all([pw, cp, ms]):
                self.sig_toast.emit("Please fill in all fields.", "error"); return
        else:
            if not all([username, pw, cp, ms]):
                self.sig_toast.emit("Please fill in all fields.", "error"); return
        if pw != cp:
            self.sig_toast.emit("Passwords do not match.", "error"); return
        if len(ms) != 6 or not ms.isdigit():
            self.sig_toast.emit("Code must be exactly 6 digits.", "error"); return
        if self._is_first:
            if not verify_master(ms):
                self.sig_toast.emit("Invalid master code.", "error"); self._ms.clear(); return
            role = "admin"
        else:
            if not self._admin_totp_secret:
                self.sig_toast.emit("Admin TOTP secret not available.", "error"); return
            if not verify_admin_totp(self._admin_totp_secret, ms):
                self.sig_toast.emit("Invalid admin code.", "error"); self._ms.clear(); return
            role = "user"
        secret   = pyotp.random_base32()
        recovery = gen_recovery(8)
        msg = ("ADMIN account created! Now scan your QR code." if self._is_first
               else f"User '{username}' created! Now scan the QR code.")
        self.sig_toast.emit(msg, "success")
        QTimer.singleShot(350, lambda: self.sig_ok.emit(
            username, secret, json.dumps(recovery), role))


# ──────────────────────────────────────────────────────────────
#  VIEW 4  —  QR Display
# ──────────────────────────────────────────────────────────────
class V_QR(LV):
    sig_done = pyqtSignal()

    def __init__(self):
        super().__init__()
        vl = self.vl

        vl.addWidget(L("Scan with Authenticator", sz=20, bold=True,
                       align=Qt.AlignmentFlag.AlignCenter))
        vl.addWidget(gap(6))
        self._sub = L("", sz=12, col=C["text2"],
                      align=Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(self._sub); vl.addWidget(gap(20))

        self._qr_lbl = QLabel(); self._qr_lbl.setFixedSize(190, 190)
        self._qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_lbl.setStyleSheet("background:white;border-radius:10px;")
        vl.addWidget(self._qr_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(gap(14))

        self._sec_lbl = QLabel(); self._sec_lbl.setFont(F(11, mono=True))
        self._sec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sec_lbl.setStyleSheet(
            f"background:{C['bg_light']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:8px 14px;color:{C['accent']};letter-spacing:2px;")
        vl.addWidget(self._sec_lbl); vl.addWidget(gap(20))

        vl.addWidget(L("Recovery Codes — save all 8 before continuing",
                       sz=11, bold=True, col=C["text2"]))
        vl.addWidget(gap(8))
        self._cgrid = QWidget(); self._cgrid.setStyleSheet("background:transparent;")
        self._cgl   = QGridLayout(self._cgrid); self._cgl.setSpacing(7)
        vl.addWidget(self._cgrid); vl.addWidget(gap(22))

        btn = GB("✓  I've saved my codes — Continue", "success", full=True)
        btn.clicked.connect(self.sig_done.emit)
        vl.addWidget(btn); vl.addStretch()

    def setup(self, username: str, totp_secret: str, recovery: list, db_name: str):
        self._sub.setText(f"Setting up 2FA for  {username}")
        self._sec_lbl.setText(totp_secret)
        self._qr_lbl.setPixmap(
            totp_uri_pixmap(totp_secret, username, f"EvoAura/{db_name}", 190))
        while self._cgl.count():
            it = self._cgl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        for i, code in enumerate(recovery):
            cl = QLabel(code); cl.setFont(F(10, mono=True))
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setStyleSheet(
                f"background:{C['bg_light']};border:1px solid {C['border']};"
                f"border-radius:6px;padding:5px 10px;color:{C['text']};")
            self._cgl.addWidget(cl, i // 2, i % 2)


# ──────────────────────────────────────────────────────────────
#  VIEW 5  —  Login
# ──────────────────────────────────────────────────────────────
class V_Login(LV):
    sig_ok     = pyqtSignal(str)
    sig_signup = pyqtSignal()
    sig_toast  = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        vl = self.vl

        badge = QLabel("WELCOME"); badge.setFont(F(9, bold=True))
        badge.setStyleSheet(
            f"color:{C['accent']};background:{C['accent_tint']};"
            f"border:1px solid {C['accent_border']};border-radius:14px;"
            f"padding:4px 14px;letter-spacing:1.8px;")
        badge.setFixedWidth(110); vl.addWidget(badge); vl.addWidget(gap(14))

        vl.addWidget(L("Sign In", sz=24, bold=True)); vl.addWidget(gap(6))
        self._ws = L("", sz=12, col=C["text2"]); vl.addWidget(self._ws)
        vl.addWidget(gap(24))

        vl.addWidget(L("USERNAME", sz=9, col=C["text2"])); vl.addWidget(gap(4))
        self._combo = QComboBox(); self._combo.setFont(F(13))
        self._combo.setStyleSheet(f"""
            QComboBox {{
                background:{C['input_bg']};border:1.5px solid {C['border']};
                border-radius:10px;padding:9px 14px;
                color:{C['text']};min-height:20px;
            }}
            QComboBox::drop-down {{ border:none; width:26px; }}
            QComboBox QAbstractItemView {{
                background:{C['bg_white']};border:1px solid {C['border']};
                color:{C['text']};
                selection-background-color:{C['accent_tint2']};
            }}
        """)
        vl.addWidget(self._combo); vl.addWidget(gap(12))

        self._pw = SI("Password", "🔒", "Enter your password", pw=True)
        self._pw.returnPressed.connect(self._login)
        vl.addWidget(self._pw); vl.addWidget(gap(14))

        notice = QWidget()
        notice.setStyleSheet(
            f"QWidget{{background:{C['blue_tint']};"
            f"border:1px solid {C['blue_border']};border-radius:10px;}}")
        nl = QHBoxLayout(notice); nl.setContentsMargins(12, 9, 12, 9); nl.setSpacing(10)
        nl.addWidget(L("A 2FA code will be required after login.", sz=11, col=C["blue"]))
        vl.addWidget(notice); vl.addWidget(gap(20))

        btn = GB("Sign In", full=True); btn.clicked.connect(self._login)
        vl.addWidget(btn); vl.addWidget(gap(16))

        fl = QHBoxLayout(); fl.addStretch()
        fl.addWidget(L("New user? ", sz=12, col=C["text2"]))
        nb = QPushButton("Create account →")
        nb.setStyleSheet(
            f"color:{C['accent']};background:transparent;border:none;"
            "font-size:12px;font-weight:600;")
        nb.clicked.connect(self.sig_signup.emit)
        fl.addWidget(nb); fl.addStretch()
        vl.addLayout(fl); vl.addStretch()

    def set_db(self, db: str):
        self._ws.setText(f"Workspace:  {db}")

    def clear_fields(self):
        self._pw.clear()
        if self._combo.count() > 0:
            self._combo.setCurrentIndex(0)

    def refresh_users(self, users: list):
        self._combo.clear()
        self._combo.addItem("👤  Select user")
        for u in users: self._combo.addItem(u)

    def _login(self):
        u  = self._combo.currentText()
        pw = self._pw.text()
        if u.startswith("👤") or not pw:
            self.sig_toast.emit("Select a user and enter your password.", "error")
            return
        self.sig_ok.emit(u)


# ──────────────────────────────────────────────────────────────
#  VIEW 6  —  OTP Verify
#  Auto-verifies when 6th digit is entered;
#  Verify button also accepts recovery codes
# ──────────────────────────────────────────────────────────────
class V_OTP(LV):
    sig_ok    = pyqtSignal()
    sig_toast = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._username = ""
        self._auto_verify_enabled = True
        vl = self.vl

        shield = QLabel("🛡️"); shield.setFont(F(26))
        shield.setFixedSize(66, 66)
        shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield.setStyleSheet(
            f"background:{C['accent_tint']};"
            f"border:2px solid {C['accent_border']};border-radius:33px;")
        vl.addWidget(shield, alignment=Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(gap(16))

        vl.addWidget(L("Two-Factor Auth", sz=22, bold=True,
                       align=Qt.AlignmentFlag.AlignCenter))
        vl.addWidget(gap(8))
        self._desc = L("", sz=12, col=C["text2"],
                       align=Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(self._desc); vl.addWidget(gap(26))

        brow = QHBoxLayout(); brow.setSpacing(8); brow.addStretch()
        self._boxes: list[QLineEdit] = []
        for i in range(6):
            b = QLineEdit(); b.setMaxLength(1); b.setFixedSize(46, 54)
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b.setFont(F(20, bold=True, mono=True))
            b.setStyleSheet(
                f"QLineEdit{{background:{C['input_bg']};border:2px solid {C['border']};"
                f"border-radius:10px;color:{C['text']};}}"
                f"QLineEdit:focus{{border:2px solid {C['accent']};}}")
            b.textChanged.connect(lambda t, idx=i: self._adv(idx, t))
            b.keyPressEvent = lambda e, idx=i, orig=b.keyPressEvent: self._back(e, idx, orig)
            self._boxes.append(b); brow.addWidget(b)
        brow.addStretch()
        bw = QWidget(); bw.setStyleSheet("background:transparent;"); bw.setLayout(brow)
        vl.addWidget(bw); vl.addWidget(gap(6))

        self._otp_status = L("", sz=11, col=C["text3"],
                             align=Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(self._otp_status); vl.addWidget(gap(14))

        vl.addWidget(L("— or enter a recovery code —", sz=10, col=C["text3"],
                       align=Qt.AlignmentFlag.AlignCenter))
        vl.addWidget(gap(8))
        self._rec = SI(ph="Recovery code  (e.g. AB12CD34)")
        vl.addWidget(self._rec); vl.addWidget(gap(22))

        btn = GB("Verify", full=True); btn.clicked.connect(self.sig_ok.emit)
        vl.addWidget(btn); vl.addStretch()

    def set_user(self, u: str):
        self._username = u
        self._desc.setText(
            f"Open your authenticator app and enter\nthe 6-digit code for  {u}")
        for b in self._boxes: b.clear()
        self._rec.clear()
        self._otp_status.setText("")
        self._auto_verify_enabled = True
        self._boxes[0].setFocus()

    def otp_code(self) -> str: return "".join(b.text() for b in self._boxes)
    def rec_code(self) -> str: return self._rec.text().strip().upper()

    def _adv(self, idx, t):
        if t:
            if idx < 5:
                self._boxes[idx + 1].setFocus()
            else:
                # Last digit — auto-verify if all boxes filled
                code = self.otp_code()
                if len(code) == 6 and code.isdigit() and self._auto_verify_enabled:
                    self._otp_status.setText("⏳  Verifying…")
                    self._auto_verify_enabled = False
                    QTimer.singleShot(120, self.sig_ok.emit)

    def _back(self, e, idx, orig):
        if e.key() == Qt.Key.Key_Backspace and not self._boxes[idx].text() and idx > 0:
            self._boxes[idx - 1].setFocus()
            self._auto_verify_enabled = True
        orig(e)


# ──────────────────────────────────────────────────────────────
#  CONTENT PAGES  (placeholder shown per nav key)
# ──────────────────────────────────────────────────────────────
class _ContentPage(QWidget):
    def __init__(self, title: str, icon: str = "📄"):
        super().__init__()
        self.setStyleSheet(f"background:{C['bg_white']};")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        il = QLabel(icon); il.setFont(F(38))
        il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.setStyleSheet("background:transparent;")
        lay.addWidget(il)

        tl = QLabel(title)
        tl.setFont(F(22, bold=True))
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setStyleSheet(f"color:{C['text']};background:transparent;")
        lay.addWidget(tl)

        sl = QLabel("This section is under construction.")
        sl.setFont(F(13)); sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.setStyleSheet(f"color:{C['text3']};background:transparent;")
        lay.addWidget(sl)


# ──────────────────────────────────────────────────────────────
#  DASHBOARD HOME PAGE
# ──────────────────────────────────────────────────────────────
class _DashboardPage(QWidget):
    """Dashboard home page with quick-access cards for every module."""

    _CARDS = [
        ("🧾", "New Sale",        "sale"),
        ("📦", "Products",        "product"),
        ("🚚", "Suppliers",       "suppliers"),
        ("🛒", "Purchase Orders", "purchase_orders"),
        ("⚠️",  "Low Stock",      "low_stock"),
        ("👥", "Customers",       "customers"),
        ("💳", "Credit Mgmt",     "credit"),
        ("💰", "P & L Summary",   "pl_summary"),
        ("💸", "Expenses",        "expenses"),
        ("🧾", "GST Breakdown",   "gst"),
        ("📊", "Day Book",        "day_book"),
        ("📤", "Export",          "export"),
    ]

    def __init__(self, navigate_cb, company_name: str = "", username: str = "",
                 parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C['bg_light']};")

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        root = QVBoxLayout(inner)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(24)

        # ── Welcome banner ─────────────────────────────────────
        banner = QFrame()
        banner.setFixedHeight(88)
        banner.setStyleSheet(
            f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {C['accent']},stop:1 {C['accent_dark']});"
            f"border-radius:14px;}}")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(28, 0, 28, 0)

        greet_col = QVBoxLayout(); greet_col.setSpacing(2)
        name_disp = company_name or "EvoAura"
        greet_col.addWidget(L(f"Welcome back, {username} 👋", 11, col="#ffd6db"))
        greet_col.addWidget(L(name_disp, 20, col="#ffffff", bold=True))
        bl.addLayout(greet_col)
        bl.addStretch()

        badge = QLabel("⚡ EvoAura")
        badge.setFont(F(13, bold=True))
        badge.setStyleSheet(
            "color:white;background:rgba(255,255,255,0.18);"
            "border-radius:10px;padding:5px 14px;")
        bl.addWidget(badge)
        root.addWidget(banner)

        # ── Section header ─────────────────────────────────────
        hdr = L("Quick Access", 13, col=C["text2"], bold=True)
        root.addWidget(hdr)

        # ── Cards grid ─────────────────────────────────────────
        grid_w = QWidget(); grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(14)
        grid.setContentsMargins(0, 0, 0, 0)

        cols = 4
        for i, (icon, label, key) in enumerate(self._CARDS):
            card = QPushButton()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setFixedHeight(90)
            card.setStyleSheet(f"""
                QPushButton {{
                    background:{C['bg_white']};
                    border:1px solid {C['border']};
                    border-radius:12px;
                    text-align:left;
                    padding:14px 16px;
                    font-size:13px;
                    color:{C['text']};
                    font-weight:600;
                }}
                QPushButton:hover {{
                    border:1.5px solid {C['accent']};
                    background:{C['accent_tint']};
                }}
                QPushButton:pressed {{
                    background:{C['accent_tint2']};
                }}
            """)

            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 10)
            card_lay.setSpacing(6)

            icon_lbl = QLabel(icon)
            icon_lbl.setFont(F(22))
            icon_lbl.setStyleSheet("background:transparent; border:none;")
            card_lay.addWidget(icon_lbl)

            name_lbl = QLabel(label)
            name_lbl.setFont(F(12, bold=True))
            name_lbl.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
            card_lay.addWidget(name_lbl)

            card.clicked.connect(lambda _=False, k=key: navigate_cb(k))
            grid.addWidget(card, i // cols, i % cols)

        root.addWidget(grid_w)
        root.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)


# ──────────────────────────────────────────────────────────────
#  PAGE REGISTRY
# ──────────────────────────────────────────────────────────────
_PAGE_META: dict[str, tuple[str, str]] = {
    "home":             ("🏠", "Dashboard"),
    "sale":             ("🛒", "New Sale"),
    "returns":          ("↩️", "Returns"),
    "bill_view":        ("🧾", "Bill View"),
    "product":          ("📦", "Products"),
    "products":         ("📦", "Products"),
    "purchase_orders":  ("📋", "Purchase Orders"),
    "suppliers":        ("🏭", "Suppliers"),
    "low_stock":        ("⚠️", "Low Stock"),
    "customers":        ("👥", "Customers"),
    "credit":           ("💳", "Credit Management"),
    "loyalty":          ("⭐", "Loyalty"),
    "pl_summary":       ("📊", "P & L Summary"),
    "expenses":         ("💸", "Expense Tracking"),
    "gst":              ("🧾", "GST Breakdown"),
    "cashflow":         ("💰", "Cash Flow"),
    "day_book":         ("📒", "Day Book"),
    "stock_report":     ("📈", "Stock Report"),
    "trial_balance":    ("⚖️", "Trial Balance"),
    "export":           ("📤", "Export"),
    "company_settings": ("🏢", "Company Settings"),
    "users":            ("👤", "Users & Roles"),
    "security":         ("🔐", "Security"),
    "audit_log":        ("🗂️", "Audit Log"),
}


# ──────────────────────────────────────────────────────────────
#  APP SHELL  (post-login: sidebar + topbar + content stack)
# ──────────────────────────────────────────────────────────────
class AppShell(QWidget):
    sig_logout = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C['bg_white']};")
        self._pages: dict[str, QWidget] = {}
        self._current_key = "home"

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = Sidebar(on_navigate=self._on_navigate)
        outer.addWidget(self._sidebar)

        right_col = QWidget()
        right_col.setStyleSheet(f"background:{C['bg_white']};")
        rc_lay = QVBoxLayout(right_col)
        rc_lay.setContentsMargins(0, 0, 0, 0)
        rc_lay.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────
        topbar = QWidget()
        topbar.setFixedHeight(52)
        topbar.setStyleSheet(
            f"background:{C['bg_white']};"
            f"border-bottom:1px solid {C['border']};")
        tbl = QHBoxLayout(topbar)
        tbl.setContentsMargins(16, 0, 20, 0)
        tbl.setSpacing(12)

        self._toggle_btn = QPushButton("☰")
        self._toggle_btn.setFixedSize(32, 32)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:1px solid {C['border']};
                border-radius:8px; font-size:16px; color:{C['text']};
            }}
            QPushButton:hover   {{ background:{C['hover_bg']}; }}
            QPushButton:pressed {{ background:{C['border']}; }}
        """)
        self._toggle_btn.clicked.connect(self._sidebar.toggle)
        tbl.addWidget(self._toggle_btn)

        self._page_title = QLabel("Home")
        self._page_title.setFont(F(14, bold=True))
        self._page_title.setStyleSheet(f"color:{C['text']};background:transparent;")
        tbl.addWidget(self._page_title)
        tbl.addStretch()

        self._avatar = QLabel("U")
        self._avatar.setFixedSize(30, 30)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setFont(F(11, bold=True))
        self._avatar.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {C['accent']},stop:1 {C['accent_dark']});"
            f"border-radius:15px;color:white;")
        tbl.addWidget(self._avatar)

        self._user_lbl = QLabel()
        self._user_lbl.setFont(F(12))
        self._user_lbl.setStyleSheet(f"color:{C['text2']};background:transparent;")
        tbl.addWidget(self._user_lbl)

        lo_btn = QPushButton("Sign Out")
        lo_btn.setFont(F(11))
        lo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        lo_btn.setStyleSheet(
            f"QPushButton{{color:{C['accent']};background:transparent;"
            f"border:1px solid {C['accent_border3']};border-radius:6px;padding:4px 14px;}}"
            f"QPushButton:hover{{background:{C['accent_tint']};}}")
        lo_btn.clicked.connect(self.sig_logout.emit)
        tbl.addWidget(lo_btn)

        rc_lay.addWidget(topbar)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{C['bg_white']};")
        rc_lay.addWidget(self._stack, 1)

        outer.addWidget(right_col, 1)

    def setup(self, username: str, db_name: str, users: int, sessions: int,
              company_name: str = ""):
        self._db_name = db_name          # ← stored for real page construction
        self._avatar.setText((username or "U")[0].upper())
        self._user_lbl.setText(username)

        # Push company name (from DB) into the sidebar brand row
        display = (company_name.strip() or
                   db_name.replace(".db", "").replace("_", " ").title())
        self._sidebar.set_company(display)

        self._username = username
        self._company_display = (company_name.strip() or
                                  db_name.replace(".db", "").replace("_", " ").title())

        home_page = _DashboardPage(
            navigate_cb  = self._show_page,
            company_name = self._company_display,
            username     = username,
        )
        self._pages["home"] = home_page
        self._stack.addWidget(home_page)
        self._sidebar.set_active("home")
        self._show_page("home")

    def _on_navigate(self, key: str):
        self._show_page(key)

    def _canonical_key(self, key: str) -> str:
        return "product" if key == "products" else key

    def _discard_page(self, key: str):
        page = self._pages.pop(key, None)
        if not page:
            return
        self._stack.removeWidget(page)
        page.deleteLater()

    def _show_page(self, key: str):
        key = self._canonical_key(key)
        self._current_key = key
        _, title = _PAGE_META.get(key, ("📄", key.replace("_", " ").title()))
        self._page_title.setText(title)

        if key != "home" and key in self._pages:
            self._discard_page(key)

        if key not in self._pages:
            page = self._build_page(key)
            self._pages[key] = page
            self._stack.addWidget(page)

        self._stack.setCurrentWidget(self._pages[key])
        self._sidebar.set_active(key)

    def _build_page(self, key: str) -> QWidget:
        """
        Returns the real widget for a nav key.
        Add more cases here as you build each module.
        Falls back to a placeholder _ContentPage for unbuilt sections.
        """
        db = getattr(self, "_db_name", "")

        # ── Real pages ────────────────────────────────────────
        if key in ("product", "products"):
            return ProductPage(db_name=db)

        if key == "suppliers":
            from supplier_page import SupplierPage
            return SupplierPage(db_name=db)

        # ── Placeholder for all other keys ────────────────────
        icon, title_text = _PAGE_META.get(key, ("📄", key.replace("_", " ").title()))
        return _ContentPage(title_text, icon)


# ──────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    I_ASKDB    = 0
    I_MASTER   = 1
    I_SETTINGS = 2
    I_SIGNUP   = 3
    I_QR       = 4
    I_LOGIN    = 5
    I_OTP      = 6

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EvoAura")
        self.resize(1160, 720)
        self.setMinimumSize(900, 580)
        self.setStyleSheet(APP_SS)

        self._db: DB | None = None
        self._db_path       = ""
        self._pending_user  = ""
        self._session_count = 0

        root = QWidget(); self.setCentralWidget(root)
        self._rl = QVBoxLayout(root)
        self._rl.setContentsMargins(0, 0, 0, 0)
        self._rl.setSpacing(0)

        self._split = QWidget()
        self._split.setStyleSheet(f"background:{C['bg_light']};")
        sl = QHBoxLayout(self._split)
        sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)

        # LEFT = context / info panel
        self.panel = RightPanel()
        sl.addWidget(self.panel, 1)

        # RIGHT = form stack
        self.stack = QStackedWidget(); self.stack.setMinimumWidth(380)
        sl.addWidget(self.stack, 1)

        self._v_ask      = V_AskDB();           self.stack.addWidget(self._v_ask)
        self._v_master   = V_MasterAuth();      self.stack.addWidget(self._v_master)
        self._v_settings = V_CompanySettings(); self.stack.addWidget(self._v_settings)
        self._v_signup   = V_Signup();          self.stack.addWidget(self._v_signup)
        self._v_qr       = V_QR();              self.stack.addWidget(self._v_qr)
        self._v_login    = V_Login();           self.stack.addWidget(self._v_login)
        self._v_otp      = V_OTP();             self.stack.addWidget(self._v_otp)

        self._shell = AppShell()
        self._shell.sig_logout.connect(self._logout)

        self._rl.addWidget(self._split)

        self._v_ask.sig.connect(self._on_db_name)
        self._v_master.sig_ok.connect(self._after_master)
        self._v_master.sig_toast.connect(self._toast)
        self._v_settings.sig_save.connect(self._after_settings)
        self._v_settings.sig_toast.connect(self._toast)
        self._v_signup.sig_ok.connect(self._after_signup)
        self._v_signup.sig_login.connect(self._go_login)
        self._v_signup.sig_toast.connect(self._toast)
        self._v_qr.sig_done.connect(self._go_login)
        self._v_login.sig_ok.connect(self._check_password)
        self._v_login.sig_signup.connect(self._go_signup_new_user)
        self._v_login.sig_toast.connect(self._toast)
        self._v_otp.sig_ok.connect(self._verify_otp)
        self._v_otp.sig_toast.connect(self._toast)

        self._boot()

    def _go_to(self, idx: int): self.stack.setCurrentIndex(idx)

    def _toast(self, msg: str, kind="info"):
        t = Toast(msg, kind, self); t.raise_(); t.show()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for c in self.findChildren(Toast):
            c.move(self.width() - 355, 16)

    def _open_db(self, path: str):
        if self._db: self._db.close()
        self._db = DB(path); self._db_path = path

    def _boot(self):
        for fname in sorted(os.listdir(".")):
            if not fname.endswith(".db"): continue
            try:
                db = DB(fname)
                if db.company_exists():
                    self._open_db(fname)
                    if db.users_exist():
                        self._go_login()
                    else:
                        self._go_signup_admin()
                    return
                db.close()
            except Exception:
                pass
        self._go_to(self.I_ASKDB)
        self.panel.show_features()

    def _on_db_name(self, db_name: str):
        if os.path.exists(db_name):
            try:
                self._open_db(db_name)
                co = self._db.get_company()
                if co:
                    if self._db.users_exist():
                        self._toast(f"Database '{db_name}' exists. Opening login.", "info")
                        self._go_login(); return
                    else:
                        self._toast("Database exists — no users yet. Go sign up.", "info")
                        self._go_signup_admin(); return
            except Exception as ex:
                self._toast(f"Could not open database: {ex}", "error"); return
        self._db_path = db_name
        self._v_master.set_db(db_name)
        self._go_to(self.I_MASTER)
        self.panel.show_master_hint()

    def _after_master(self):
        self._open_db(self._db_path)
        self._v_settings.prefill(self._db_path)
        self._go_to(self.I_SETTINGS)
        self.panel.show_features()

    def _after_settings(self):
        self._db.save_company(self._v_settings.get_data())
        self._go_signup_admin()

    def _go_signup_admin(self):
        """First-time: create the ADMIN account using master code."""
        self._v_signup.set_mode(is_first=True)
        self._v_signup.clear_fields()
        self._v_signup.set_db(self._db_path)
        self._go_to(self.I_SIGNUP)
        self.panel.show_signup_panel(self._db_path)

    def _go_signup_new_user(self):
        """From login page: create a regular user (admin TOTP required)."""
        if not self._db:
            self._toast("No database open.", "error"); return
        admin = self._db.get_admin()
        if not admin:
            self._toast("ADMIN account not found. Cannot add users.", "error"); return
        self._v_signup.set_mode(is_first=False, admin_totp_secret=admin["totp_secret"])
        self._v_signup.clear_fields()
        self._v_signup.set_db(self._db_path)
        self._go_to(self.I_SIGNUP)
        self.panel.show_signup_panel(self._db_path)

    def _after_signup(self, username: str, totp_secret: str, recovery_json: str, role: str):
        pw_hash = hash_pw(self._v_signup._pw.text())
        ok = self._db.create_user(username, pw_hash, totp_secret, recovery_json, role)
        if not ok:
            self._toast("Username already exists. Choose another.", "error"); return
        recovery = json.loads(recovery_json)
        self._v_qr.setup(username, totp_secret, recovery, self._db_path)
        self._go_to(self.I_QR)
        self.panel.show_features()

    def _go_login(self, _=None):
        users = self._db.list_usernames() if self._db else []
        self._v_login.clear_fields()
        self._v_login.set_db(self._db_path)
        self._v_login.refresh_users(users)
        self._go_to(self.I_LOGIN)
        self.panel.show_login_panel(users, self._db_path)

    def _check_password(self, username: str):
        pw   = self._v_login._pw.text()
        user = self._db.get_user(username) if self._db else None
        if not user:
            self._toast("User not found.", "error"); return
        if user["pw_hash"] != hash_pw(pw):
            self._toast("Incorrect password.", "error")
            self._v_login._pw.clear(); return
        self._pending_user = username
        self._v_otp.set_user(username)
        self._go_to(self.I_OTP)
        self.panel.show_otp_hint(username)

    def _verify_otp(self):
        otp  = self._v_otp.otp_code()
        rec  = self._v_otp.rec_code()
        user = self._db.get_user(self._pending_user) if self._db else None
        if not user:
            self._toast("User not found.", "error"); return
        verified = False
        if len(otp) == 6 and otp.isdigit():
            verified = pyotp.TOTP(user["totp_secret"]).verify(otp, valid_window=1)
        if not verified and rec:
            if self._db.consume_recovery(self._pending_user, rec):
                verified = True
                self._toast("Recovery code accepted. Code removed from list.", "warn")
        if not verified:
            self._v_otp._auto_verify_enabled = True   # re-enable for retry
            self._v_otp._otp_status.setText("❌  Invalid code — try again")
            self._toast("Invalid code. Try again.", "error"); return
        self._v_otp._otp_status.setText("✅  Verified!")
        self._session_count += 1
        self._toast(f"Welcome back, {self._pending_user}! 🎉", "success")
        QTimer.singleShot(450, self._open_shell)

    def _open_shell(self):
        self._split.setVisible(False)
        self._rl.removeWidget(self._split)
        co = self._db.get_company() if self._db else None
        company_name = (co.get("name", "").strip() if co else "") or \
                       self._db_path.replace(".db", "").replace("_", " ").title()
        self._shell.setup(
            username     = self._pending_user,
            db_name      = self._db_path,
            users        = len(self._db.list_usernames()),
            sessions     = self._session_count,
            company_name = company_name,
        )
        self._rl.addWidget(self._shell)
        self._shell.setVisible(True)

    def _logout(self):
        self._shell.setVisible(False)
        self._rl.removeWidget(self._shell)
        self._v_login.clear_fields()
        self._v_signup.clear_fields()
        self._pending_user = ""
        self._rl.addWidget(self._split)
        self._split.setVisible(True)
        self._go_login()

    def closeEvent(self, e):
        if self._db: self._db.close()
        super().closeEvent(e)


# ──────────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ensure_global_input_guard()
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C["bg_white"]))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C["input_bg"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(C["bg_light"]))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C["bg_light"]))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    win.showMaximized()
    sys.exit(app.exec())
