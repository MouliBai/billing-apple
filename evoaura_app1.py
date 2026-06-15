"""
EvoAura Desktop  —  PyQt6  |  SQLite  |  pyotp  |  qrcode
══════════════════════════════════════════════════════════════
EXACT BOOT FLOW:
  Start
    └─ DB file exists?
        ├─ NO  → AskDBName → MasterAuth → CompanySetup → Signup → QR → Login
        └─ YES → Users exist?
                  ├─ NO  → Signup → QR → Login
                  └─ YES → Login → OTP → Dashboard

Master TOTP secret: KRSXG5DSNFXGOIDB
Dependencies: PyQt6  pyotp  qrcode[pil]  Pillow
"""

import sys, os, sqlite3, hashlib, secrets, json, io, base64
import pyotp, qrcode
from PIL import Image

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QComboBox, QCheckBox, QFileDialog, QFrame,
    QSizePolicy, QScrollArea, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui  import QFont, QColor, QPalette, QPixmap, QImage

# ──────────────────────────────────────────────────────────────
#  MASTER SECRET  (update here to change for all views)
# ──────────────────────────────────────────────────────────────
MASTER_SECRET = "KRSXG5DSNFXGOIDB"

# ──────────────────────────────────────────────────────────────
#  DESIGN TOKENS
# ──────────────────────────────────────────────────────────────
C = dict(
    bg_dark  = "#FFFFFF",
    bg_mid   = "#F5F5F7",
    bg_panel = "#F2F2F7",
    accent   = "#FA2D48",
    accent2  = "#FA2D48",
    blue     = "#2980b9",
    success  = "#27ae60",
    warning  = "#e67e22",
    text     = "#1D1D1F",
    text2    = "#6E6E73",
    text3    = "#A1A1A6",
    input_bg = "#FFFFFF",
    border   = "#D2D2D7",
    card     = "#FAFAFA",
)

APP_SS = f"""
QWidget      {{ background:transparent; color:{C['text']};
               font-family:'-apple-system','Segoe UI',Arial,sans-serif; font-size:13px; }}
QScrollArea  {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{C['bg_mid']}; width:5px; border-radius:2px; }}
QScrollBar::handle:vertical {{ background:{C['text3']}; border-radius:2px; min-height:20px; }}
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
        self.con.commit()

    # company ──────────────────────────────────────────────────
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

    # users ────────────────────────────────────────────────────
    def users_exist(self) -> bool:
        r = self.con.execute("SELECT id FROM users LIMIT 1").fetchone()
        return r is not None

    def create_user(self, username, pw_hash, totp_secret, recovery_json) -> bool:
        try:
            self.con.execute(
                "INSERT INTO users (username,pw_hash,totp_secret,recovery_json) "
                "VALUES (?,?,?,?)", (username, pw_hash, totp_secret, recovery_json))
            self.con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

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
    w.setStyleSheet("background:transparent;"); return w

def hline() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{C['border']};background:{C['border']};max-height:1px;"); return f

def card_style(hover=False) -> str:
    base = f"background:{C['card']};border:1px solid {C['border']};border-radius:10px;"
    hover_s = f" background:rgba(250,45,72,0.04);border:1px solid rgba(250,45,72,0.25);"
    return base + (hover_s if hover else "")


# ──────────────────────────────────────────────────────────────
#  TOAST
# ──────────────────────────────────────────────────────────────
class Toast(QLabel):
    _P = {"success":("#27ae60","✓"), "error":("#FA2D48","✕"), "info":("#2980b9","ℹ"), "warn":("#e67e22","⚠")}
    def __init__(self, msg: str, kind="info", parent=None):
        super().__init__(parent)
        col, icon = self._P.get(kind, self._P["info"])
        self.setText(f"  {icon}   {msg}  ")
        self.setFont(F(12))
        self.setStyleSheet(f"QLabel{{background:#FFFFFF;border:1.5px solid {col};"
                           f"border-radius:10px;padding:10px 16px;color:{C['text']};"
                           f"box-shadow: 0 2px 12px rgba(0,0,0,0.08);}}")
        self.setFixedWidth(340); self.adjustSize()
        if parent:
            self.move(parent.width()-355, 16); self.raise_(); self.show()
        QTimer.singleShot(3500, self.deleteLater)


# ──────────────────────────────────────────────────────────────
#  STYLED INPUT
# ──────────────────────────────────────────────────────────────
class SI(QWidget):
    """Styled dark input with optional label, icon, password mode."""
    returnPressed = pyqtSignal()

    def __init__(self, label="", icon="", ph="", pw=False, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        v = QVBoxLayout(self); v.setContentsMargins(0,0,0,0); v.setSpacing(4)

        self._lbl = None
        if label:
            self._lbl = QLabel(label.upper())
            self._lbl.setFont(F(9, bold=True))
            self._lbl.setStyleSheet(f"color:{C['text2']};letter-spacing:1.2px;background:transparent;")
            v.addWidget(self._lbl)

        self._box = QWidget()
        self._box.setStyleSheet(self._bs(False))
        rl = QHBoxLayout(self._box); rl.setContentsMargins(10,0,8,0); rl.setSpacing(6)

        if icon:
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;border:none;")
            il.setFixedWidth(22); rl.addWidget(il)

        self.field = QLineEdit()
        self.field.setPlaceholderText(ph)
        self.field.setFont(F(13))
        if pw: self.field.setEchoMode(QLineEdit.EchoMode.Password)
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
        return f"QWidget{{background:{C['input_bg']};border:1.5px solid {c};border-radius:10px;}}"

    def _fin(self, e):
        self._box.setStyleSheet(self._bs(True))
        if self._lbl: self._lbl.setStyleSheet(
            f"color:{C['accent']};letter-spacing:1.2px;background:transparent;")
        QLineEdit.focusInEvent(self.field, e)

    def _fout(self, e):
        self._box.setStyleSheet(self._bs(False))
        if self._lbl: self._lbl.setStyleSheet(
            f"color:{C['text2']};letter-spacing:1.2px;background:transparent;")
        QLineEdit.focusOutEvent(self.field, e)

    def text(self)   -> str:  return self.field.text()
    def clear(self):          self.field.clear()
    def set_pw(self, show):
        self.field.setEchoMode(
            QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password)


# ──────────────────────────────────────────────────────────────
#  GRADIENT BUTTON
# ──────────────────────────────────────────────────────────────
class GB(QPushButton):
    _G = {"primary":("FA2D48","C81F36"), "secondary":("6E6E73","4a4a4f"),
          "success":("27ae60","1e8449"), "warn":("e67e22","ca6f1e")}
    def __init__(self, text, v="primary", full=False, sm=False, parent=None):
        super().__init__(text, parent)
        c1,c2 = self._G.get(v, self._G["primary"])
        p = "6px 14px" if sm else "11px 26px"
        sz = 11 if sm else 13
        self.setFont(F(sz, bold=True))
        if full: self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QPushButton {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #{c1},stop:1 #{c2});
                border:none; border-radius:10px; color:white; padding:{p}; letter-spacing:0.3px;
            }}
            QPushButton:hover  {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #{c2},stop:1 #{c1}); }}
            QPushButton:pressed{{ opacity:0.8; }}
            QPushButton:disabled{{ background:{C['border']}; color:{C['text3']}; }}
        """)


# ──────────────────────────────────────────────────────────────
#  RIGHT PANEL  (context-aware)
# ──────────────────────────────────────────────────────────────
class RightPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background:{C['bg_panel']};")

        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        sc.setStyleSheet("background:transparent;border:none;")
        self._inner = QWidget(); self._inner.setStyleSheet("background:transparent;")
        self._vl = QVBoxLayout(self._inner)
        self._vl.setContentsMargins(34,42,34,34); self._vl.setSpacing(0)

        self._build_brand()
        self._vl.addWidget(gap(20)); self._vl.addWidget(hline()); self._vl.addWidget(gap(18))

        # dynamic section
        self._dyn = QWidget(); self._dyn.setStyleSheet("background:transparent;")
        self._dl  = QVBoxLayout(self._dyn)
        self._dl.setContentsMargins(0,0,0,0); self._dl.setSpacing(0)
        self._vl.addWidget(self._dyn); self._vl.addStretch()

        # footer
        self._vl.addWidget(gap(16))
        fl = QHBoxLayout(); fl.setSpacing(12)
        for t in ["Privacy","Terms","Support"]:
            b = QPushButton(t)
            b.setStyleSheet(f"QPushButton{{color:{C['text3']};background:transparent;border:none;font-size:10px;}}"
                            f"QPushButton:hover{{color:{C['accent']};}}")
            fl.addWidget(b)
        fl.addStretch(); self._vl.addLayout(fl)
        sc.setWidget(self._inner); outer.addWidget(sc)

        self.show_features()

    def _build_brand(self):
        badge = QLabel("⚡  EVO AURA")
        badge.setFont(F(13, bold=True))
        badge.setStyleSheet(f"color:{C['accent']};background:rgba(250,45,72,0.08);"
                            f"border:1px solid rgba(250,45,72,0.22);border-radius:16px;"
                            f"padding:5px 16px;letter-spacing:2px;")
        badge.setFixedWidth(154); self._vl.addWidget(badge); self._vl.addWidget(gap(20))
        h = QLabel("The future of\nbusiness management")
        h.setFont(F(20, bold=True))
        h.setStyleSheet(f"color:{C['text']};background:transparent;"); h.setWordWrap(True)
        self._vl.addWidget(h); self._vl.addWidget(gap(10))
        d = L("EvoAura — secure authentication, real-time analytics, "
              "and powerful company tooling in one elegant platform.",
              sz=11, col=C["text2"]); self._vl.addWidget(d)

    def _clear(self):
        while self._dl.count():
            it = self._dl.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    # ── public context methods ────────────────────────────────
    def show_features(self):
        self._clear()
        for icon, title, desc in [
            ("🔐","Bank-grade Security","TOTP 2FA with pyotp — real-time verified"),
            ("⚡","Lightning Fast","SQLite local storage — instant response"),
            ("📊","Smart Dashboard","Real-time stats & business intelligence"),
            ("🏢","Multi-tenant","Multiple company DBs from one install"),
        ]:
            c = QWidget()
            c.setStyleSheet(f"QWidget{{background:#FFFFFF;"
                            f"border:1px solid {C['border']};border-radius:10px;}}")
            cl = QHBoxLayout(c); cl.setContentsMargins(12,10,12,10); cl.setSpacing(10)
            il = QLabel(icon); il.setFont(F(16))
            il.setStyleSheet("background:transparent;border:none;"); il.setFixedWidth(26)
            cl.addWidget(il, alignment=Qt.AlignmentFlag.AlignTop)
            tw = QWidget(); tw.setStyleSheet("background:transparent;border:none;")
            tl = QVBoxLayout(tw); tl.setContentsMargins(0,0,0,0); tl.setSpacing(2)
            tl.addWidget(L(title,sz=11,bold=True)); tl.addWidget(L(desc,sz=10,col=C["text2"]))
            cl.addWidget(tw)
            self._dl.addWidget(c); self._dl.addWidget(gap(8))

    def show_login_panel(self, usernames: list, db_name: str):
        self._clear()
        self._dl.addWidget(L("Registered Users", sz=11, bold=True, col=C["text2"]))
        self._dl.addWidget(gap(4))
        if db_name:
            db_l = QLabel(f"📂  {db_name}")
            db_l.setFont(F(10, mono=True))
            db_l.setStyleSheet(f"color:{C['accent2']};background:transparent;")
            self._dl.addWidget(db_l); self._dl.addWidget(gap(10))
        if not usernames:
            self._dl.addWidget(L("No users yet — sign up first.", sz=11, col=C["text3"]))
        for u in usernames:
            row = QWidget()
            row.setStyleSheet(f"QWidget{{background:#FFFFFF;"
                              f"border:1px solid {C['border']};border-radius:8px;}}")
            rl = QHBoxLayout(row); rl.setContentsMargins(10,7,10,7); rl.setSpacing(10)
            av = QLabel(u[0].upper()); av.setFixedSize(28,28)
            av.setAlignment(Qt.AlignmentFlag.AlignCenter); av.setFont(F(11, bold=True))
            av.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                             "stop:0 #FA2D48,stop:1 #C81F36);border-radius:14px;color:white;")
            rl.addWidget(av); rl.addWidget(L(u, sz=12)); rl.addStretch()
            self._dl.addWidget(row); self._dl.addWidget(gap(6))

    def show_signup_panel(self, db_name: str):
        self._clear()
        if db_name:
            self._dl.addWidget(L("Joining Workspace", sz=11, bold=True, col=C["text2"]))
            self._dl.addWidget(gap(4))
            ws = QLabel(f"📂  {db_name}"); ws.setFont(F(11, mono=True))
            ws.setStyleSheet(f"color:{C['accent2']};background:transparent;")
            self._dl.addWidget(ws); self._dl.addWidget(gap(16))
        for icon, tip in [
            ("🔒","Use a strong password — 12+ characters"),
            ("📱","Install Google Authenticator or Authy first"),
            ("💾","Store your 8 recovery codes somewhere safe"),
            ("🛡️","Master code comes from your authenticator"),
        ]:
            row = QHBoxLayout(); row.setSpacing(10)
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;"); il.setFixedWidth(24)
            row.addWidget(il); row.addWidget(L(tip, sz=11, col=C["text2"])); row.addStretch()
            cw = QWidget(); cw.setStyleSheet("background:transparent;"); cw.setLayout(row)
            self._dl.addWidget(cw); self._dl.addWidget(gap(9))

    def show_master_hint(self):
        self._clear()
        self._dl.addWidget(L("Master TOTP Setup", sz=11, bold=True, col=C["text2"]))
        self._dl.addWidget(gap(10))
        steps = [
            ("1️⃣","Open Google Authenticator or Authy"),
            ("2️⃣","Tap  +  → Enter setup key manually"),
            ("3️⃣",f"Account:  EvoAura Master"),
            ("4️⃣",f"Key:  {MASTER_SECRET}"),
            ("5️⃣","Type TOTP  = Base32, no time limit"),
            ("6️⃣","Enter the 6-digit code shown"),
        ]
        for icon, tip in steps:
            row = QHBoxLayout(); row.setSpacing(10)
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;"); il.setFixedWidth(26)
            tl = L(tip, sz=11, col=C["text2"]); tl.setWordWrap(True)
            row.addWidget(il); row.addWidget(tl, 1); row.addStretch()
            cw = QWidget(); cw.setStyleSheet("background:transparent;"); cw.setLayout(row)
            self._dl.addWidget(cw); self._dl.addWidget(gap(8))
        # Secret box
        sb = QLabel(MASTER_SECRET); sb.setFont(F(11, mono=True))
        sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb.setStyleSheet(f"background:#FAFAFA;border:1px solid {C['border']};"
                         f"border-radius:8px;padding:8px;color:{C['accent']};letter-spacing:2px;")
        self._dl.addWidget(gap(4)); self._dl.addWidget(sb)

    def show_otp_hint(self, username: str):
        self._clear()
        self._dl.addWidget(L("Verifying 2FA", sz=11, bold=True, col=C["text2"]))
        self._dl.addWidget(gap(8))
        for icon, tip in [
            ("📱","Open your authenticator app"),
            ("🔍",f"Find the entry for  {username}"),
            ("⌨️","Enter the current 6-digit code"),
            ("⏱️","Codes refresh every 30 seconds"),
            ("🆘","No phone? use a recovery code instead"),
        ]:
            row = QHBoxLayout(); row.setSpacing(10)
            il = QLabel(icon); il.setFont(F(14))
            il.setStyleSheet("background:transparent;"); il.setFixedWidth(24)
            row.addWidget(il); row.addWidget(L(tip, sz=11, col=C["text2"])); row.addStretch()
            cw = QWidget(); cw.setStyleSheet("background:transparent;"); cw.setLayout(row)
            self._dl.addWidget(cw); self._dl.addWidget(gap(8))


# ──────────────────────────────────────────────────────────────
#  LEFT VIEW BASE  (scrollable dark panel)
# ──────────────────────────────────────────────────────────────
class LV(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"background:{C['bg_mid']};border:none;")
        self._w = QWidget(); self._w.setStyleSheet(f"background:{C['bg_mid']};")
        self._l = QVBoxLayout(self._w)
        self._l.setContentsMargins(50,46,50,46); self._l.setSpacing(0)
        self.setWidget(self._w); self.setMinimumWidth(380)

    @property
    def vl(self): return self._l


# ──────────────────────────────────────────────────────────────
#  VIEW 0  —  AskDBName
# ──────────────────────────────────────────────────────────────
class V_AskDB(LV):
    sig = pyqtSignal(str)   # db file path

    def __init__(self):
        super().__init__()
        vl = self.vl

        # step dots ───────────────────────────────────────────
        row = QHBoxLayout(); row.setSpacing(8)
        for n in range(1,4):
            d = QLabel(str(n)); d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setFixedSize(26,26); d.setFont(F(10, bold=True))
            if n==1: d.setStyleSheet(f"background:{C['accent']};border-radius:13px;color:white;")
            else:    d.setStyleSheet(f"background:{C['bg_mid']};"
                                     f"border:1px solid {C['border']};border-radius:13px;color:{C['text3']};")
            row.addWidget(d)
            if n<3:
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedWidth(22)
                sep.setStyleSheet(f"color:{C['border']};background:{C['border']};max-height:1px;")
                row.addWidget(sep)
        row.addStretch(); vl.addLayout(row); vl.addWidget(gap(28))

        vl.addWidget(L("Set up your workspace", sz=22, bold=True))
        vl.addWidget(gap(8))
        vl.addWidget(L("Enter your company name to create a secure local database.\n"
                        "This becomes your workspace identifier.", sz=13, col=C["text2"]))
        vl.addWidget(gap(28))

        self._inp = SI("Company / Database Name","🏢","e.g. TechCorp, MyShop, Acme")
        self._inp.returnPressed.connect(self._submit)
        vl.addWidget(self._inp); vl.addWidget(gap(6))
        self._hint = L("", sz=11, col=C["text3"]); vl.addWidget(self._hint)
        self._inp.field.textChanged.connect(
            lambda t: self._hint.setText(
                f"Will create:  {t.strip().replace(' ','_')}.db" if t.strip() else ""))
        vl.addWidget(gap(24))

        btn = GB("Continue  →", full=True); btn.clicked.connect(self._submit)
        vl.addWidget(btn); vl.addStretch()

    def _submit(self):
        raw = self._inp.text().strip().replace(" ","_")
        if not raw: return
        self.sig.emit(raw if raw.endswith(".db") else f"{raw}.db")


# ──────────────────────────────────────────────────────────────
#  VIEW 1  —  MasterAuth  (verify TOTP before creating DB)
# ──────────────────────────────────────────────────────────────
class V_MasterAuth(LV):
    sig_ok    = pyqtSignal()
    sig_toast = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        vl = self.vl

        icon = QLabel("🔐"); icon.setFont(F(26))
        icon.setFixedSize(56,56); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background:rgba(250,45,72,0.08);"
                           "border:2px solid rgba(250,45,72,0.22);border-radius:28px;")
        vl.addWidget(icon); vl.addWidget(gap(18))

        vl.addWidget(L("Security Verification", sz=22, bold=True)); vl.addWidget(gap(8))
        self._desc = L("Enter your 6-digit master TOTP code to authorize\ncreation of this database.",
                        sz=13, col=C["text2"]); vl.addWidget(self._desc); vl.addWidget(gap(26))

        self._code = SI("Master TOTP Code","🔑","6-digit code from authenticator", pw=True)
        self._code.returnPressed.connect(self._verify)
        vl.addWidget(self._code); vl.addWidget(gap(24))

        btn = GB("Verify & Create Database", full=True); btn.clicked.connect(self._verify)
        vl.addWidget(btn); vl.addWidget(gap(14))
        vl.addWidget(L(f"Secret for Google Authenticator:  {MASTER_SECRET}",
                        sz=10, col=C["text3"])); vl.addStretch()

    def set_db(self, db): self._desc.setText(
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

        vl.addWidget(L("🏢  Company Settings", sz=21, bold=True)); vl.addWidget(gap(6))
        vl.addWidget(L("Configure your company profile and branding.", sz=13, col=C["text2"]))
        vl.addWidget(gap(20))

        # logo card ──────────────────────────────────────────
        logo_card = QWidget()
        logo_card.setStyleSheet(f"QWidget{{background:{C['bg_mid']};"
                                f"border:1.5px dashed {C['border']};border-radius:12px;}}")
        lcl = QHBoxLayout(logo_card); lcl.setContentsMargins(14,14,14,14); lcl.setSpacing(14)
        self._logo_lbl = QLabel("🏢"); self._logo_lbl.setFont(F(22))
        self._logo_lbl.setFixedSize(68,68); self._logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_lbl.setStyleSheet(f"background:{C['border']};"
                                     f"border:1px solid {C['border']};border-radius:8px;")
        lcl.addWidget(self._logo_lbl)
        col_w = QWidget(); col_w.setStyleSheet("background:transparent;border:none;")
        cl2 = QVBoxLayout(col_w); cl2.setContentsMargins(0,0,0,0); cl2.setSpacing(8)
        cl2.addWidget(L("Company Logo", sz=12, bold=True))
        br = QHBoxLayout(); br.setSpacing(8)
        up = GB("Upload","secondary",sm=True); up.clicked.connect(self._upload)
        self._rm = GB("Remove","primary",sm=True); self._rm.clicked.connect(self._remove)
        self._rm.setVisible(False)
        br.addWidget(up); br.addWidget(self._rm); br.addStretch()
        cl2.addLayout(br); lcl.addWidget(col_w)
        vl.addWidget(logo_card); vl.addWidget(gap(16))

        self._cname = SI("Company Name","🏢","Your company name")
        self._phone = SI("Phone","📞","+91 98765 43210")
        self._addr  = SI("Address","📍","123 Business St, City")
        self._gst   = SI("GST Number","🧾","22AAAAA0000A1Z5")
        for w in [self._cname, self._phone, self._addr, self._gst]:
            vl.addWidget(w); vl.addWidget(gap(10))

        vl.addWidget(L("FOOTER MESSAGE", sz=9, col=C["text2"])); vl.addWidget(gap(4))
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
        self._cname.field.setText(db_name.replace(".db","").replace("_"," ").title())

    def _upload(self):
        p,_ = QFileDialog.getOpenFileName(self,"Select Logo","","Images (*.png *.jpg *.jpeg *.webp)")
        if not p: return
        with open(p,"rb") as f: raw = f.read()
        self._logo_b64 = base64.b64encode(raw).decode()
        pix = QPixmap(p).scaled(68,68,Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
        self._logo_lbl.setPixmap(pix); self._logo_lbl.setText("")
        self._rm.setVisible(True)

    def _remove(self):
        self._logo_b64 = ""
        self._logo_lbl.clear(); self._logo_lbl.setText("🏢")
        self._rm.setVisible(False)

    def get_data(self) -> dict:
        return dict(name=self._cname.text(), phone=self._phone.text(),
                    address=self._addr.text(), gst=self._gst.text(),
                    footer=self._footer.toPlainText(), logo_b64=self._logo_b64)

    def _save(self):
        if not self._cname.text().strip():
            self.sig_toast.emit("Company name is required.", "error"); return
        self.sig_toast.emit("Company settings saved!", "success")
        QTimer.singleShot(350, self.sig_save.emit)


# ──────────────────────────────────────────────────────────────
#  VIEW 3  —  Signup
# ──────────────────────────────────────────────────────────────
class V_Signup(LV):
    sig_ok    = pyqtSignal(str, str, str)  # username, totp_secret, recovery_json
    sig_login = pyqtSignal()
    sig_toast = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        vl = self.vl

        vl.addWidget(L("Create Account", sz=22, bold=True)); vl.addWidget(gap(6))
        self._ws = L("", sz=12, col=C["text2"]); vl.addWidget(self._ws); vl.addWidget(gap(24))

        self._un  = SI("Username",        "👤","Choose a username")
        self._pw  = SI("Password",        "🔒","Strong password",           pw=True)
        self._cpw = SI("Confirm Password","🔒","Repeat password",            pw=True)
        self._ms  = SI("Master Code",     "🛡️","6-digit master TOTP code",  pw=True)
        self._ms.returnPressed.connect(self._create)

        for w in [self._un, self._pw, self._cpw]:
            vl.addWidget(w); vl.addWidget(gap(10))

        # strength bar ────────────────────────────────────────
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
        vl.addWidget(chk); vl.addWidget(gap(8)); vl.addWidget(hline()); vl.addWidget(gap(10))
        vl.addWidget(self._ms); vl.addWidget(gap(22))

        btn = GB("Create Account", full=True); btn.clicked.connect(self._create)
        vl.addWidget(btn); vl.addWidget(gap(16))

        fl = QHBoxLayout(); fl.addStretch()
        fl.addWidget(L("Already have an account? ", sz=12, col=C["text2"]))
        si_btn = QPushButton("Sign in →")
        si_btn.setStyleSheet(f"color:{C['accent']};background:transparent;border:none;"
                              "font-size:12px;font-weight:600;")
        si_btn.clicked.connect(self.sig_login.emit); fl.addWidget(si_btn); fl.addStretch()
        vl.addLayout(fl); vl.addStretch()

    def set_db(self, db: str): self._ws.setText(f"Joining workspace:  {db}")

    def _strength(self, t: str):
        n = len(t)
        if not n: self._slab.setText(""); self._bar.setFixedWidth(0); return
        col = C["success"] if n>10 else (C["accent2"] if n>6 else C["accent"])
        txt = "Strong ✓" if n>10 else ("Medium" if n>6 else "Weak")
        self._slab.setText(f"Strength:  {txt}")
        self._bar.setStyleSheet(f"background:{col};border-radius:2px;")
        self._bar.setFixedWidth(int(self._bbg.width() * min(100, n*9) / 100))

    def resizeEvent(self,e): super().resizeEvent(e); self._strength(self._pw.text())

    def _create(self):
        u  = self._un.text().strip()
        pw = self._pw.text()
        cp = self._cpw.text()
        ms = self._ms.text().strip()
        if not all([u, pw, cp, ms]):
            self.sig_toast.emit("Please fill in all fields.", "error"); return
        if pw != cp:
            self.sig_toast.emit("Passwords do not match.", "error"); return
        if len(ms) != 6 or not ms.isdigit():
            self.sig_toast.emit("Master code must be exactly 6 digits.", "error"); return
        if not verify_master(ms):
            self.sig_toast.emit("Invalid master code.", "error"); self._ms.clear(); return

        secret   = pyotp.random_base32()
        recovery = gen_recovery(8)
        self.sig_toast.emit("Account created! Now scan your QR code.", "success")
        QTimer.singleShot(350, lambda: self.sig_ok.emit(u, secret, json.dumps(recovery)))


# ──────────────────────────────────────────────────────────────
#  VIEW 4  —  QRDisplay
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
                       align=Qt.AlignmentFlag.AlignCenter); vl.addWidget(self._sub)
        vl.addWidget(gap(20))

        self._qr_lbl = QLabel(); self._qr_lbl.setFixedSize(190,190)
        self._qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_lbl.setStyleSheet("background:white;border-radius:10px;")
        vl.addWidget(self._qr_lbl, alignment=Qt.AlignmentFlag.AlignCenter); vl.addWidget(gap(14))

        self._sec_lbl = QLabel(); self._sec_lbl.setFont(F(11, mono=True))
        self._sec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sec_lbl.setStyleSheet(
            f"background:{C['bg_mid']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:8px 14px;color:{C['accent']};letter-spacing:2px;")
        vl.addWidget(self._sec_lbl); vl.addWidget(gap(20))

        vl.addWidget(L("Recovery Codes — save all 8 before continuing",
                        sz=11, bold=True, col=C["text2"])); vl.addWidget(gap(8))
        self._cgrid = QWidget(); self._cgrid.setStyleSheet("background:transparent;")
        self._cgl   = QGridLayout(self._cgrid); self._cgl.setSpacing(7)
        vl.addWidget(self._cgrid); vl.addWidget(gap(22))

        btn = GB("✓  I've saved my codes — Continue","success",full=True)
        btn.clicked.connect(self.sig_done.emit)
        vl.addWidget(btn); vl.addStretch()

    def setup(self, username: str, totp_secret: str, recovery: list, db_name: str):
        self._sub.setText(f"Setting up 2FA for  {username}")
        self._sec_lbl.setText(totp_secret)
        self._qr_lbl.setPixmap(totp_uri_pixmap(totp_secret, username,
                                               f"EvoAura/{db_name}", 190))
        while self._cgl.count():
            it = self._cgl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        for i, code in enumerate(recovery):
            cl = QLabel(code); cl.setFont(F(10, mono=True))
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setStyleSheet(
                f"background:{C['bg_mid']};border:1px solid {C['border']};"
                f"border-radius:6px;padding:5px 10px;color:{C['text']};")
            self._cgl.addWidget(cl, i//2, i%2)


# ──────────────────────────────────────────────────────────────
#  VIEW 5  —  Login
# ──────────────────────────────────────────────────────────────
class V_Login(LV):
    sig_ok     = pyqtSignal(str)   # username
    sig_signup = pyqtSignal()
    sig_toast  = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        vl = self.vl

        badge = QLabel("WELCOME"); badge.setFont(F(9, bold=True))
        badge.setStyleSheet(
            f"color:{C['accent']};background:rgba(250,45,72,0.08);"
            f"border:1px solid rgba(250,45,72,0.22);border-radius:14px;"
            f"padding:4px 14px;letter-spacing:1.8px;")
        badge.setFixedWidth(110); vl.addWidget(badge); vl.addWidget(gap(14))

        vl.addWidget(L("Sign In", sz=24, bold=True)); vl.addWidget(gap(6))
        self._ws = L("", sz=12, col=C["text2"]); vl.addWidget(self._ws); vl.addWidget(gap(24))

        vl.addWidget(L("USERNAME", sz=9, col=C["text2"])); vl.addWidget(gap(4))
        self._combo = QComboBox(); self._combo.setFont(F(13))
        self._combo.setStyleSheet(f"""
            QComboBox {{background:{C['input_bg']};border:1.5px solid {C['border']};
                border-radius:10px;padding:9px 14px;color:{C['text']};min-height:20px;}}
            QComboBox::drop-down {{border:none;width:26px;}}
            QComboBox QAbstractItemView {{background:{C['bg_dark']};border:1px solid {C['border']};
                color:{C['text']};selection-background-color:rgba(250,45,72,0.12);}}""")
        vl.addWidget(self._combo); vl.addWidget(gap(12))

        self._pw = SI("Password","🔒","Enter your password", pw=True)
        self._pw.returnPressed.connect(self._login)
        vl.addWidget(self._pw); vl.addWidget(gap(14))

        notice = QWidget()
        notice.setStyleSheet("QWidget{background:rgba(41,128,185,0.08);"
                             "border:1px solid rgba(41,128,185,0.22);border-radius:10px;}")
        nl = QHBoxLayout(notice); nl.setContentsMargins(12,9,12,9); nl.setSpacing(10)
        nl.addWidget(L("A 2FA code will be required after login.",
                                                     sz=11, col="#2980b9"))
        vl.addWidget(notice); vl.addWidget(gap(20))

        btn = GB("Sign In", full=True); btn.clicked.connect(self._login)
        vl.addWidget(btn); vl.addWidget(gap(16))

        fl = QHBoxLayout(); fl.addStretch()
        fl.addWidget(L("New user? ", sz=12, col=C["text2"]))
        nb = QPushButton("Create account →")
        nb.setStyleSheet(f"color:{C['accent']};background:transparent;border:none;"
                          "font-size:12px;font-weight:600;")
        nb.clicked.connect(self.sig_signup.emit); fl.addWidget(nb); fl.addStretch()
        vl.addLayout(fl); vl.addStretch()

    def set_db(self, db: str): self._ws.setText(f"Workspace:  {db}")

    def refresh_users(self, users: list):
        self._combo.clear()
        self._combo.addItem("👤  Select user")
        for u in users: self._combo.addItem(u)

    def _login(self):
        u  = self._combo.currentText()
        pw = self._pw.text()
        if u.startswith("—") or not pw:
            self.sig_toast.emit("Select a user and enter your password.", "error"); return
        self.sig_ok.emit(u)   # pw validation in MainWindow


# ──────────────────────────────────────────────────────────────
#  VIEW 6  —  OTP Verify
# ──────────────────────────────────────────────────────────────
class V_OTP(LV):
    sig_ok    = pyqtSignal()
    sig_toast = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._username = ""
        vl = self.vl

        shield = QLabel("🛡️"); shield.setFont(F(26))
        shield.setFixedSize(66,66); shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield.setStyleSheet("background:rgba(250,45,72,0.08);"
                             "border:2px solid rgba(250,45,72,0.22);border-radius:33px;")
        vl.addWidget(shield, alignment=Qt.AlignmentFlag.AlignCenter); vl.addWidget(gap(16))

        vl.addWidget(L("Two-Factor Auth", sz=22, bold=True,
                        align=Qt.AlignmentFlag.AlignCenter)); vl.addWidget(gap(8))
        self._desc = L("", sz=12, col=C["text2"],
                        align=Qt.AlignmentFlag.AlignCenter); vl.addWidget(self._desc)
        vl.addWidget(gap(26))

        # 6 digit boxes ───────────────────────────────────────
        brow = QHBoxLayout(); brow.setSpacing(8); brow.addStretch()
        self._boxes: list[QLineEdit] = []
        for i in range(6):
            b = QLineEdit(); b.setMaxLength(1); b.setFixedSize(44,50)
            b.setAlignment(Qt.AlignmentFlag.AlignCenter); b.setFont(F(20,bold=True,mono=True))
            b.setStyleSheet(
                f"QLineEdit{{background:{C['input_bg']};border:1.5px solid {C['border']};"
                f"border-radius:8px;color:{C['text']};}}"
                f"QLineEdit:focus{{border:1.5px solid {C['accent']};}}")
            b.textChanged.connect(lambda t, idx=i: self._adv(idx, t))
            b.keyPressEvent = lambda e, idx=i, orig=b.keyPressEvent: self._back(e, idx, orig)
            self._boxes.append(b); brow.addWidget(b)
        brow.addStretch()
        bw = QWidget(); bw.setStyleSheet("background:transparent;"); bw.setLayout(brow)
        vl.addWidget(bw); vl.addWidget(gap(10))

        vl.addWidget(L("— or enter a recovery code —", sz=10, col=C["text3"],
                        align=Qt.AlignmentFlag.AlignCenter)); vl.addWidget(gap(8))
        self._rec = SI(ph="Recovery code  (e.g. AB12CD34)")
        vl.addWidget(self._rec); vl.addWidget(gap(22))

        btn = GB("Verify", full=True); btn.clicked.connect(self.sig_ok.emit)
        vl.addWidget(btn); vl.addStretch()

    def set_user(self, u: str):
        self._username = u
        self._desc.setText(f"Open your authenticator app and enter\nthe 6-digit code for  {u}")
        for b in self._boxes: b.clear()
        self._rec.clear()
        self._boxes[0].setFocus()

    def otp_code(self) -> str: return "".join(b.text() for b in self._boxes)
    def rec_code(self) -> str: return self._rec.text().strip().upper()

    def _adv(self, idx, t):
        if t and idx < 5: self._boxes[idx+1].setFocus()

    def _back(self, e, idx, orig):
        if e.key() == Qt.Key.Key_Backspace and not self._boxes[idx].text() and idx > 0:
            self._boxes[idx-1].setFocus()
        orig(e)


# ──────────────────────────────────────────────────────────────
#  VIEW 7  —  Dashboard
# ──────────────────────────────────────────────────────────────
class V_Dashboard(QWidget):
    sig_logout = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C['bg_dark']};")
        ml = QVBoxLayout(self); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)

        # navbar ───────────────────────────────────────────────
        nav = QWidget(); nav.setFixedHeight(54)
        nav.setStyleSheet(f"background:{C['bg_dark']};"
                          f"border-bottom:1px solid {C['border']};")
        nl = QHBoxLayout(nav); nl.setContentsMargins(28,0,28,0); nl.setSpacing(12)
        brand = QLabel("⚡  EVO AURA"); brand.setFont(F(13, bold=True))
        brand.setStyleSheet(f"color:{C['accent']};background:transparent;letter-spacing:2px;")
        nl.addWidget(brand)
        self._db_badge = QLabel(); self._db_badge.setFont(F(10))
        self._db_badge.setStyleSheet(
            f"color:{C['accent']};background:rgba(250,45,72,0.08);"
            f"border:1px solid rgba(250,45,72,0.22);border-radius:12px;padding:2px 12px;")
        nl.addWidget(self._db_badge); nl.addStretch()
        self._avatar = QLabel("U"); self._avatar.setFixedSize(32,32)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter); self._avatar.setFont(F(11,bold=True))
        self._avatar.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FA2D48,stop:1 #C81F36);"
            "border-radius:16px;color:white;")
        nl.addWidget(self._avatar)
        self._user_lbl = L("", sz=13, col=C["text2"]); nl.addWidget(self._user_lbl)
        lo = QPushButton("Sign Out"); lo.setFont(F(11))
        lo.setStyleSheet(
            f"QPushButton{{color:{C['accent']};background:transparent;"
            f"border:1px solid rgba(250,45,72,0.26);border-radius:6px;padding:4px 14px;}}"
            f"QPushButton:hover{{background:rgba(250,45,72,0.08);}}")
        lo.clicked.connect(self.sig_logout.emit); nl.addWidget(lo)
        ml.addWidget(nav)

        # content ─────────────────────────────────────────────
        sc = QScrollArea(); sc.setWidgetResizable(True)
        sc.setStyleSheet("background:transparent;border:none;")
        cnt = QWidget(); cnt.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(cnt); cl.setContentsMargins(36,32,36,36); cl.setSpacing(0)

        self._welcome = QLabel(); self._welcome.setFont(F(21, bold=True))
        self._welcome.setStyleSheet(f"color:{C['text']};background:transparent;")
        cl.addWidget(self._welcome)
        cl.addWidget(L("Your workspace is secure and running smoothly.",sz=13,col=C["text2"]))
        cl.addWidget(gap(26))

        # stat cards ──────────────────────────────────────────
        self._sv: dict[str, QLabel] = {}
        grid = QWidget(); grid.setStyleSheet("background:transparent;")
        gl = QGridLayout(grid); gl.setSpacing(14)
        for i,(icon,lbl_t,chg) in enumerate([
            ("👥","Users",       "+0 this week"),
            ("⚡","Sessions",    "today"),
            ("🛡️","Security",   "All clear"),
            ("📈","Uptime",     "Last 30 days"),
        ]):
            c = QWidget()
            c.setStyleSheet(f"QWidget{{background:#FFFFFF;"
                            f"border:1px solid {C['border']};border-radius:12px;}}")
            cv = QVBoxLayout(c); cv.setContentsMargins(18,16,18,16); cv.setSpacing(4)
            cv.addWidget(L(icon,sz=20))
            vl2 = L("—",sz=26,bold=True); cv.addWidget(vl2); self._sv[lbl_t] = vl2
            cv.addWidget(L(lbl_t,sz=11,col=C["text3"]))
            cv.addWidget(L(chg,sz=11,col=C["success"]))
            gl.addWidget(c, i//2, i%2)
        cl.addWidget(grid); cl.addWidget(gap(26))

        # quick actions ───────────────────────────────────────
        cl.addWidget(L("Quick Actions", sz=13, bold=True)); cl.addWidget(gap(12))
        ar = QHBoxLayout(); ar.setSpacing(12)
        for ai,at,ad in [("👥","Manage Users","Add, edit, remove"),
                          ("🏢","Company","Update profile"),
                          ("🔐","Security Log","View auth events"),
                          ("📤","Export","Download reports")]:
            ac = QWidget()
            ac.setStyleSheet(f"QWidget{{background:#FFFFFF;"
                             f"border:1px solid {C['border']};border-radius:10px;}}"
                             f"QWidget:hover{{border:1px solid rgba(250,45,72,0.28);"
                             f"background:rgba(250,45,72,0.04);}}")
            acl = QVBoxLayout(ac); acl.setContentsMargins(16,14,16,14); acl.setSpacing(5)
            acl.addWidget(L(ai,sz=20)); acl.addWidget(L(at,sz=11,bold=True))
            acl.addWidget(L(ad,sz=10,col=C["text3"])); ar.addWidget(ac)
        cl.addLayout(ar); cl.addStretch()
        sc.setWidget(cnt); ml.addWidget(sc)

    def setup(self, username: str, db_name: str, users: int, sessions: int):
        self._welcome.setText(f"Good morning, {username} 👋")
        self._avatar.setText((username or "U")[0].upper())
        self._user_lbl.setText(username)
        self._db_badge.setText(db_name.replace(".db",""))
        self._sv["Users"].setText(str(users))
        self._sv["Sessions"].setText(str(sessions))
        self._sv["Security"].setText("0")
        self._sv["Uptime"].setText("99.9%")


# ──────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    # QStackedWidget indices
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

        self._db: DB | None   = None
        self._db_path         = ""
        self._pending_user    = ""
        self._session_count   = 0

        # root ─────────────────────────────────────────────────
        root = QWidget(); self.setCentralWidget(root)
        self._rl = QVBoxLayout(root)
        self._rl.setContentsMargins(0,0,0,0); self._rl.setSpacing(0)

        # split  (left = stack, right = panel) ─────────────────
        self._split = QWidget()
        self._split.setStyleSheet(f"background:{C['bg_mid']};")
        sl = QHBoxLayout(self._split)
        sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)

        self.stack = QStackedWidget(); self.stack.setMinimumWidth(380)
        sl.addWidget(self.stack, 1)

        self.panel = RightPanel()
        sl.addWidget(self.panel, 1)

        # views ────────────────────────────────────────────────
        self._v_ask      = V_AskDB();            self.stack.addWidget(self._v_ask)       # 0
        self._v_master   = V_MasterAuth();       self.stack.addWidget(self._v_master)    # 1
        self._v_settings = V_CompanySettings();  self.stack.addWidget(self._v_settings)  # 2
        self._v_signup   = V_Signup();           self.stack.addWidget(self._v_signup)    # 3
        self._v_qr       = V_QR();               self.stack.addWidget(self._v_qr)        # 4
        self._v_login    = V_Login();            self.stack.addWidget(self._v_login)     # 5
        self._v_otp      = V_OTP();              self.stack.addWidget(self._v_otp)       # 6

        self._v_dash = V_Dashboard()

        self._rl.addWidget(self._split)

        # wire signals ─────────────────────────────────────────
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
        self._v_login.sig_signup.connect(lambda: self._go_to(self.I_SIGNUP))
        self._v_login.sig_toast.connect(self._toast)

        self._v_otp.sig_ok.connect(self._verify_otp)
        self._v_otp.sig_toast.connect(self._toast)

        self._v_dash.sig_logout.connect(self._logout)

        # boot ─────────────────────────────────────────────────
        self._boot()

    # ── helpers ───────────────────────────────────────────────
    def _go_to(self, idx: int): self.stack.setCurrentIndex(idx)

    def _toast(self, msg: str, kind="info"):
        t = Toast(msg, kind, self); t.raise_(); t.show()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for c in self.findChildren(Toast): c.move(self.width()-355, 16)

    def _open_db(self, path: str):
        if self._db: self._db.close()
        self._db = DB(path); self._db_path = path

    # ── BOOT LOGIC ────────────────────────────────────────────
    def _boot(self):
        """
        Start
         └─ Any .db in cwd with company info?
             ├─ NO  → AskDBName (fresh setup)
             └─ YES → users exist?
                       ├─ NO  → Signup
                       └─ YES → Login
        """
        for fname in sorted(os.listdir(".")):
            if not fname.endswith(".db"): continue
            try:
                db = DB(fname)
                if db.company_exists():
                    self._open_db(fname)
                    if db.users_exist():
                        self._go_login()
                    else:
                        self._go_signup()
                    return
                db.close()
            except Exception:
                pass
        # fresh start
        self._go_to(self.I_ASKDB)
        self.panel.show_features()

    # ── FLOW STEPS ────────────────────────────────────────────
    def _on_db_name(self, db_name: str):
        """AskDB submitted."""
        if os.path.exists(db_name):
            # DB file exists — open it and route
            try:
                self._open_db(db_name)
                co = self._db.get_company()
                if co:
                    if self._db.users_exist():
                        self._toast(f"Database '{db_name}' exists. Opening login.", "info")
                        self._go_login(); return
                    else:
                        self._toast(f"Database exists — no users yet. Go sign up.", "info")
                        self._go_signup(); return
            except Exception as ex:
                self._toast(f"Could not open database: {ex}", "error"); return
        # new DB — verify master first
        self._db_path = db_name
        self._v_master.set_db(db_name)
        self._go_to(self.I_MASTER)
        self.panel.show_master_hint()

    def _after_master(self):
        """Master TOTP passed — create DB and go to company setup."""
        self._open_db(self._db_path)
        self._v_settings.prefill(self._db_path)
        self._go_to(self.I_SETTINGS)
        self.panel.show_features()

    def _after_settings(self):
        """Company info saved → go to signup (first user)."""
        data = self._v_settings.get_data()
        self._db.save_company(data)
        self._go_signup()

    def _go_signup(self):
        self._v_signup.set_db(self._db_path)
        self._go_to(self.I_SIGNUP)
        self.panel.show_signup_panel(self._db_path)

    def _after_signup(self, username: str, totp_secret: str, recovery_json: str):
        """User created → save to DB → show QR."""
        pw_hash = hash_pw(self._v_signup._pw.text())
        ok = self._db.create_user(username, pw_hash, totp_secret, recovery_json)
        if not ok:
            self._toast("Username already exists. Choose another.", "error"); return
        recovery = json.loads(recovery_json)
        self._v_qr.setup(username, totp_secret, recovery, self._db_path)
        self._go_to(self.I_QR)
        self.panel.show_features()

    def _go_login(self, _=None):
        """Navigate to login, refresh user list."""
        users = self._db.list_usernames() if self._db else []
        self._v_login.set_db(self._db_path)
        self._v_login.refresh_users(users)
        self._go_to(self.I_LOGIN)
        self.panel.show_login_panel(users, self._db_path)

    def _check_password(self, username: str):
        """Login button pressed — validate password."""
        pw = self._v_login._pw.text()
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
        """OTP Verify button — check TOTP code or recovery code."""
        otp = self._v_otp.otp_code()
        rec = self._v_otp.rec_code()
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
            self._toast("Invalid code. Try again.", "error"); return

        self._session_count += 1
        self._toast(f"Welcome back, {self._pending_user}! 🎉", "success")
        QTimer.singleShot(450, self._open_dashboard)

    def _open_dashboard(self):
        self._split.setParent(None)
        self._v_dash.setup(
            self._pending_user, self._db_path,
            users=len(self._db.list_usernames()),
            sessions=self._session_count,
        )
        self._rl.addWidget(self._v_dash); self._v_dash.show()

    def _logout(self):
        self._v_dash.setParent(None)
        self._rl.addWidget(self._split); self._split.show()
        self._go_login()


# ──────────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C["bg_dark"]))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C["input_bg"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(C["bg_mid"]))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C["bg_mid"]))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)
    win = MainWindow(); win.show()
    win.showMaximized()
    sys.exit(app.exec())