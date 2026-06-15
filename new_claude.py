import sys
import os
import glob
import sqlite3
import random
import string
import pyotp
import qrcode

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QLineEdit, QGridLayout, QMessageBox, QInputDialog,
    QVBoxLayout, QHBoxLayout, QFrame, QComboBox,
    QCheckBox, QTextEdit, QFileDialog, QStackedWidget
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt


# ─────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────

MASTER_SECRET = "KRSXG5DSNFXGOIDB"


# ─────────────────────────────────────────────────────────────
#  GENERIC HELPERS
# ─────────────────────────────────────────────────────────────

def verify_master_code(code: str) -> bool:
    return pyotp.TOTP(MASTER_SECRET).verify(code)


def verify_otp(secret: str, otp: str) -> bool:
    return pyotp.TOTP(secret).verify(otp)


def generate_recovery_codes(n: int = 5) -> list:
    chars = string.ascii_uppercase + string.digits
    return [''.join(random.choices(chars, k=8)) for _ in range(n)]


def generate_qr(secret: str, username: str) -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="EvoAura")
    path = f"{username}_qr.png"
    qrcode.make(uri).save(path)
    return path


def pixmap_from_blob(blob) -> QPixmap:
    px = QPixmap()
    if isinstance(blob, (bytes, bytearray)):
        px.loadFromData(blob)
    elif isinstance(blob, str) and os.path.exists(blob):
        px.load(blob)
    return px


def px_scaled(pixmap: QPixmap, w: int, h: int) -> QPixmap:
    return pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def alert(parent, title: str, msg: str, kind: str = "info"):
    dispatch = {
        "info":  QMessageBox.information,
        "warn":  QMessageBox.warning,
        "error": QMessageBox.critical,
    }
    dispatch.get(kind, QMessageBox.information)(parent, title, msg)


# ─────────────────────────────────────────────────────────────
#  DATABASE — USERS
# ─────────────────────────────────────────────────────────────

def init_db(db_name: str):
    with sqlite3.connect(db_name) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                username       TEXT UNIQUE,
                password       TEXT,
                role           TEXT,
                otp_secret     TEXT,
                recovery_codes TEXT
            );

            CREATE TABLE IF NOT EXISTS company_info (
                id           INTEGER PRIMARY KEY,
                logo         BLOB,
                company_name TEXT,
                phone        TEXT,
                address      TEXT,
                gst          TEXT,
                footer       TEXT
            );
        """)


def has_users(db_name: str) -> bool:
    with sqlite3.connect(db_name) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def get_all_usernames(db_name: str) -> list:
    with sqlite3.connect(db_name) as conn:
        rows = conn.execute(
            "SELECT username FROM users ORDER BY username"
        ).fetchall()
    return [r[0] for r in rows]


def create_user(db_name: str, username: str, password: str,
                role: str = "user") -> dict:
    secret  = pyotp.random_base32()
    codes   = generate_recovery_codes()
    qr_path = generate_qr(secret, username)
    try:
        with sqlite3.connect(db_name) as conn:
            conn.execute(
                "INSERT INTO users VALUES (NULL, ?, ?, ?, ?, ?)",
                (username, password, role, secret, ",".join(codes))
            )
        return {"success": True, "secret": secret,
                "recovery_codes": codes, "qr_path": qr_path}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Username already exists"}


def login_user(db_name: str, username: str, password: str) -> dict:
    with sqlite3.connect(db_name) as conn:
        row = conn.execute(
            "SELECT password, otp_secret, role, recovery_codes "
            "FROM users WHERE username=?",
            (username,)
        ).fetchone()

    if not row:
        return {"success": False, "message": "User not found"}

    db_pass, secret, role, codes = row
    if password != db_pass:
        return {"success": False, "message": "Wrong password"}

    return {
        "success":        True,
        "secret":         secret,
        "role":           role,
        "recovery_codes": codes.split(",") if codes else []
    }


def get_user_otp_data(db_name: str, username: str):
    with sqlite3.connect(db_name) as conn:
        row = conn.execute(
            "SELECT otp_secret, recovery_codes FROM users WHERE username=?",
            (username,)
        ).fetchone()
    if not row:
        return None, []
    secret, codes = row
    return secret, (codes.split(",") if codes else [])


# ─────────────────────────────────────────────────────────────
#  DATABASE — COMPANY INFO
# ─────────────────────────────────────────────────────────────

def save_company_info(db_name: str, logo_path: str, company_name: str,
                      phone: str, address: str, gst: str, footer: str):
    logo_data = None
    if logo_path and os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()

    with sqlite3.connect(db_name) as conn:
        exists = conn.execute(
            "SELECT id FROM company_info WHERE id=1"
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE company_info "
                "SET logo=?,company_name=?,phone=?,address=?,gst=?,footer=? "
                "WHERE id=1",
                (logo_data, company_name, phone, address, gst, footer)
            )
        else:
            conn.execute(
                "INSERT INTO company_info "
                "(id,logo,company_name,phone,address,gst,footer) "
                "VALUES (1,?,?,?,?,?,?)",
                (logo_data, company_name, phone, address, gst, footer)
            )


def clear_company_logo(db_name: str):
    with sqlite3.connect(db_name) as conn:
        conn.execute("UPDATE company_info SET logo=NULL WHERE id=1")


def load_company_info(db_name: str) -> dict:
    with sqlite3.connect(db_name) as conn:
        row = conn.execute(
            "SELECT logo, company_name, phone, address, gst, footer "
            "FROM company_info WHERE id=1"
        ).fetchone()
    if row:
        return {
            "logo":         row[0] if row[0] else b"",
            "company_name": row[1] or "",
            "phone":        row[2] or "",
            "address":      row[3] or "",
            "gst":          row[4] or "",
            "footer":       row[5] or "",
        }
    return {}


# display ─────────────────────────────────────────────────────────────
#  QR DISPLAY
# ─────────────────────────────────────────────────────────────


class QRDisplay(QWidget):

    def __init__(self, secret: str, qr_path: str, recovery_codes: list):
        super().__init__()
        self.recovery_codes = recovery_codes

        self.setWindowTitle("Setup 2FA")
        self.setFixedSize(420, 560)

        layout = QVBoxLayout()
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        title = QLabel("📱  Scan QR in Authenticator App")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1a7fe8;"
        )
        layout.addWidget(title)

        qr_label = QLabel()
        qr_px = QPixmap(qr_path)
        if not qr_px.isNull():
            qr_label.setPixmap(px_scaled(qr_px, 200, 200))
        qr_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(qr_label)

        lbl_s = QLabel(f"🔑  Secret Key:\n{secret}")
        lbl_s.setWordWrap(True)
        lbl_s.setStyleSheet(
            "font-size: 12px; background:#f0f7ff; "
            "padding:8px; border-radius:5px;"
        )
        layout.addWidget(lbl_s)

        self.lbl_r = QLabel(
            "🛡  Recovery Codes (save these!):\n" + "\n".join(recovery_codes)
        )
        self.lbl_r.setWordWrap(True)
        self.lbl_r.setStyleSheet(
            "font-size: 12px; background:#fff7e6; "
            "padding:8px; border-radius:5px;"
        )
        layout.addWidget(self.lbl_r)

        btn_row = QHBoxLayout()

        copy_btn = QPushButton("📋 Copy Codes")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setMinimumHeight(34)
        copy_btn.clicked.connect(self._copy_codes)

        done_btn = QPushButton("✅ Done")
        done_btn.setMinimumHeight(34)
        done_btn.clicked.connect(self.close)

        btn_row.addWidget(copy_btn)
        btn_row.addWidget(done_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _copy_codes(self):
        QApplication.clipboard().setText("\n".join(self.recovery_codes))
        alert(self, "Copied", "Recovery codes copied to clipboard ✅")


# ─────────────────────────────────────────────────────────────
#  STEP 1 — ASK DB / COMPANY NAME
# ─────────────────────────────────────────────────────────────

class AskDBName(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evo Aura — First Setup")
        self.setFixedSize(420, 230)

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = QLabel("🏢  Enter Company Name")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1a7fe8;"
        )
        layout.addWidget(title)

        sub = QLabel("This will be used as your company name.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #777;")
        layout.addWidget(sub)

        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("e.g.  my_shop")
        self.db_input.setMinimumHeight(36)
        self.db_input.returnPressed.connect(self._go_next)
        layout.addWidget(self.db_input)

        btn = QPushButton("Next  →")
        btn.setMinimumHeight(38)
        btn.clicked.connect(self._go_next)
        layout.addWidget(btn)

        self.setLayout(layout)

    def _go_next(self):
        name = self.db_input.text().strip().replace(" ", "_")
        if not name:
            alert(self, "Error", "Please enter a Company name.", "warn")
            return
        if not name.endswith(".db"):
            name += ".db"
        if os.path.exists(name):
            alert(self, "Already Exists",
                  f"'{name}' already exists.\nPlease choose a different name.",
                  "warn")
            return
        self.auth = StartupAuth(name)
        self.auth.show()
        self.close()


# ─────────────────────────────────────────────────────────────
#  STEP 2 — MASTER CODE VERIFICATION
# ─────────────────────────────────────────────────────────────

class StartupAuth(QWidget):

    def __init__(self, db_name: str):
        super().__init__()
        self.db_name = db_name

        self.setWindowTitle("Security Verification")
        self.setFixedSize(420, 240)

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = QLabel("🔐  Enter Master Setup Code")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1a7fe8;"
        )
        layout.addWidget(title)

        sub = QLabel(f"Database will be created as:  <b>{db_name}</b>")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #555;")
        sub.setTextFormat(Qt.RichText)
        layout.addWidget(sub)

        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("Enter 6-digit TOTP code")
        self.otp_input.setEchoMode(QLineEdit.Password)
        self.otp_input.setMinimumHeight(36)
        self.otp_input.returnPressed.connect(self._verify)
        layout.addWidget(self.otp_input)

        btn = QPushButton("Verify & Create Database")
        btn.setMinimumHeight(38)
        btn.clicked.connect(self._verify)
        layout.addWidget(btn)

        self.setLayout(layout)

    def _verify(self):
        code = self.otp_input.text().strip()
        if not verify_master_code(code):
            alert(self, "Error", "Invalid Master Code ❌\nPlease try again.", "warn")
            self.otp_input.clear()
            return

        init_db(self.db_name)
        default_name = (
            self.db_name.replace(".db", "").replace("_", " ").title()
        )
        save_company_info(self.db_name, "", default_name, "", "", "", "")
        alert(self, "Database Created",
              f"✅  '{self.db_name}' created successfully!\n"
              "Now create the first user.")

        self.company_form = CompanySettings(self.db_name)
        self.company_form.destroyed.connect(self._open_signup)
        self.company_form.show()
        self.close()

    def _open_signup(self):
        self.signup = SignupForm(self.db_name)
        self.signup.show()


# ─────────────────────────────────────────────────────────────
#  SIGNUP
# ─────────────────────────────────────────────────────────────

class SignupForm(QWidget):

    def __init__(self, db_name: str):
        super().__init__()
        self.db_name = db_name

        self.setWindowTitle("Create User")
        self.setFixedSize(420, 390)

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 25, 40, 25)
        layout.setSpacing(14)

        title = QLabel("👤  Create New User")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1a7fe8;"
        )
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnMinimumWidth(0, 110)
        grid.setColumnMinimumWidth(1, 210)

        self.username         = QLineEdit()
        self.username.setPlaceholderText("Enter username")
        self.username.setMinimumHeight(34)

        self.password         = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setMinimumHeight(34)

        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("Confirm password")
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setMinimumHeight(34)

        self.show_pass = QCheckBox("Show Password")
        self.show_pass.stateChanged.connect(self._toggle_password)

        self.master = QLineEdit()
        self.master.setPlaceholderText("6-digit TOTP code")
        self.master.setEchoMode(QLineEdit.Password)
        self.master.setMinimumHeight(34)

        grid.addWidget(QLabel("Username"),         0, 0)
        grid.addWidget(self.username,               0, 1)
        grid.addWidget(QLabel("Password"),         1, 0)
        grid.addWidget(self.password,               1, 1)
        grid.addWidget(QLabel("Confirm Password"), 2, 0)
        grid.addWidget(self.confirm_password,       2, 1)
        grid.addWidget(self.show_pass,              3, 1)
        grid.addWidget(QLabel("Setup Code"),       4, 0)
        grid.addWidget(self.master,                 4, 1)

        layout.addLayout(grid)

        btn = QPushButton("Create User")
        btn.setMinimumHeight(38)
        btn.clicked.connect(self._create)
        layout.addWidget(btn)

        self.setLayout(layout)

    def _toggle_password(self, state: int):
        mode = QLineEdit.Normal if state else QLineEdit.Password
        self.password.setEchoMode(mode)
        self.confirm_password.setEchoMode(mode)

    def _create(self):
        u = self.username.text().strip()
        p = self.password.text().strip()
        c = self.confirm_password.text().strip()
        m = self.master.text().strip()

        if not all([u, p, c, m]):
            alert(self, "Error", "Please fill all fields.", "warn")
            return
        if p != c:
            alert(self, "Error", "Passwords do not match ❌", "warn")
            return
        if not verify_master_code(m):
            alert(self, "Error", "Invalid Setup Code ❌", "warn")
            return

        result = create_user(self.db_name, u, p)
        if not result["success"]:
            alert(self, "Error", result["message"], "warn")
            return

        db = self.db_name

        def _open_login():
            win = LoginForm(db)
            win.show()
            QApplication.instance()._login_ref = win

        self.qr = QRDisplay(
            result["secret"], result["qr_path"], result["recovery_codes"]
        )
        self.qr.destroyed.connect(_open_login)
        self.qr.show()
        self.close()


# ─────────────────────────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────────────────────────

class LoginForm(QWidget):

    def __init__(self, db_name: str):
        super().__init__()
        self.db_name = db_name

        self.setWindowTitle("Evo Aura — Login")
        self.setFixedSize(420, 290)

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 25, 40, 25)
        layout.setSpacing(14)

        title = QLabel("🔑  Login to Evo Aura")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1a7fe8;"
        )
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnMinimumWidth(0, 90)
        grid.setColumnMinimumWidth(1, 220)

        self.username = QComboBox()
        self.username.setEditable(True)
        self.username.setInsertPolicy(QComboBox.NoInsert)
        self.username.setPlaceholderText("Select username")
        self.username.setMinimumHeight(34)
        self._load_usernames()

        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setMinimumHeight(34)
        self.password.returnPressed.connect(self._login)

        grid.addWidget(QLabel("Username"), 0, 0)
        grid.addWidget(self.username,       0, 1)
        grid.addWidget(QLabel("Password"), 1, 0)
        grid.addWidget(self.password,       1, 1)
        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_login = QPushButton("Login")
        btn_login.setMinimumHeight(38)
        btn_login.clicked.connect(self._login)

        btn_signup = QPushButton("New User")
        btn_signup.setMinimumHeight(38)
        btn_signup.clicked.connect(self._open_signup)

        btn_row.addWidget(btn_login)
        btn_row.addWidget(btn_signup)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _load_usernames(self):
        self.username.clear()
        for name in get_all_usernames(self.db_name):
            self.username.addItem(name)
        self.username.setCurrentIndex(-1)

    def _login(self):
        u = self.username.currentText().strip()
        p = self.password.text().strip()

        if not u or not p:
            alert(self, "Error", "Please enter username and password.", "warn")
            return

        result = login_user(self.db_name, u, p)
        if not result["success"]:
            alert(self, "Login Failed", result["message"], "warn")
            return

        otp, ok = QInputDialog.getText(
            self, "2FA Verification", "Enter OTP or Recovery Code:"
        )
        if not ok:
            return

        if (verify_otp(result["secret"], otp)
                or otp in result["recovery_codes"]):
            alert(self, "Success", "Login Successful ✅")
            self.dashboard = Dashboard(self.db_name, u)
            self.dashboard.show()
            self.close()
        else:
            alert(self, "Error", "Invalid OTP / Recovery Code ❌", "warn")

    def _open_signup(self):
        self.signup = SignupForm(self.db_name)
        self.signup.destroyed.connect(self._load_usernames)
        self.signup.show()


# ─────────────────────────────────────────────────────────────
#  COMPANY SETTINGS
# ─────────────────────────────────────────────────────────────

class CompanySettings(QWidget):

    def __init__(self, db_name: str):
        super().__init__()
        self.db_name   = db_name
        self.logo_path = ""

        self.setWindowTitle("Company Settings")
        self.setFixedSize(450, 580)

        layout = QVBoxLayout()
        layout.setContentsMargins(35, 25, 35, 25)
        layout.setSpacing(14)

        title = QLabel("🏢  Company Settings")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1a7fe8;"
        )
        layout.addWidget(title)

        # Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(90, 90)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet(
            "border: 2px dashed #4da3ff; border-radius: 8px; color: #aaa;"
        )
        self.logo_label.setText("No Logo")

        upload_btn = QPushButton("Upload Logo")
        upload_btn.setFixedHeight(30)
        upload_btn.clicked.connect(self._upload_logo)

        remove_btn = QPushButton("Remove Logo")
        remove_btn.setFixedHeight(30)
        remove_btn.setStyleSheet("background-color:#ff4d4d; color:white;")
        remove_btn.clicked.connect(self._remove_logo)

        btn_col = QVBoxLayout()
        btn_col.addWidget(upload_btn)
        btn_col.addWidget(remove_btn)

        logo_row = QHBoxLayout()
        logo_row.addStretch()
        logo_row.addWidget(self.logo_label)
        logo_row.addSpacing(12)
        logo_row.addLayout(btn_col)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        # Fields
        self.company_name = QLineEdit()
        self.company_name.setPlaceholderText("Company name")
        self.company_name.setMinimumHeight(34)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Phone number")
        self.phone.setMinimumHeight(34)

        self.address = QLineEdit()
        self.address.setPlaceholderText("Address")
        self.address.setMinimumHeight(34)

        self.gst = QLineEdit()
        self.gst.setPlaceholderText("GST number")
        self.gst.setMinimumHeight(34)

        self.footer = QTextEdit()
        self.footer.setPlaceholderText("Footer message / description")
        self.footer.setMinimumHeight(90)
        self.footer.setMaximumHeight(110)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, 230)

        grid.addWidget(QLabel("Company Name"), 0, 0)
        grid.addWidget(self.company_name,       0, 1)
        grid.addWidget(QLabel("Phone"),        1, 0)
        grid.addWidget(self.phone,              1, 1)
        grid.addWidget(QLabel("Address"),      2, 0)
        grid.addWidget(self.address,            2, 1)
        grid.addWidget(QLabel("GST No"),       3, 0)
        grid.addWidget(self.gst,               3, 1)
        grid.addWidget(QLabel("Footer"),       4, 0)
        grid.addWidget(self.footer,            4, 1)

        layout.addLayout(grid)

        save_btn = QPushButton("Save Settings")
        save_btn.setMinimumHeight(38)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        self.setLayout(layout)
        self._load()

    def _upload_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.logo_path = path
            px = QPixmap(path)
            if not px.isNull():
                self.logo_label.setPixmap(px_scaled(px, 90, 90))
                self.logo_label.setText("")

    def _remove_logo(self):
        reply = QMessageBox.question(
            self, "Remove Logo",
            "Are you sure you want to remove the logo?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        self.logo_label.clear()
        self.logo_label.setText("No Logo")
        self.logo_path = ""
        clear_company_logo(self.db_name)
        alert(self, "Done", "Logo removed successfully")

    def _save(self):
        try:
            save_company_info(
                self.db_name,
                self.logo_path,
                self.company_name.text().strip(),
                self.phone.text().strip(),
                self.address.text().strip(),
                self.gst.text().strip(),
                self.footer.toPlainText().strip()
            )
            alert(self, "Success", "Company settings saved successfully!")
            self.close()
        except Exception as e:
            alert(self, "Error", str(e), "error")

    def _load(self):
        data = load_company_info(self.db_name)
        if not data:
            default = (
                self.db_name.replace(".db", "").replace("_", " ").title()
            )
            self.company_name.setText(default)
            return

        self.company_name.setText(data.get("company_name", ""))
        self.phone.setText(data.get("phone", ""))
        self.address.setText(data.get("address", ""))
        self.gst.setText(data.get("gst", ""))
        self.footer.setPlainText(data.get("footer", ""))

        logo = data.get("logo", b"")
        if isinstance(logo, (bytes, bytearray)) and logo:
            px = QPixmap()
            px.loadFromData(logo)
            if not px.isNull():
                self.logo_label.setPixmap(px_scaled(px, 90, 90))
                self.logo_label.setText("")


# ─────────────────────────────────────────────────────────────
#  DASHBOARD  — imported from dashboard.py
# ─────────────────────────────────────────────────────────────

from dashboard import Dashboard  # noqa: E402  (placed here intentionally)


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)

    db_files = glob.glob("*.db")

    if db_files:
        db_name = db_files[0]
        init_db(db_name)
        window = (
            LoginForm(db_name) if has_users(db_name)
            else SignupForm(db_name)
        )
    else:
        window = AskDBName()

    window.show()
    sys.exit(app.exec_())