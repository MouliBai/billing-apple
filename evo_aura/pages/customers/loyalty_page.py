"""EvoAura Loyalty Control Center."""

import sqlite3
from datetime import date, datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QComboBox, QSpinBox, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog, QMessageBox,
    QTabWidget,
)

from core.app_branding import apply_app_icon
from core.input_behavior import ensure_global_input_guard
from core.theme import C, FIELD_SS
from core.ui_helpers import NO_ARROW as _NO_ARROW, apply_combo_delegate as _apply_combo_delegate
from pages.customers.customer_center_page import (
    init_customer_tables, get_customer_invoices, CustomerFormDialog,
)


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


TIER_ORDER = ["Bronze", "Silver", "Gold", "Platinum"]
TIER_RULES = {
    "Bronze": 0,
    "Silver": 500,
    "Gold": 1500,
    "Platinum": 3000,
}


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


def _table_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def init_loyalty_tables(db):
    init_customer_tables(db)
    with sqlite3.connect(db) as conn:
        customer_cols = _table_columns(conn, "customers")
        required_customer_cols = {
            "loyalty_enabled": "INTEGER DEFAULT 1",
            "loyalty_points": "INTEGER DEFAULT 0",
            "loyalty_tier": "TEXT DEFAULT 'Bronze'",
            "total_points_earned": "INTEGER DEFAULT 0",
            "total_points_redeemed": "INTEGER DEFAULT 0",
        }
        for name, ddl in required_customer_cols.items():
            if name not in customer_cols:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {name} {ddl}")
        conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS loyalty_settings (
            id INTEGER PRIMARY KEY CHECK(id=1),
            earn_per_amount REAL DEFAULT 100,
            earn_points INTEGER DEFAULT 1,
            redeem_point_value REAL DEFAULT 1,
            min_redeem_points INTEGER DEFAULT 50,
            updated_at TEXT DEFAULT ''
        );
        INSERT OR IGNORE INTO loyalty_settings(
            id,earn_per_amount,earn_points,redeem_point_value,min_redeem_points,updated_at)
        VALUES(1,100,1,1,50,CURRENT_TIMESTAMP);
        """)


def tier_for_points(points):
    points = int(points or 0)
    tier = "Bronze"
    for name in TIER_ORDER:
        if points >= TIER_RULES[name]:
            tier = name
    return tier


def loyalty_rows(db):
    customers = _rows(
        db, "SELECT * FROM customers WHERE loyalty_enabled=1 "
            "ORDER BY loyalty_points DESC,name")
    result = []
    for customer in customers:
        invoices = get_customer_invoices(db, customer)
        total_sales = sum(float(row.get("bill_amount") or 0) for row in invoices)
        last_sale = invoices[0].get("sale_date") if invoices else ""
        logs = _rows(
            db, "SELECT * FROM customer_loyalty_log WHERE customer_code=? "
                "ORDER BY action_date DESC,id DESC LIMIT 1",
            (customer["code"],))
        points = int(customer.get("loyalty_points") or 0)
        result.append({
            **customer,
            "loyalty_tier": customer.get("loyalty_tier") or tier_for_points(points),
            "total_sales": total_sales,
            "total_bills": len(invoices),
            "last_purchase_date": last_sale,
            "last_loyalty_action": logs[0]["action_date"] if logs else "",
        })
    return result


def loyalty_kpis(db, rows):
    month = date.today().strftime("%Y-%m")
    logs = _rows(
        db, "SELECT * FROM customer_loyalty_log WHERE substr(action_date,1,7)=?",
        (month,))
    top_customer = rows[0].get("name") if rows else "â€”"
    return {
        "customers": len(rows),
        "active_points": sum(int(row.get("loyalty_points") or 0) for row in rows),
        "earned_month": sum(int(row.get("points_earned") or 0) for row in logs),
        "redeemed_month": sum(int(row.get("points_redeemed") or 0) for row in logs),
        "gold_plus": sum(
            1 for row in rows if row.get("loyalty_tier") in ("Gold", "Platinum")),
        "top_customer": top_customer,
    }


class LoyaltyPointsDialog(QDialog):
    def __init__(self, db, user="Admin", customer=None, parent=None):
        super().__init__(parent)
        apply_app_icon(self)
        ensure_global_input_guard()
        self.db = db
        self.user = user
        self.customer = customer
        self.setWindowTitle("Add / Redeem Loyalty Points")
        self.setMinimumWidth(560)

        layout = QGridLayout(self)
        self.customer_box = QComboBox()
        self.customers = _rows(
            db, "SELECT code,name,phone,loyalty_points FROM customers "
                "WHERE loyalty_enabled=1 ORDER BY name")
        for source in self.customers:
            self.customer_box.addItem(
                f"{source['name']} Â· {source['phone'] or source['code']} "
                f"({int(source.get('loyalty_points') or 0)} pts)",
                source["code"])
        _apply_combo_delegate(self.customer_box)
        if customer:
            index = self.customer_box.findData(customer.get("code"))
            self.customer_box.setCurrentIndex(max(0, index))
            self.customer_box.setEnabled(False)

        self.action = QComboBox()
        self.action.addItems([
            "Manual Earn", "Manual Redeem", "Adjustment Add", "Adjustment Deduct"])
        _apply_combo_delegate(self.action)
        self.points = QSpinBox()
        self.points.setRange(1, 999999)
        self.points.setStyleSheet(_NO_ARROW)
        self.invoice = QLineEdit()
        self.invoice.setPlaceholderText("Invoice number / bill number")
        self.invoice.setStyleSheet(FIELD_SS)
        self.notes = QTextEdit()
        self.notes.setFixedHeight(85)
        self.balance_hint = QLabel("â€”")
        self.balance_hint.setStyleSheet(
            f"color:{C['text2']};font-size:12px;padding:6px;")

        fields = [
            ("Customer", self.customer_box), ("Action", self.action),
            ("Points", self.points), ("Invoice Number", self.invoice),
            ("Current Balance", self.balance_hint), ("Notes", self.notes),
        ]
        for row, (label, widget) in enumerate(fields):
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(widget, row, 1)

        cancel = _button("Cancel")
        save = _button("Save Loyalty Entry", True)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        layout.addWidget(cancel, len(fields), 0)
        layout.addWidget(save, len(fields), 1)
        self.customer_box.currentIndexChanged.connect(self._update_hint)
        self._update_hint()

    def _selected_customer(self):
        code = self.customer_box.currentData()
        return next((row for row in self.customers if row["code"] == code), None)

    def _update_hint(self):
        customer = self._selected_customer()
        points = int(customer.get("loyalty_points") or 0) if customer else 0
        self.balance_hint.setText(
            f"{points:,} points available Â· Tier: {tier_for_points(points)}")

    def _save(self):
        customer = self._selected_customer()
        if not customer:
            QMessageBox.warning(self, "Loyalty", "Select a customer.")
            return
        current = int(customer.get("loyalty_points") or 0)
        points = int(self.points.value())
        action = self.action.currentText()
        earned = points if action in ("Manual Earn", "Adjustment Add") else 0
        redeemed = points if action in ("Manual Redeem", "Adjustment Deduct") else 0
        if redeemed > current:
            QMessageBox.warning(
                self, "Loyalty", "Redeem/deduct points cannot exceed balance.")
            return
        new_balance = current + earned - redeemed
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                INSERT INTO customer_loyalty_log(
                    customer_code,action_date,action,invoice_number,points_earned,
                    points_redeemed,balance_points,notes)
                VALUES(?,?,?,?,?,?,?,?)
            """, (
                customer["code"], now[:10], action, self.invoice.text().strip(),
                earned, redeemed, new_balance, self.notes.toPlainText().strip()))
            conn.execute("""
                UPDATE customers
                   SET loyalty_points=?,
                       loyalty_tier=?,
                       total_points_earned=COALESCE(total_points_earned,0)+?,
                       total_points_redeemed=COALESCE(total_points_redeemed,0)+?,
                       updated_at=?
                 WHERE code=?
            """, (
                new_balance, tier_for_points(new_balance), earned, redeemed,
                now, customer["code"]))
        self.accept()


class LoyaltySettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        apply_app_icon(self)
        self.db = db
        self.setWindowTitle("Loyalty Rules")
        self.setMinimumWidth(520)
        row = _rows(db, "SELECT * FROM loyalty_settings WHERE id=1")
        settings = row[0] if row else {}
        layout = QGridLayout(self)
        self.earn_amount = QSpinBox()
        self.earn_amount.setRange(1, 999999)
        self.earn_amount.setPrefix("â‚¹ ")
        self.earn_amount.setValue(int(settings.get("earn_per_amount") or 100))
        self.earn_points = QSpinBox()
        self.earn_points.setRange(1, 9999)
        self.earn_points.setValue(int(settings.get("earn_points") or 1))
        self.redeem_value = QSpinBox()
        self.redeem_value.setRange(1, 9999)
        self.redeem_value.setPrefix("â‚¹ ")
        self.redeem_value.setValue(int(settings.get("redeem_point_value") or 1))
        self.min_redeem = QSpinBox()
        self.min_redeem.setRange(1, 999999)
        self.min_redeem.setSuffix(" pts")
        self.min_redeem.setValue(int(settings.get("min_redeem_points") or 50))
        for spin in (
            self.earn_amount, self.earn_points, self.redeem_value, self.min_redeem):
            spin.setStyleSheet(_NO_ARROW)
        fields = [
            ("Earn points for every sale amount", self.earn_amount),
            ("Points earned", self.earn_points),
            ("Redeem value per point", self.redeem_value),
            ("Minimum redeem points", self.min_redeem),
        ]
        for index, (label, widget) in enumerate(fields):
            layout.addWidget(QLabel(label), index, 0)
            layout.addWidget(widget, index, 1)
        hint = QLabel(
            "Tier rules: Bronze 0+ Â· Silver 500+ Â· Gold 1500+ Â· Platinum 3000+")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        layout.addWidget(hint, len(fields), 0, 1, 2)
        cancel = _button("Cancel")
        save = _button("Save Rules", True)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        layout.addWidget(cancel, len(fields) + 1, 0)
        layout.addWidget(save, len(fields) + 1, 1)

    def _save(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                INSERT INTO loyalty_settings(
                    id,earn_per_amount,earn_points,redeem_point_value,
                    min_redeem_points,updated_at)
                VALUES(1,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    earn_per_amount=excluded.earn_per_amount,
                    earn_points=excluded.earn_points,
                    redeem_point_value=excluded.redeem_point_value,
                    min_redeem_points=excluded.min_redeem_points,
                    updated_at=excluded.updated_at
            """, (
                self.earn_amount.value(), self.earn_points.value(),
                self.redeem_value.value(), self.min_redeem.value(),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.accept()


class LoyaltyPage(QWidget):
    def __init__(self, db_name, current_user="Admin", parent=None):
        super().__init__(parent)
        ensure_global_input_guard()
        apply_app_icon(self)
        self.db = db_name
        self.current_user = current_user
        self.rows = []
        self._selected = None
        init_loyalty_tables(db_name)
        self.setStyleSheet(f"background:{C['bg_light']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("Loyalty Control Center")
        title.setStyleSheet(
            f"font-size:23px;font-weight:800;color:{C['text']};")
        subtitle = QLabel(
            "Manage customer points, tiers, redemptions and loyalty activity")
        subtitle.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        top.addLayout(title_wrap)
        top.addStretch()
        self.add_btn = _button("+ Add / Redeem Points", True)
        self.rules_btn = _button("âš™ Loyalty Rules")
        self.add_btn.clicked.connect(self._add_points)
        self.rules_btn.clicked.connect(self._rules)
        top.addWidget(self.rules_btn)
        top.addWidget(self.add_btn)
        root.addLayout(top)

        self.kpi_labels = {}
        specs = [
            ("customers", "Loyalty Customers", "ðŸ‘¥", C["blue"]),
            ("active_points", "Active Point Balance", "â­", C["warning"]),
            ("earned_month", "Earned This Month", "âž•", C["success"]),
            ("redeemed_month", "Redeemed This Month", "ðŸŽ", C["accent"]),
            ("gold_plus", "Gold / Platinum", "ðŸ‘‘", "#5856D6"),
            ("top_customer", "Top Loyalty Customer", "ðŸ†", "#00A67E"),
        ]
        grid = QGridLayout()
        grid.setSpacing(9)
        for index, (key, label, icon, _color) in enumerate(specs):
            card = _card()
            card.setMinimumHeight(78)
            lay = QVBoxLayout(card)
            lay.setContentsMargins(13, 9, 13, 9)
            heading = QLabel(f"{icon}  {label}")
            heading.setStyleSheet(
                f"color:{C['text3']};font-size:10px;font-weight:700;border:none;")
            value = QLabel("â€”")
            value.setStyleSheet(
                f"color:{C['text']};font-size:18px;font-weight:800;border:none;")
            lay.addWidget(heading)
            lay.addWidget(value)
            self.kpi_labels[key] = value
            grid.addWidget(card, index // 3, index % 3)
        root.addLayout(grid)

        filters = _card()
        fl = QHBoxLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Customer name, phone or codeâ€¦")
        self.search.setStyleSheet(FIELD_SS)
        self.tier = QComboBox()
        self.tier.addItems(["All Tiers", *TIER_ORDER])
        self.status = QComboBox()
        self.status.addItems(["All Status", "Active", "Inactive", "Blocked"])
        self.points_filter = QComboBox()
        self.points_filter.addItems([
            "All Points", "No Points", "1 - 499", "500 - 1499",
            "1500 - 2999", "3000+"])
        for combo in (self.tier, self.status, self.points_filter):
            _apply_combo_delegate(combo)
            combo.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        fl.addWidget(QLabel("Advanced Filter"))
        fl.addWidget(self.search, 1)
        fl.addWidget(self.tier)
        fl.addWidget(self.points_filter)
        fl.addWidget(self.status)
        root.addWidget(filters)

        self.table = _table([
            "Customer Code", "Customer Name", "Phone", "Tier", "Points",
            "Earned", "Redeemed", "Purchase Value", "Last Purchase",
            "Last Activity", "Status", "Actions"])
        self.table.cellClicked.connect(self._cell_clicked)

        self.drawer = _card()
        self.drawer.setMinimumWidth(460)
        self.drawer.setMaximumWidth(520)
        self.drawer.hide()
        dl = QVBoxLayout(self.drawer)
        drawer_top = QHBoxLayout()
        self.drawer_title = QLabel("Loyalty Detail")
        self.drawer_title.setStyleSheet(
            f"font-size:17px;font-weight:800;color:{C['text']};border:none;")
        close = QPushButton("âœ•")
        close.setFixedSize(28, 28)
        close.clicked.connect(self.drawer.hide)
        drawer_top.addWidget(self.drawer_title)
        drawer_top.addStretch()
        drawer_top.addWidget(close)
        dl.addLayout(drawer_top)
        self.drawer_summary = QLabel("â€”")
        self.drawer_summary.setWordWrap(True)
        self.drawer_summary.setStyleSheet(
            f"font-size:12px;color:{C['text2']};border:none;")
        dl.addWidget(self.drawer_summary)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane{{border:1px solid {C['border']};border-radius:8px;}}
            QTabBar::tab{{padding:7px 8px;background:{C['bg_panel']};}}
            QTabBar::tab:selected{{background:{C['accent']};color:white;}}
        """)
        self.history_table = _table([
            "Date", "Action", "Invoice", "Earned", "Redeemed", "Balance", "Notes"])
        self.purchase_table = _table([
            "Invoice", "Date", "Qty", "Bill", "Paid", "Balance", "Status"])
        self.rules_table = _table(["Tier", "Required Points", "Reward Position"])
        for table, label in (
            (self.history_table, "POINT HISTORY"),
            (self.purchase_table, "PURCHASES"),
            (self.rules_table, "TIER RULES")):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(table)
            self.tabs.addTab(page, label)
        dl.addWidget(self.tabs, 1)
        actions = QGridLayout()
        self.add_selected_btn = _button("â­ Add / Redeem")
        self.edit_customer_btn = _button("âœ Edit Customer")
        self.toggle_btn = _button("Disable Loyalty")
        self.sync_btn = _button("Sync Tier", True)
        actions.addWidget(self.add_selected_btn, 0, 0)
        actions.addWidget(self.edit_customer_btn, 0, 1)
        actions.addWidget(self.toggle_btn, 1, 0)
        actions.addWidget(self.sync_btn, 1, 1)
        dl.addLayout(actions)
        self.add_selected_btn.clicked.connect(self._add_points_selected)
        self.edit_customer_btn.clicked.connect(self._edit_customer)
        self.toggle_btn.clicked.connect(self._toggle_loyalty)
        self.sync_btn.clicked.connect(self._sync_selected_tier)

        body = QHBoxLayout()
        body.addWidget(self.table, 1)
        body.addWidget(self.drawer)
        root.addLayout(body, 1)
        self.refresh()


    def _filters_match(self, row):
        search = self.search.text().strip().casefold()
        if search and search not in " ".join(str(row.get(key) or "") for key in (
                "code", "name", "phone")).casefold():
            return False
        if self.tier.currentIndex() > 0 and row.get("loyalty_tier") != self.tier.currentText():
            return False
        if self.status.currentIndex() > 0 and row.get("status") != self.status.currentText():
            return False
        points = int(row.get("loyalty_points") or 0)
        point_filter = self.points_filter.currentText()
        ranges = {
            "No Points": points == 0,
            "1 - 499": 1 <= points <= 499,
            "500 - 1499": 500 <= points <= 1499,
            "1500 - 2999": 1500 <= points <= 2999,
            "3000+": points >= 3000,
        }
        if point_filter in ranges and not ranges[point_filter]:
            return False
        return True

    def refresh(self, *_):
        all_rows = loyalty_rows(self.db)
        self.rows = [row for row in all_rows if self._filters_match(row)]
        self.table.setRowCount(0)
        for source in self.rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                source.get("code"), source.get("name"), source.get("phone"),
                source.get("loyalty_tier"), source.get("loyalty_points"),
                source.get("total_points_earned"),
                source.get("total_points_redeemed"), _money(source.get("total_sales")),
                source.get("last_purchase_date"), source.get("last_loyalty_action"),
                source.get("status"), "ðŸ‘  â­  âœ  â›”"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or "â€”"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4 and int(source.get("loyalty_points") or 0) > 0:
                    item.setForeground(QBrush(QColor(C["accent"])))
                if col == 3 and source.get("loyalty_tier") in ("Gold", "Platinum"):
                    item.setForeground(QBrush(QColor("#C08400")))
                self.table.setItem(row, col, item)
        kpis = loyalty_kpis(self.db, all_rows)
        for key, widget in self.kpi_labels.items():
            value = kpis[key]
            widget.setText(str(value) if key == "top_customer" else f"{int(value):,}")
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
            row = table.rowCount()
            table.insertRow(row)
            for col, key in enumerate(columns):
                value = source.get(key)
                text = _money(value) if col in money_columns else str(value or "â€”")
                table.setItem(row, col, QTableWidgetItem(text))

    def _cell_clicked(self, row, _column):
        if 0 <= row < len(self.rows):
            self._show_drawer(self.rows[row])

    def _show_drawer(self, customer):
        self._selected = customer
        points = int(customer.get("loyalty_points") or 0)
        next_tier = next(
            (tier for tier in TIER_ORDER if TIER_RULES[tier] > points), "")
        needed = TIER_RULES[next_tier] - points if next_tier else 0
        self.drawer_title.setText(customer.get("name") or "Customer")
        self.drawer_summary.setText(
            f"<b>Code:</b> {customer.get('code')}<br>"
            f"<b>Phone:</b> {customer.get('phone') or 'â€”'}<br>"
            f"<b>Tier:</b> {customer.get('loyalty_tier') or 'Bronze'}<br>"
            f"<b>Point Balance:</b> {points:,}<br>"
            f"<b>Total Earned:</b> {int(customer.get('total_points_earned') or 0):,}<br>"
            f"<b>Total Redeemed:</b> {int(customer.get('total_points_redeemed') or 0):,}<br>"
            f"<b>Next Tier:</b> {next_tier or 'Top tier'}"
            f"{f' Â· {needed:,} points needed' if next_tier else ''}")
        history = _rows(
            self.db, "SELECT * FROM customer_loyalty_log WHERE customer_code=? "
                     "ORDER BY action_date DESC,id DESC",
            (customer["code"],))
        purchases = get_customer_invoices(self.db, customer)
        self._fill(
            self.history_table, history,
            ["action_date", "action", "invoice_number", "points_earned",
             "points_redeemed", "balance_points", "notes"])
        self._fill(
            self.purchase_table, purchases,
            ["invoice_number", "sale_date", "total_qty", "bill_amount",
             "paid_amount", "balance_amount", "status"],
            money_columns=(3, 4, 5))
        rules = [
            {"tier": name, "points": TIER_RULES[name], "position": index + 1}
            for index, name in enumerate(TIER_ORDER)
        ]
        self._fill(self.rules_table, rules, ["tier", "points", "position"])
        self.toggle_btn.setText(
            "Enable Loyalty" if not int(customer.get("loyalty_enabled") or 0)
            else "Disable Loyalty")
        self.drawer.show()

    def _add_points(self):
        if LoyaltyPointsDialog(
                self.db, self.current_user, parent=self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _add_points_selected(self):
        if not self._selected:
            return
        if LoyaltyPointsDialog(
                self.db, self.current_user, self._selected,
                self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _rules(self):
        if LoyaltySettingsDialog(self.db, self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _edit_customer(self):
        if not self._selected:
            return
        if CustomerFormDialog(
                self.db, self.current_user, self._selected,
                self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _toggle_loyalty(self):
        if not self._selected:
            return
        new_value = 0 if int(self._selected.get("loyalty_enabled") or 0) else 1
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE customers SET loyalty_enabled=?,updated_at=? WHERE code=?",
                (new_value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 self._selected["code"]))
        self.drawer.hide()
        self._selected = None
        self.refresh()

    def _sync_selected_tier(self):
        if not self._selected:
            return
        points = int(self._selected.get("loyalty_points") or 0)
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE customers SET loyalty_tier=?,updated_at=? WHERE code=?",
                (tier_for_points(points),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 self._selected["code"]))
        self.refresh()


