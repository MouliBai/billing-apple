"""EvoAura Customer Due / Collection Control Center."""

import sqlite3
from datetime import date, datetime, timedelta

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QMessageBox, QTabWidget,
)

from core.app_branding import apply_app_icon
from core.input_behavior import ensure_global_input_guard
from pages.inventory.product_page import C, FIELD_SS, _NO_ARROW, _apply_combo_delegate
from pages.customers.customer_center_page import init_customer_tables, get_customer_invoices


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


def _rows(db, sql, params=()):
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except sqlite3.Error:
        return []


def init_credit_tables(db):
    init_customer_tables(db)
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS customer_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_number TEXT UNIQUE NOT NULL,
            customer_code TEXT NOT NULL,
            payment_date TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            payment_mode TEXT DEFAULT '',
            reference_number TEXT DEFAULT '',
            adjusted_invoice TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            received_by TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS customer_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL,
            reminder_date TEXT DEFAULT '',
            reminder_type TEXT DEFAULT '',
            message TEXT DEFAULT '',
            sent_by TEXT DEFAULT '',
            status TEXT DEFAULT 'Logged'
        );
        """)


def _parse_date(value):
    text = str(value or "")[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def outstanding_bills(db, customer):
    terms = int(customer.get("payment_terms") or 0)
    bills = []
    for invoice in get_customer_invoices(db, customer):
        balance = float(invoice.get("balance_amount") or 0)
        if balance <= 0:
            continue
        bill_date = _parse_date(invoice.get("sale_date"))
        due_date = bill_date + timedelta(days=terms) if bill_date else None
        days_overdue = max(0, (date.today() - due_date).days) if due_date else 0
        status = (
            "Overdue" if days_overdue > 0 else
            "Due Today" if due_date == date.today() else
            "Due")
        bills.append({
            **invoice,
            "due_date": due_date.isoformat() if due_date else "",
            "days_overdue": days_overdue,
            "status": status,
        })
    if not bills and float(customer.get("credit_balance") or 0) > 0:
        created = _parse_date(customer.get("created_at"))
        bill_date = created or date.today()
        due_date = bill_date + timedelta(days=terms)
        overdue = max(0, (date.today() - due_date).days)
        bills.append({
            "invoice_number": "Opening / Unallocated",
            "sale_date": bill_date.isoformat(),
            "due_date": due_date.isoformat(),
            "bill_amount": float(customer.get("credit_balance") or 0),
            "paid_amount": 0,
            "balance_amount": float(customer.get("credit_balance") or 0),
            "days_overdue": overdue,
            "status": "Overdue" if overdue else "Due",
        })
    return bills


def credit_rows(db):
    customers = _rows(
        db, "SELECT * FROM customers WHERE credit_balance>0 OR allow_credit=1 "
            "ORDER BY credit_balance DESC,name")
    result = []
    for customer in customers:
        bills = outstanding_bills(db, customer)
        total_credit = sum(float(row.get("bill_amount") or 0) for row in bills)
        balance = float(customer.get("credit_balance") or 0)
        if bills:
            balance = max(
                balance, sum(float(row.get("balance_amount") or 0) for row in bills))
        paid = max(0, total_credit - balance)
        due_dates = [
            _parse_date(row.get("due_date")) for row in bills
            if _parse_date(row.get("due_date"))]
        oldest = min(due_dates) if due_dates else None
        days_overdue = max(
            [int(row.get("days_overdue") or 0) for row in bills] or [0])
        limit = float(customer.get("credit_limit") or 0)
        if limit > 0 and balance > limit:
            status = "Limit Exceeded"
        elif days_overdue > 0:
            status = "Overdue"
        elif balance > 0:
            status = "Due"
        else:
            status = "Paid"
        result.append({
            **customer,
            "total_bills": len(bills),
            "total_credit": total_credit or balance,
            "paid_amount": paid,
            "balance_due": balance,
            "oldest_due_date": oldest.isoformat() if oldest else "",
            "days_overdue": days_overdue,
            "credit_status": status,
            "overdue_amount": sum(
                float(row.get("balance_amount") or 0)
                for row in bills if int(row.get("days_overdue") or 0) > 0),
            "bills": bills,
        })
    return result


def credit_kpis(db, rows):
    month = date.today().strftime("%Y-%m")
    payments = _rows(
        db, "SELECT amount FROM customer_payments WHERE substr(payment_date,1,7)=?",
        (month,))
    due_today = sum(
        float(bill.get("balance_amount") or 0)
        for row in rows for bill in row["bills"]
        if bill.get("due_date") == date.today().isoformat())
    return {
        "due": sum(float(row["balance_due"]) for row in rows),
        "overdue": sum(float(row["overdue_amount"]) for row in rows),
        "customers": sum(1 for row in rows if row["balance_due"] > 0),
        "overdue_customers": sum(
            1 for row in rows if int(row.get("days_overdue") or 0) > 0),
        "today": due_today,
        "collection": sum(float(row.get("amount") or 0) for row in payments),
    }


def next_receipt(db):
    prefix = f"RCPT-{date.today().strftime('%Y%m%d')}-"
    with sqlite3.connect(db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM customer_payments WHERE receipt_number LIKE ?",
            (prefix + "%",)).fetchone()[0]
    return f"{prefix}{count + 1:03d}"


class PaymentDialog(QDialog):
    def __init__(self, db, customer, user="Admin", parent=None):
        super().__init__(parent)
        apply_app_icon(self)
        self.db = db; self.customer = customer; self.user = user
        self.setWindowTitle("Add Customer Payment")
        self.setMinimumWidth(520)
        layout = QGridLayout(self)
        name = QLabel(customer.get("name") or "Customer")
        balance = QLabel(_money(customer.get("balance_due")))
        self.payment_date = QDateEdit(QDate.currentDate())
        self.payment_date.setCalendarPopup(True); self.payment_date.setDisplayFormat("dd-MM-yyyy")
        self.amount = QDoubleSpinBox(); self.amount.setRange(0, 999999999)
        self.amount.setPrefix("â‚¹ "); self.amount.setValue(
            float(customer.get("balance_due") or 0))
        self.mode = QComboBox()
        self.mode.addItems(["Cash", "UPI", "Card", "Bank Transfer"])
        _apply_combo_delegate(self.mode)
        self.reference = QLineEdit()
        self.invoice = QComboBox(); self.invoice.addItem("Auto / Oldest Bill")
        self.invoice.addItems([
            bill.get("invoice_number") or "Unnumbered" for bill in customer["bills"]])
        _apply_combo_delegate(self.invoice)
        self.notes = QTextEdit(); self.notes.setFixedHeight(70)
        fields = [
            ("Customer", name), ("Balance Due", balance),
            ("Payment Date", self.payment_date), ("Amount Received", self.amount),
            ("Payment Mode", self.mode), ("Reference Number", self.reference),
            ("Adjust Against Bill", self.invoice), ("Notes", self.notes)]
        for row, (label, widget) in enumerate(fields):
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(widget, row, 1)
        cancel = _button("Cancel"); save = _button("Save Payment", True)
        cancel.clicked.connect(self.reject); save.clicked.connect(self._save)
        layout.addWidget(cancel, len(fields), 0); layout.addWidget(save, len(fields), 1)

    def _save(self):
        amount = min(
            self.amount.value(), float(self.customer.get("balance_due") or 0))
        if amount <= 0:
            QMessageBox.warning(self, "Payment", "Enter a payment amount.")
            return
        code = self.customer["code"]
        current = float(self.customer.get("balance_due") or 0)
        new_balance = max(0, current - amount)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        receipt = next_receipt(self.db)
        invoice = (
            "" if self.invoice.currentIndex() == 0 else self.invoice.currentText())
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                INSERT INTO customer_payments(
                    receipt_number,customer_code,payment_date,amount,payment_mode,
                    reference_number,adjusted_invoice,notes,received_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
            """, (
                receipt, code, self.payment_date.date().toString("yyyy-MM-dd"),
                amount, self.mode.currentText(), self.reference.text().strip(),
                invoice, self.notes.toPlainText().strip(), self.user, now))
            conn.execute(
                "UPDATE customers SET credit_balance=?,last_payment_date=?,"
                "updated_at=? WHERE code=?",
                (new_balance, self.payment_date.date().toString("yyyy-MM-dd"),
                 now, code))
            conn.execute("""
                INSERT INTO customer_ledger(
                    customer_code,entry_date,entry_type,invoice_number,debit,
                    credit,balance,payment_mode,notes,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                code, self.payment_date.date().toString("yyyy-MM-dd"),
                "Payment Received", invoice, 0, amount, new_balance,
                self.mode.currentText(),
                f"{receipt} Â· {self.notes.toPlainText().strip()}",
                self.user, now))
        self.accept()


class CreditManagementPage(QWidget):
    def __init__(self, db_name, current_user="Admin", parent=None):
        super().__init__(parent)
        ensure_global_input_guard(); apply_app_icon(self)
        self.db = db_name; self.current_user = current_user
        self.rows = []; self._selected = None
        init_credit_tables(db_name)
        self.setStyleSheet(f"background:{C['bg_light']};")
        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("Customer Due / Collection Control Center")
        title.setStyleSheet(
            f"font-size:23px;font-weight:800;color:{C['text']};")
        subtitle = QLabel(
            "Track balances, overdue customers and monthly collections")
        subtitle.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        title_wrap.addWidget(title); title_wrap.addWidget(subtitle)
        top.addLayout(title_wrap); top.addStretch()
        self.add_payment_top = _button("+ Add Payment", True)
        self.add_payment_top.clicked.connect(self._add_payment)
        top.addWidget(self.add_payment_top); root.addLayout(top)

        self.kpi_labels = {}
        specs = [
            ("due", "Total Credit Due", "ðŸ’³", C["blue"]),
            ("overdue", "Overdue Amount", "â›”", C["accent"]),
            ("customers", "Credit Customers", "ðŸ‘¥", "#5856D6"),
            ("overdue_customers", "Overdue Customers", "âš ï¸", C["warning"]),
            ("today", "Due Today", "ðŸ“…", "#FF9500"),
            ("collection", "Collection This Month", "ðŸ’°", C["success"]),
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
        self.search.setPlaceholderText("Customer name, phone or bill numberâ€¦")
        self.search.setStyleSheet(FIELD_SS)
        self.credit_status = QComboBox()
        self.credit_status.addItems(
            ["All Status", "Due", "Overdue", "Paid", "Limit Exceeded"])
        self.customer_type = QComboBox()
        self.customer_type.addItems(
            ["All Types", "Regular", "Credit", "VIP", "Wholesale"])
        self.terms = QComboBox()
        self.terms.addItems(["All Terms", "7 days", "15 days", "30 days"])
        self.city = QComboBox()
        self.min_amount = QDoubleSpinBox(); self.max_amount = QDoubleSpinBox()
        for spin in (self.min_amount, self.max_amount):
            spin.setRange(0, 999999999); spin.setPrefix("â‚¹ ")
            spin.setStyleSheet(_NO_ARROW); spin.valueChanged.connect(self.refresh)
        for combo in (
            self.credit_status, self.customer_type, self.terms, self.city):
            _apply_combo_delegate(combo); combo.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        fl.addWidget(QLabel("Advanced Filter")); fl.addWidget(self.search, 1)
        fl.addWidget(self.credit_status); fl.addWidget(self.customer_type)
        fl.addWidget(self.terms); fl.addWidget(self.city)
        fl.addWidget(self.min_amount); fl.addWidget(self.max_amount)
        root.addWidget(filters)

        self.table = _table([
            "Customer Code", "Customer Name", "Phone", "Total Bills",
            "Total Credit", "Paid Amount", "Balance Due", "Oldest Due Date",
            "Days Overdue", "Credit Limit", "Credit Status", "Actions"])
        self.table.cellClicked.connect(self._cell_clicked)

        self.drawer = _card(); self.drawer.setMinimumWidth(460)
        self.drawer.setMaximumWidth(520); self.drawer.hide()
        dl = QVBoxLayout(self.drawer)
        drawer_top = QHBoxLayout()
        self.drawer_title = QLabel("Credit Detail")
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
        self.tabs = QTabWidget()
        self.bills_table = _table([
            "Bill", "Bill Date", "Due Date", "Bill", "Paid",
            "Balance", "Days", "Status"])
        self.payments_table = _table([
            "Date", "Receipt", "Amount", "Mode", "Reference", "Received By"])
        self.ledger_table = _table([
            "Date", "Type", "Reference", "Debit", "Credit", "Balance", "Notes"])
        self.reminders_table = _table([
            "Date", "Type", "Message", "Sent By", "Status"])
        for table, label in (
            (self.bills_table, "OUTSTANDING BILLS"),
            (self.payments_table, "PAYMENTS"),
            (self.ledger_table, "CREDIT LEDGER"),
            (self.reminders_table, "REMINDERS")):
            page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(table)
            self.tabs.addTab(page, label)
        dl.addWidget(self.tabs, 1)
        actions = QGridLayout()
        self.payment_btn = _button("ðŸ’³ Add Payment", True)
        self.reminder_btn = _button("ðŸ”” Log Reminder")
        self.call_btn = _button("ðŸ“ž Call Customer")
        self.block_btn = _button("â›” Block Credit")
        actions.addWidget(self.payment_btn, 0, 0)
        actions.addWidget(self.reminder_btn, 0, 1)
        actions.addWidget(self.call_btn, 1, 0)
        actions.addWidget(self.block_btn, 1, 1)
        dl.addLayout(actions)
        self.payment_btn.clicked.connect(self._add_payment)
        self.reminder_btn.clicked.connect(self._add_reminder)
        self.call_btn.clicked.connect(self._call_customer)
        self.block_btn.clicked.connect(self._block_credit)

        body = QHBoxLayout(); body.addWidget(self.table, 1); body.addWidget(self.drawer)
        root.addLayout(body, 1)
        self.refresh()

    def _matches(self, row):
        search = self.search.text().strip().casefold()
        bill_text = " ".join(
            str(bill.get("invoice_number") or "") for bill in row["bills"])
        if search and search not in " ".join([
                str(row.get("name") or ""), str(row.get("phone") or ""),
                str(row.get("code") or ""), bill_text]).casefold():
            return False
        if self.credit_status.currentIndex() > 0 and (
                row["credit_status"] != self.credit_status.currentText()):
            return False
        if self.customer_type.currentIndex() > 0 and (
                row.get("customer_type") != self.customer_type.currentText()):
            return False
        if self.city.currentIndex() > 0 and row.get("city") != self.city.currentText():
            return False
        if self.terms.currentIndex() > 0:
            wanted = int(self.terms.currentText().split()[0])
            if int(row.get("payment_terms") or 0) != wanted:
                return False
        balance = float(row.get("balance_due") or 0)
        if self.min_amount.value() and balance < self.min_amount.value():
            return False
        if self.max_amount.value() and balance > self.max_amount.value():
            return False
        return True

    def refresh(self, *_):
        all_rows = credit_rows(self.db)
        cities = sorted({row.get("city") for row in all_rows if row.get("city")})
        current = self.city.currentText()
        self.city.blockSignals(True); self.city.clear(); self.city.addItem("All Cities")
        self.city.addItems(cities)
        index = self.city.findText(current); self.city.setCurrentIndex(max(0, index))
        self.city.blockSignals(False)
        self.rows = [row for row in all_rows if self._matches(row)]
        self.table.setRowCount(0)
        for source in self.rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = [
                source.get("code"), source.get("name"), source.get("phone"),
                source.get("total_bills"), _money(source.get("total_credit")),
                _money(source.get("paid_amount")), _money(source.get("balance_due")),
                source.get("oldest_due_date"), source.get("days_overdue"),
                _money(source.get("credit_limit")), source.get("credit_status"),
                "ðŸ‘  ðŸ’³  ðŸ””  ðŸ“ž  â›”"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or "â€”"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 10:
                    color = {
                        "Paid": C["success"], "Due": C["blue"],
                        "Overdue": C["accent"], "Limit Exceeded": "#8B0000",
                        "Due Today": C["warning"]}.get(str(value), C["text2"])
                    item.setForeground(QBrush(QColor(color)))
                self.table.setItem(row, col, item)
        kpis = credit_kpis(self.db, all_rows)
        for key, label in self.kpi_labels.items():
            value = kpis[key]
            label.setText(
                _money(value) if key in ("due", "overdue", "today", "collection")
                else f"{int(value):,}")
        if self._selected:
            updated = next(
                (row for row in all_rows if row["code"] == self._selected["code"]),
                None)
            if updated:
                self._show_drawer(updated)

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
        self.drawer_title.setText(customer.get("name") or "Credit Detail")
        self.drawer_summary.setText(
            f"<b>Phone:</b> {customer.get('phone') or 'â€”'}<br>"
            f"<b>Customer Code:</b> {customer.get('code')}<br>"
            f"<b>Credit Limit:</b> {_money(customer.get('credit_limit'))}<br>"
            f"<b>Balance Due:</b> {_money(customer.get('balance_due'))}<br>"
            f"<b>Overdue Amount:</b> {_money(customer.get('overdue_amount'))}<br>"
            f"<b>Oldest Due:</b> {customer.get('oldest_due_date') or 'â€”'}<br>"
            f"<b>Status:</b> {customer.get('credit_status')}")
        self._fill(
            self.bills_table, customer["bills"],
            ["invoice_number", "sale_date", "due_date", "bill_amount",
             "paid_amount", "balance_amount", "days_overdue", "status"],
            money_columns=(3, 4, 5))
        payments = _rows(
            self.db, "SELECT * FROM customer_payments WHERE customer_code=? "
                     "ORDER BY payment_date DESC,id DESC", (customer["code"],))
        ledger = _rows(
            self.db, "SELECT * FROM customer_ledger WHERE customer_code=? "
                     "ORDER BY entry_date DESC,id DESC", (customer["code"],))
        reminders = _rows(
            self.db, "SELECT * FROM customer_reminders WHERE customer_code=? "
                     "ORDER BY reminder_date DESC,id DESC", (customer["code"],))
        self._fill(
            self.payments_table, payments,
            ["payment_date", "receipt_number", "amount", "payment_mode",
             "reference_number", "received_by"], money_columns=(2,))
        self._fill(
            self.ledger_table, ledger,
            ["entry_date", "entry_type", "invoice_number", "debit", "credit",
             "balance", "notes"], money_columns=(3, 4, 5))
        self._fill(
            self.reminders_table, reminders,
            ["reminder_date", "reminder_type", "message", "sent_by", "status"])
        self.drawer.show()

    def _add_payment(self):
        customer = self._selected
        if not customer:
            row = self.table.currentRow()
            customer = self.rows[row] if 0 <= row < len(self.rows) else None
        if not customer:
            QMessageBox.information(
                self, "Add Payment", "Select a credit customer first.")
            return
        if PaymentDialog(
                self.db, customer, self.current_user,
                self).exec() == QDialog.DialogCode.Accepted:
            self.refresh(); self.tabs.setCurrentIndex(1)

    def _add_reminder(self):
        if not self._selected:
            return
        dialog = QDialog(self); dialog.setWindowTitle("Log Collection Reminder")
        layout = QGridLayout(dialog)
        reminder_type = QComboBox()
        reminder_type.addItems(["Phone Call", "WhatsApp", "SMS", "In Person"])
        message = QTextEdit()
        message.setPlainText(
            f"Payment reminder: {_money(self._selected.get('balance_due'))} is due.")
        layout.addWidget(QLabel("Reminder Type"), 0, 0)
        layout.addWidget(reminder_type, 0, 1)
        layout.addWidget(QLabel("Message"), 1, 0)
        layout.addWidget(message, 1, 1)
        cancel = _button("Cancel"); save = _button("Save Reminder", True)
        cancel.clicked.connect(dialog.reject); save.clicked.connect(dialog.accept)
        layout.addWidget(cancel, 2, 0); layout.addWidget(save, 2, 1)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                INSERT INTO customer_reminders(
                    customer_code,reminder_date,reminder_type,message,sent_by,status)
                VALUES(?,?,?,?,?,'Logged')
            """, (
                self._selected["code"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reminder_type.currentText(), message.toPlainText().strip(),
                self.current_user))
        self._show_drawer(self._selected); self.tabs.setCurrentIndex(3)

    def _call_customer(self):
        if self._selected:
            QMessageBox.information(
                self, "Call Customer",
                f"{self._selected.get('name')}\n"
                f"Phone: {self._selected.get('phone') or 'Not available'}")

    def _block_credit(self):
        if not self._selected:
            return
        allow = 0 if self._selected.get("allow_credit") else 1
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE customers SET allow_credit=?,updated_at=? WHERE code=?",
                (allow, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 self._selected["code"]))
        self.refresh()


