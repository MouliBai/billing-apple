"""EvoAura Customer Control Center."""

import sqlite3
from datetime import date, datetime, timedelta

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox,
    QCheckBox, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialog, QMessageBox, QTabWidget, QScrollArea,
)

from core.app_branding import apply_app_icon
from core.input_behavior import ensure_global_input_guard
from core.theme import C, FIELD_SS
from core.ui_helpers import NO_ARROW as _NO_ARROW, apply_combo_delegate as _apply_combo_delegate


TABLE_SS = f"""
QTableWidget {{
    background:{C['bg_white']}; border:1px solid {C['border']};
    border-radius:10px; gridline-color:#ECECF0; font-size:12px;
    alternate-background-color:{C['bg_panel']};
}}
QHeaderView::section {{
    background:{C['bg_panel']}; color:{C['text2']}; font-size:11px;
    font-weight:700; padding:9px 6px; border:none;
    border-bottom:1px solid {C['border']};
}}
QTableWidget::item {{ padding:7px; }}
QTableWidget::item:selected {{ background:{C['accent_tint2']}; color:{C['text']}; }}
"""


def _money(value):
    return f"â‚¹{float(value or 0):,.2f}"


def _button(text, primary=False):
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(38)
    button.setStyleSheet(f"""
        QPushButton {{
            background:{C['accent'] if primary else C['bg_white']};
            color:{'white' if primary else C['text']};
            border:{'none' if primary else f"1px solid {C['border']}"};
            border-radius:9px; padding:7px 14px; font-weight:700;
        }}
        QPushButton:hover {{
            background:{C['accent_dark'] if primary else C['accent_tint2']};
            border-color:{C['accent']};
        }}
    """)
    return button


def _card():
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:{C['bg_white']};border:1px solid {C['border']};"
        "border-radius:13px;}}")
    return frame


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    table.setStyleSheet(TABLE_SS)
    return table


def init_customer_tables(db):
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            whatsapp TEXT DEFAULT '',
            email TEXT DEFAULT '',
            gender TEXT DEFAULT '',
            date_of_birth TEXT DEFAULT '',
            anniversary_date TEXT DEFAULT '',
            customer_type TEXT DEFAULT 'Regular',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            pincode TEXT DEFAULT '',
            gstin TEXT DEFAULT '',
            business_name TEXT DEFAULT '',
            pan TEXT DEFAULT '',
            billing_address TEXT DEFAULT '',
            allow_credit INTEGER DEFAULT 0,
            credit_limit REAL DEFAULT 0,
            credit_balance REAL DEFAULT 0,
            payment_terms INTEGER DEFAULT 0,
            last_payment_date TEXT DEFAULT '',
            loyalty_enabled INTEGER DEFAULT 1,
            loyalty_points INTEGER DEFAULT 0,
            loyalty_tier TEXT DEFAULT 'Bronze',
            total_points_earned INTEGER DEFAULT 0,
            total_points_redeemed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS customer_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL,
            entry_date TEXT DEFAULT '',
            entry_type TEXT DEFAULT '',
            invoice_number TEXT DEFAULT '',
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            payment_mode TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS customer_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL,
            return_number TEXT DEFAULT '',
            return_date TEXT DEFAULT '',
            original_invoice TEXT DEFAULT '',
            product TEXT DEFAULT '',
            quantity INTEGER DEFAULT 0,
            refund_amount REAL DEFAULT 0,
            exchange_product TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            status TEXT DEFAULT 'Completed'
        );
        CREATE TABLE IF NOT EXISTS customer_loyalty_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL,
            action_date TEXT DEFAULT '',
            action TEXT DEFAULT '',
            invoice_number TEXT DEFAULT '',
            points_earned INTEGER DEFAULT 0,
            points_redeemed INTEGER DEFAULT 0,
            balance_points INTEGER DEFAULT 0,
            notes TEXT DEFAULT ''
        );
        """)


def _rows(db, sql, params=()):
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except sqlite3.Error:
        return []


def _table_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def get_customer_invoices(db, customer):
    """Read common billing schemas without requiring one exact invoice layout."""
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            if "invoices" not in tables:
                return []
            cols = _table_columns(conn, "invoices")
            number = next(
                (x for x in ("invoice_number", "invoice_id", "invoice_no", "bill_no")
                 if x in cols), None)
            inv_date = next(
                (x for x in ("date", "invoice_date", "sale_date", "created_at")
                 if x in cols), None)
            total = next(
                (x for x in ("grand_total", "net_amount", "total", "bill_amount")
                 if x in cols), None)
            paid = next(
                (x for x in ("paid_amount", "amount_paid") if x in cols), None)
            balance = next(
                (x for x in ("balance_amount", "balance", "due_amount") if x in cols),
                None)
            phone_col = next(
                (x for x in ("customer_phone", "phone", "mobile") if x in cols), None)
            code_col = next(
                (x for x in ("customer_code", "customer_id") if x in cols), None)
            name_col = next(
                (x for x in ("customer_name", "customer") if x in cols), None)
            if not all((number, inv_date, total)):
                return []
            conditions, params = [], []
            if code_col:
                conditions.append(f"CAST({code_col} AS TEXT)=?")
                params.append(str(customer.get("code") or ""))
            if phone_col and customer.get("phone"):
                conditions.append(f"{phone_col}=?")
                params.append(customer["phone"])
            if name_col and customer.get("name"):
                conditions.append(f"LOWER({name_col})=LOWER(?)")
                params.append(customer["name"])
            if not conditions:
                return []
            sql = (
                f"SELECT {number} AS invoice_number,{inv_date} AS sale_date,"
                f"{total} AS bill_amount,"
                f"{paid if paid else '0'} AS paid_amount,"
                f"{balance if balance else f'({total}-{paid})' if paid else total} "
                "AS balance_amount "
                f"FROM invoices WHERE {' OR '.join(conditions)} "
                f"ORDER BY {inv_date} DESC")
            rows = [dict(row) for row in conn.execute(sql, params)]
            for row in rows:
                row["payment_mode"] = ""
                row["status"] = (
                    "Paid" if float(row.get("balance_amount") or 0) <= 0
                    else "Pending")
                row["total_items"] = 0
                row["total_qty"] = 0
            return rows
    except sqlite3.Error:
        return []


def get_purchased_products(db, invoices):
    if not invoices:
        return []
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            if "invoice_items" not in {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}:
                return []
            cols = _table_columns(conn, "invoice_items")
            inv_col = next(
                (x for x in ("invoice_number", "invoice_id", "invoice_no")
                 if x in cols), None)
            product_code = next(
                (x for x in ("product_code", "item_code", "code") if x in cols),
                None)
            product_name = next(
                (x for x in ("product_name", "name", "description") if x in cols),
                None)
            qty = next((x for x in ("quantity", "qty") if x in cols), None)
            price = next(
                (x for x in ("selling_price", "price", "rate") if x in cols), None)
            total = next(
                (x for x in ("total", "line_total", "amount") if x in cols), None)
            if not all((inv_col, product_name, qty, price)):
                return []
            numbers = [row["invoice_number"] for row in invoices]
            marks = ",".join("?" for _ in numbers)
            rows = conn.execute(
                f"""SELECT COALESCE({product_code if product_code else "''"},'')
                           AS product_code,
                           {product_name} AS product_name,
                           SUM({qty}) AS qty_bought,
                           MAX({price}) AS last_selling_price,
                           SUM({total if total else f'{qty}*{price}'}) AS total_spent
                    FROM invoice_items WHERE {inv_col} IN ({marks})
                    GROUP BY product_code,product_name
                    ORDER BY total_spent DESC""", numbers).fetchall()
            result = [dict(row) for row in rows]
            for row in result:
                row.update({
                    "category": "", "brand": "", "size": "", "color": "",
                    "last_purchase_date": "",
                })
            return result
    except sqlite3.Error:
        return []


def customer_rows(db):
    customers = _rows(db, "SELECT * FROM customers ORDER BY name")
    result = []
    for customer in customers:
        invoices = get_customer_invoices(db, customer)
        bill_total = sum(float(row.get("bill_amount") or 0) for row in invoices)
        last = invoices[0].get("sale_date") if invoices else ""
        returns = _rows(
            db, "SELECT COUNT(*) AS n FROM customer_returns WHERE customer_code=?",
            (customer["code"],))
        products = get_purchased_products(db, invoices)
        result.append({
            **customer,
            "total_bills": len(invoices),
            "total_purchase_value": bill_total,
            "average_bill_value": bill_total / len(invoices) if invoices else 0,
            "last_purchase_date": last,
            "return_count": int(returns[0]["n"] if returns else 0),
            "last_product_purchased": (
                products[0].get("product_name") if products else ""),
        })
    return result


def customer_kpis(rows):
    month = date.today().strftime("%Y-%m")
    recent_cutoff = (date.today() - timedelta(days=90)).isoformat()
    return {
        "total": len(rows),
        "active": sum(
            1 for row in rows
            if row.get("last_purchase_date", "") >= recent_cutoff
            or row.get("status") == "Active"),
        "credit": sum(1 for row in rows if float(row.get("credit_balance") or 0) > 0),
        "due": sum(float(row.get("credit_balance") or 0) for row in rows),
        "repeat": sum(1 for row in rows if int(row.get("total_bills") or 0) > 1),
        "month": sum(
            1 for row in rows if str(row.get("created_at") or "").startswith(month)),
    }


def next_customer_code(db):
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT code FROM customers WHERE code LIKE 'CUS%'").fetchall()
    highest = 0
    for (code,) in rows:
        suffix = str(code)[3:]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"CUS{highest + 1:05d}"


class CustomerFormDialog(QDialog):
    def __init__(self, db, current_user="Admin", customer=None, parent=None):
        super().__init__(parent)
        apply_app_icon(self)
        ensure_global_input_guard()
        self.db = db; self.current_user = current_user
        self.customer = customer or {}
        self.setWindowTitle("Edit Customer" if customer else "Add Customer")
        self.resize(820, 700)
        root = QVBoxLayout(self)
        title = QLabel(self.windowTitle())
        title.setStyleSheet(
            f"font-size:21px;font-weight:800;color:{C['text']};")
        root.addWidget(title)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        body = QWidget(); grid = QGridLayout(body)
        grid.setHorizontalSpacing(16); grid.setVerticalSpacing(9)

        def line(placeholder=""):
            widget = QLineEdit(); widget.setPlaceholderText(placeholder)
            widget.setStyleSheet(FIELD_SS); return widget

        self.code = line(); self.code.setReadOnly(True)
        self.name = line("Customer name"); self.phone = line("Phone number")
        self.whatsapp = line("WhatsApp number"); self.email = line("Email")
        self.gender = QComboBox(); self.gender.addItems(["", "Male", "Female", "Other"])
        self.dob = QDateEdit(); self.anniversary = QDateEdit()
        for widget in (self.dob, self.anniversary):
            widget.setCalendarPopup(True); widget.setDisplayFormat("dd-MM-yyyy")
            widget.setSpecialValueText("Not set")
            widget.setMinimumDate(QDate(1900, 1, 1)); widget.setDate(widget.minimumDate())
        self.customer_type = QComboBox()
        self.customer_type.addItems(["Walk-in", "Regular", "Credit", "Wholesale", "VIP"])
        self.status = QComboBox()
        self.status.addItems(["Active", "Inactive", "Blocked"])
        self.address = line("Address"); self.city = line("City")
        self.state = line("State"); self.pincode = line("Pincode")
        self.gstin = line("GSTIN"); self.business_name = line("Business name")
        self.pan = line("PAN"); self.billing_address = line("Billing address")
        self.allow_credit = QCheckBox("Allow Credit")
        self.credit_limit = QDoubleSpinBox(); self.credit_balance = QDoubleSpinBox()
        for widget in (self.credit_limit, self.credit_balance):
            widget.setRange(0, 999999999); widget.setPrefix("â‚¹ ")
            widget.setStyleSheet(_NO_ARROW)
        self.payment_terms = QSpinBox(); self.payment_terms.setRange(0, 365)
        self.payment_terms.setSuffix(" days"); self.payment_terms.setStyleSheet(_NO_ARROW)
        self.loyalty_enabled = QCheckBox("Loyalty Enabled")
        self.loyalty_enabled.setChecked(True)
        self.loyalty_points = QSpinBox(); self.loyalty_points.setRange(0, 999999999)
        self.loyalty_tier = QComboBox()
        self.loyalty_tier.addItems(["Bronze", "Silver", "Gold", "Platinum"])
        self.notes = QTextEdit(); self.notes.setFixedHeight(70)
        for combo in (self.gender, self.customer_type, self.status, self.loyalty_tier):
            _apply_combo_delegate(combo)

        sections = [
            ("Basic Information", [
                ("Customer Code", self.code), ("Customer Name *", self.name),
                ("Phone *", self.phone), ("WhatsApp Number", self.whatsapp),
                ("Email", self.email), ("Gender", self.gender),
                ("Date of Birth", self.dob), ("Anniversary", self.anniversary),
                ("Customer Type", self.customer_type), ("Status", self.status)]),
            ("Address", [
                ("Address", self.address), ("City", self.city),
                ("State", self.state), ("Pincode", self.pincode)]),
            ("GST / Business Customer", [
                ("GSTIN", self.gstin), ("Business Name", self.business_name),
                ("PAN", self.pan), ("Billing Address", self.billing_address)]),
            ("Credit Information", [
                ("Credit Permission", self.allow_credit),
                ("Credit Limit", self.credit_limit),
                ("Current Credit Balance", self.credit_balance),
                ("Payment Terms", self.payment_terms)]),
            ("Loyalty", [
                ("Loyalty Enabled", self.loyalty_enabled),
                ("Loyalty Points", self.loyalty_points),
                ("Loyalty Tier", self.loyalty_tier)]),
        ]
        row = 0
        for section, fields in sections:
            heading = QLabel(section)
            heading.setStyleSheet(
                f"font-size:14px;font-weight:800;color:{C['text']};"
                f"padding:9px 2px 4px;border-bottom:1px solid {C['border']};")
            grid.addWidget(heading, row, 0, 1, 4); row += 1
            for index, (label, widget) in enumerate(fields):
                r, side = row + index // 2, index % 2
                grid.addWidget(QLabel(label), r, side * 2)
                grid.addWidget(widget, r, side * 2 + 1)
            row += (len(fields) + 1) // 2
        grid.addWidget(QLabel("Notes"), row, 0)
        grid.addWidget(self.notes, row, 1, 1, 3)
        scroll.setWidget(body); root.addWidget(scroll, 1)
        actions = QHBoxLayout(); actions.addStretch()
        cancel = _button("Cancel"); save = _button("Save Customer", True)
        cancel.clicked.connect(self.reject); save.clicked.connect(self._save)
        actions.addWidget(cancel); actions.addWidget(save); root.addLayout(actions)
        self._load()

    def _load(self):
        c = self.customer
        self.code.setText(c.get("code") or next_customer_code(self.db))
        for widget, key in (
            (self.name, "name"), (self.phone, "phone"), (self.whatsapp, "whatsapp"),
            (self.email, "email"), (self.address, "address"), (self.city, "city"),
            (self.state, "state"), (self.pincode, "pincode"), (self.gstin, "gstin"),
            (self.business_name, "business_name"), (self.pan, "pan"),
            (self.billing_address, "billing_address")):
            widget.setText(str(c.get(key) or ""))
        for combo, key, default in (
            (self.gender, "gender", ""), (self.customer_type, "customer_type", "Regular"),
            (self.status, "status", "Active"), (self.loyalty_tier, "loyalty_tier", "Bronze")):
            index = combo.findText(c.get(key) or default)
            combo.setCurrentIndex(max(0, index))
        for widget, key in ((self.dob, "date_of_birth"),
                            (self.anniversary, "anniversary_date")):
            parsed = QDate.fromString(str(c.get(key) or ""), "yyyy-MM-dd")
            widget.setDate(parsed if parsed.isValid() else widget.minimumDate())
        self.allow_credit.setChecked(bool(c.get("allow_credit")))
        self.credit_limit.setValue(float(c.get("credit_limit") or 0))
        self.credit_balance.setValue(float(c.get("credit_balance") or 0))
        self.payment_terms.setValue(int(c.get("payment_terms") or 0))
        self.loyalty_enabled.setChecked(bool(c.get("loyalty_enabled", 1)))
        self.loyalty_points.setValue(int(c.get("loyalty_points") or 0))
        self.notes.setPlainText(c.get("notes") or "")

    def _save(self):
        if not self.name.text().strip() or not self.phone.text().strip():
            QMessageBox.warning(
                self, "Validation", "Customer name and phone are required.")
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values = {
            "code": self.code.text(), "name": self.name.text().strip(),
            "phone": self.phone.text().strip(), "whatsapp": self.whatsapp.text().strip(),
            "email": self.email.text().strip(), "gender": self.gender.currentText(),
            "date_of_birth": "" if self.dob.date() == self.dob.minimumDate()
                             else self.dob.date().toString("yyyy-MM-dd"),
            "anniversary_date": "" if self.anniversary.date() == self.anniversary.minimumDate()
                                else self.anniversary.date().toString("yyyy-MM-dd"),
            "customer_type": self.customer_type.currentText(),
            "address": self.address.text().strip(), "city": self.city.text().strip(),
            "state": self.state.text().strip(), "pincode": self.pincode.text().strip(),
            "gstin": self.gstin.text().strip().upper(),
            "business_name": self.business_name.text().strip(),
            "pan": self.pan.text().strip().upper(),
            "billing_address": self.billing_address.text().strip(),
            "allow_credit": int(self.allow_credit.isChecked()),
            "credit_limit": self.credit_limit.value(),
            "credit_balance": self.credit_balance.value(),
            "payment_terms": self.payment_terms.value(),
            "loyalty_enabled": int(self.loyalty_enabled.isChecked()),
            "loyalty_points": self.loyalty_points.value(),
            "loyalty_tier": self.loyalty_tier.currentText(),
            "status": self.status.currentText(),
            "notes": self.notes.toPlainText().strip(),
        }
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                INSERT INTO customers(
                    code,name,phone,whatsapp,email,gender,date_of_birth,
                    anniversary_date,customer_type,address,city,state,pincode,
                    gstin,business_name,pan,billing_address,allow_credit,
                    credit_limit,credit_balance,payment_terms,loyalty_enabled,
                    loyalty_points,loyalty_tier,status,notes,created_at,
                    created_by,updated_at)
                VALUES(:code,:name,:phone,:whatsapp,:email,:gender,:date_of_birth,
                    :anniversary_date,:customer_type,:address,:city,:state,:pincode,
                    :gstin,:business_name,:pan,:billing_address,:allow_credit,
                    :credit_limit,:credit_balance,:payment_terms,:loyalty_enabled,
                    :loyalty_points,:loyalty_tier,:status,:notes,:created_at,
                    :created_by,:updated_at)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name,phone=excluded.phone,
                    whatsapp=excluded.whatsapp,email=excluded.email,
                    gender=excluded.gender,date_of_birth=excluded.date_of_birth,
                    anniversary_date=excluded.anniversary_date,
                    customer_type=excluded.customer_type,address=excluded.address,
                    city=excluded.city,state=excluded.state,pincode=excluded.pincode,
                    gstin=excluded.gstin,business_name=excluded.business_name,
                    pan=excluded.pan,billing_address=excluded.billing_address,
                    allow_credit=excluded.allow_credit,
                    credit_limit=excluded.credit_limit,
                    credit_balance=excluded.credit_balance,
                    payment_terms=excluded.payment_terms,
                    loyalty_enabled=excluded.loyalty_enabled,
                    loyalty_points=excluded.loyalty_points,
                    loyalty_tier=excluded.loyalty_tier,status=excluded.status,
                    notes=excluded.notes,updated_at=excluded.updated_at
            """, {**values, "created_at": self.customer.get("created_at") or now,
                  "created_by": self.current_user, "updated_at": now})
        self.accept()


class CustomerPage(QWidget):
    def __init__(self, db_name, current_user="Admin", navigate_cb=None, parent=None):
        super().__init__(parent)
        ensure_global_input_guard(); apply_app_icon(self)
        self.db = db_name; self.current_user = current_user
        self.navigate_cb = navigate_cb
        self.rows = []; self._selected = None
        init_customer_tables(db_name)
        self.setStyleSheet(f"background:{C['bg_light']};")
        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(10)
        top = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("Customer Control Center")
        title.setStyleSheet(
            f"font-size:23px;font-weight:800;color:{C['text']};")
        subtitle = QLabel(
            "Billing history, customer credit, returns and loyalty")
        subtitle.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        title_wrap.addWidget(title); title_wrap.addWidget(subtitle)
        top.addLayout(title_wrap); top.addStretch()
        add = _button("+ Add Customer", True); add.clicked.connect(self._add_customer)
        top.addWidget(add); root.addLayout(top)

        self.kpi_labels = {}
        specs = [
            ("total", "Total Customers", "ðŸ‘¥", C["blue"]),
            ("active", "Active Customers", "âœ…", C["success"]),
            ("credit", "Credit Customers", "ðŸ’³", C["warning"]),
            ("due", "Total Credit Due", "â³", C["accent"]),
            ("repeat", "Repeat Customers", "ðŸ”", "#5856D6"),
            ("month", "This Month Customers", "ðŸ“…", "#00A67E"),
        ]
        grid = QGridLayout(); grid.setSpacing(9)
        for index, (key, label, icon, color) in enumerate(specs):
            card = _card(); card.setMinimumHeight(78)
            lay = QVBoxLayout(card); lay.setContentsMargins(13, 9, 13, 9)
            heading = QLabel(f"{icon}  {label}")
            heading.setStyleSheet(
                f"color:{C['text3']};font-size:10px;font-weight:700;border:none;")
            value = QLabel("â€”")
            value.setStyleSheet(
                f"color:{C['text']};font-size:18px;font-weight:800;border:none;")
            lay.addWidget(heading); lay.addWidget(value)
            self.kpi_labels[key] = value
            grid.addWidget(card, index // 3, index % 3)
        root.addLayout(grid)

        filters = _card(); fl = QHBoxLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Name, phone, customer code or GSTINâ€¦")
        self.search.setStyleSheet(FIELD_SS)
        self.customer_type = QComboBox()
        self.customer_type.addItems(
            ["All Types", "Walk-in", "Regular", "Credit", "Wholesale", "VIP"])
        self.credit_status = QComboBox()
        self.credit_status.addItems(["All Credit", "No Due", "Due", "Overdue"])
        self.loyalty = QComboBox()
        self.loyalty.addItems(
            ["All Loyalty", "Bronze", "Silver", "Gold", "Platinum"])
        self.city = QComboBox(); self.status = QComboBox()
        self.status.addItems(["All Status", "Active", "Inactive", "Blocked"])
        for combo in (
            self.customer_type, self.credit_status, self.loyalty,
            self.city, self.status):
            _apply_combo_delegate(combo); combo.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        fl.addWidget(QLabel("Advanced Filter")); fl.addWidget(self.search, 1)
        fl.addWidget(self.customer_type); fl.addWidget(self.credit_status)
        fl.addWidget(self.loyalty); fl.addWidget(self.city); fl.addWidget(self.status)
        root.addWidget(filters)

        self.table = _table([
            "Customer Code", "Customer Name", "Phone", "City", "Total Bills",
            "Total Purchase Value", "Credit Balance", "Loyalty Points",
            "Last Purchase Date", "Status", "Actions"])
        self.table.cellClicked.connect(self._cell_clicked)

        self.drawer = _card(); self.drawer.setMinimumWidth(430)
        self.drawer.setMaximumWidth(500); self.drawer.hide()
        dl = QVBoxLayout(self.drawer)
        drawer_top = QHBoxLayout()
        self.drawer_title = QLabel("Customer Detail")
        self.drawer_title.setStyleSheet(
            f"font-size:17px;font-weight:800;color:{C['text']};border:none;")
        close = QPushButton("âœ•"); close.setFixedSize(28, 28)
        close.clicked.connect(self.drawer.hide)
        drawer_top.addWidget(self.drawer_title); drawer_top.addStretch()
        drawer_top.addWidget(close); dl.addLayout(drawer_top)
        self.drawer_summary = QLabel("â€”"); self.drawer_summary.setWordWrap(True)
        self.drawer_summary.setStyleSheet(
            f"font-size:12px;color:{C['text2']};border:none;")
        dl.addWidget(self.drawer_summary)
        self.detail_kpis = QLabel("â€”"); self.detail_kpis.setWordWrap(True)
        self.detail_kpis.setStyleSheet(
            f"background:{C['bg_panel']};padding:9px;border-radius:8px;"
            f"color:{C['text']};")
        dl.addWidget(self.detail_kpis)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane{{border:1px solid {C['border']};border-radius:8px;}}
            QTabBar::tab{{padding:7px 8px;background:{C['bg_panel']};}}
            QTabBar::tab:selected{{background:{C['accent']};color:white;}}
        """)
        self.purchase_table = _table([
            "Invoice", "Date", "Qty", "Bill", "Paid", "Balance", "Status"])
        self.products_table = _table([
            "Product", "Qty", "Last Price", "Total Spent"])
        self.ledger_table = _table([
            "Date", "Type", "Invoice", "Debit", "Credit", "Balance", "Mode"])
        self.returns_table = _table([
            "Return No", "Date", "Invoice", "Product", "Qty", "Refund", "Status"])
        self.loyalty_table = _table([
            "Date", "Action", "Invoice", "Earned", "Redeemed", "Balance"])
        for table, label in (
            (self.purchase_table, "PURCHASES"), (self.products_table, "PRODUCTS"),
            (self.ledger_table, "CREDIT"), (self.returns_table, "RETURNS"),
            (self.loyalty_table, "LOYALTY")):
            page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(table)
            self.tabs.addTab(page, label)
        dl.addWidget(self.tabs, 1)
        actions = QGridLayout()
        self.edit_btn = _button("âœ Edit Customer")
        self.sale_btn = _button("ðŸ§¾ New Sale", True)
        self.payment_btn = _button("ðŸ’³ Add Payment")
        self.block_btn = _button("â›” Disable / Block")
        actions.addWidget(self.edit_btn, 0, 0); actions.addWidget(self.sale_btn, 0, 1)
        actions.addWidget(self.payment_btn, 1, 0); actions.addWidget(self.block_btn, 1, 1)
        dl.addLayout(actions)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.sale_btn.clicked.connect(self._new_sale)
        self.payment_btn.clicked.connect(self._add_payment)
        self.block_btn.clicked.connect(self._block_customer)

        body = QHBoxLayout(); body.addWidget(self.table, 1); body.addWidget(self.drawer)
        root.addLayout(body, 1)
        self.refresh()

    def _filters_match(self, row):
        search = self.search.text().strip().casefold()
        if search and search not in " ".join(str(row.get(key) or "") for key in (
            "code", "name", "phone", "gstin")).casefold():
            return False
        if self.customer_type.currentIndex() > 0 and (
                row.get("customer_type") != self.customer_type.currentText()):
            return False
        if self.loyalty.currentIndex() > 0 and (
                row.get("loyalty_tier") != self.loyalty.currentText()):
            return False
        if self.city.currentIndex() > 0 and row.get("city") != self.city.currentText():
            return False
        if self.status.currentIndex() > 0 and row.get("status") != self.status.currentText():
            return False
        balance = float(row.get("credit_balance") or 0)
        credit_filter = self.credit_status.currentText()
        if credit_filter == "No Due" and balance > 0:
            return False
        if credit_filter in ("Due", "Overdue") and balance <= 0:
            return False
        return True

    def refresh(self, *_):
        all_rows = customer_rows(self.db)
        cities = sorted({row.get("city") for row in all_rows if row.get("city")})
        current_city = self.city.currentText()
        self.city.blockSignals(True); self.city.clear(); self.city.addItem("All Cities")
        self.city.addItems(cities)
        index = self.city.findText(current_city); self.city.setCurrentIndex(max(0, index))
        self.city.blockSignals(False)
        self.rows = [row for row in all_rows if self._filters_match(row)]
        self.table.setRowCount(0)
        for source in self.rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = [
                source.get("code"), source.get("name"), source.get("phone"),
                source.get("city"), source.get("total_bills"),
                _money(source.get("total_purchase_value")),
                _money(source.get("credit_balance")), source.get("loyalty_points"),
                source.get("last_purchase_date"), source.get("status"),
                "ðŸ‘  âœ  ðŸ§¾  ðŸ’³  â›”"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or "â€”"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6 and float(source.get("credit_balance") or 0) > 0:
                    item.setForeground(QBrush(QColor(C["accent"])))
                self.table.setItem(row, col, item)
        kpis = customer_kpis(all_rows)
        for key, label in self.kpi_labels.items():
            label.setText(_money(kpis[key]) if key == "due" else f"{int(kpis[key]):,}")
        if self._selected:
            updated = next(
                (row for row in all_rows if row["code"] == self._selected["code"]),
                None)
            if updated:
                self._show_drawer(updated)

    def refresh_light(self):
        self.refresh()

    def _fill(self, table, rows, columns, money_columns=()):
        table.setRowCount(0)
        for source in rows:
            row = table.rowCount(); table.insertRow(row)
            for col, key in enumerate(columns):
                value = source.get(key)
                text = _money(value) if col in money_columns else str(value or "â€”")
                table.setItem(row, col, QTableWidgetItem(text))

    def _cell_clicked(self, row, _column):
        if 0 <= row < len(self.rows):
            self._show_drawer(self.rows[row])

    def _show_drawer(self, customer):
        self._selected = customer
        self.drawer_title.setText(customer.get("name") or "Customer")
        self.drawer_summary.setText(
            f"<b>Code:</b> {customer.get('code')}<br>"
            f"<b>Phone:</b> {customer.get('phone') or 'â€”'}<br>"
            f"<b>Type:</b> {customer.get('customer_type') or 'â€”'}<br>"
            f"<b>City:</b> {customer.get('city') or 'â€”'}<br>"
            f"<b>Status:</b> {customer.get('status') or 'â€”'}<br>"
            f"<b>Credit Balance:</b> {_money(customer.get('credit_balance'))}<br>"
            f"<b>Loyalty:</b> {customer.get('loyalty_points',0)} points Â· "
            f"{customer.get('loyalty_tier') or 'Bronze'}")
        self.detail_kpis.setText(
            f"Bills: {customer.get('total_bills',0)}   Â·   "
            f"Purchases: {_money(customer.get('total_purchase_value'))}   Â·   "
            f"Average Bill: {_money(customer.get('average_bill_value'))}\n"
            f"Returns: {customer.get('return_count',0)}   Â·   "
            f"Last Purchase: {customer.get('last_purchase_date') or 'â€”'}")
        invoices = get_customer_invoices(self.db, customer)
        products = get_purchased_products(self.db, invoices)
        ledger = _rows(
            self.db, "SELECT * FROM customer_ledger WHERE customer_code=? "
                     "ORDER BY entry_date DESC,id DESC", (customer["code"],))
        returns = _rows(
            self.db, "SELECT * FROM customer_returns WHERE customer_code=? "
                     "ORDER BY return_date DESC,id DESC", (customer["code"],))
        loyalty = _rows(
            self.db, "SELECT * FROM customer_loyalty_log WHERE customer_code=? "
                     "ORDER BY action_date DESC,id DESC", (customer["code"],))
        self._fill(
            self.purchase_table, invoices,
            ["invoice_number", "sale_date", "total_qty", "bill_amount",
             "paid_amount", "balance_amount", "status"],
            money_columns=(3, 4, 5))
        self._fill(
            self.products_table, products,
            ["product_name", "qty_bought", "last_selling_price", "total_spent"],
            money_columns=(2, 3))
        self._fill(
            self.ledger_table, ledger,
            ["entry_date", "entry_type", "invoice_number", "debit", "credit",
             "balance", "payment_mode"], money_columns=(3, 4, 5))
        self._fill(
            self.returns_table, returns,
            ["return_number", "return_date", "original_invoice", "product",
             "quantity", "refund_amount", "status"], money_columns=(5,))
        self._fill(
            self.loyalty_table, loyalty,
            ["action_date", "action", "invoice_number", "points_earned",
             "points_redeemed", "balance_points"])
        self.drawer.show()

    def _add_customer(self):
        if CustomerFormDialog(
                self.db, self.current_user, parent=self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _edit_selected(self):
        if not self._selected:
            return
        if CustomerFormDialog(
                self.db, self.current_user, self._selected,
                self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _new_sale(self):
        if not self._selected:
            return
        if self.navigate_cb:
            self.navigate_cb("sale")
            return
        QMessageBox.information(
            self, "New Sale",
            f"Customer selected for billing:\n\n"
            f"{self._selected.get('name')} Â· {self._selected.get('phone')}\n\n"
            "Open New Sale from the sidebar. The billing page can read this "
            "customer from the shared customers table.")

    def _add_payment(self):
        if not self._selected:
            return
        dialog = QDialog(self); dialog.setWindowTitle("Customer Payment")
        layout = QGridLayout(dialog)
        amount = QDoubleSpinBox(); amount.setRange(0, 999999999); amount.setPrefix("â‚¹ ")
        amount.setValue(float(self._selected.get("credit_balance") or 0))
        mode = QComboBox(); mode.addItems(["Cash", "UPI", "Card", "Bank Transfer"])
        notes = QLineEdit(); notes.setPlaceholderText("Reference / notes")
        layout.addWidget(QLabel("Amount"), 0, 0); layout.addWidget(amount, 0, 1)
        layout.addWidget(QLabel("Payment Mode"), 1, 0); layout.addWidget(mode, 1, 1)
        layout.addWidget(QLabel("Notes"), 2, 0); layout.addWidget(notes, 2, 1)
        save = _button("Save Payment", True); cancel = _button("Cancel")
        cancel.clicked.connect(dialog.reject); save.clicked.connect(dialog.accept)
        layout.addWidget(cancel, 3, 0); layout.addWidget(save, 3, 1)
        if dialog.exec() != QDialog.DialogCode.Accepted or amount.value() <= 0:
            return
        paid = min(amount.value(), float(self._selected.get("credit_balance") or 0))
        new_balance = max(
            0, float(self._selected.get("credit_balance") or 0) - paid)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE customers SET credit_balance=?,last_payment_date=?,"
                "updated_at=? WHERE code=?",
                (new_balance, now[:10], now, self._selected["code"]))
            conn.execute("""
                INSERT INTO customer_ledger(
                    customer_code,entry_date,entry_type,invoice_number,debit,
                    credit,balance,payment_mode,notes,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                self._selected["code"], now[:10], "Payment Received", "",
                0, paid, new_balance, mode.currentText(), notes.text().strip(),
                self.current_user, now))
        self.refresh(); self.tabs.setCurrentIndex(2)

    def _block_customer(self):
        if not self._selected:
            return
        status = "Blocked" if self._selected.get("status") != "Blocked" else "Active"
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE customers SET status=?,updated_at=? WHERE code=?",
                (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 self._selected["code"]))
        self.refresh()


