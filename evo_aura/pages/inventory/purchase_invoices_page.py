"""EvoAura Purchase Invoice / Stock-In Control Center."""

import sqlite3
from datetime import date, datetime, timedelta

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox,
    QCheckBox, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialog, QMessageBox, QScrollArea, QSizePolicy,
)

from core.app_branding import apply_app_icon
from core.input_behavior import ensure_global_input_guard
from core.theme import C, FIELD_SS
from core.ui_helpers import NO_ARROW as _NO_ARROW, apply_combo_delegate as _apply_combo_delegate
from repositories.product_repository import init_product_table
from pages.inventory.supplier_page import init_supplier_tables


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
            border-radius:9px; padding:7px 15px; font-weight:700;
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


def init_purchase_tables(db):
    init_product_table(db)
    init_supplier_tables(db)
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            supplier_code TEXT DEFAULT '',
            supplier_name TEXT DEFAULT '',
            invoice_date TEXT DEFAULT '',
            purchase_date TEXT DEFAULT '',
            due_date TEXT DEFAULT '',
            gross_amount REAL DEFAULT 0,
            gst_amount REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            net_amount REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            balance_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Pending',
            stock_updated INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL,
            product_code TEXT NOT NULL,
            product_name TEXT DEFAULT '',
            category TEXT DEFAULT '',
            size TEXT DEFAULT '',
            color TEXT DEFAULT '',
            quantity INTEGER DEFAULT 0,
            purchase_price REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            gst_rate REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            net_line_amount REAL DEFAULT 0,
            stock_updated INTEGER DEFAULT 0
        );
        """)


def _rows(db, sql, params=()):
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def purchase_rows(db, filters=None):
    filters = filters or {}
    sql = """
        SELECT po.*,
               COUNT(DISTINCT poi.product_code) AS total_products,
               COALESCE(SUM(poi.quantity),0) AS total_quantity
        FROM purchase_orders po
        LEFT JOIN purchase_order_items poi ON poi.invoice_number=po.invoice_number
        WHERE 1=1
    """
    params = []
    if filters.get("search"):
        q = f"%{filters['search']}%"
        sql += """ AND (po.invoice_number LIKE ? OR po.supplier_name LIKE ?
                  OR EXISTS(
                    SELECT 1 FROM purchase_order_items x
                    WHERE x.invoice_number=po.invoice_number
                      AND (x.product_code LIKE ? OR x.product_name LIKE ?)))"""
        params += [q, q, q, q]
    if filters.get("supplier"):
        sql += " AND po.supplier_name=?"; params.append(filters["supplier"])
    if filters.get("payment"):
        sql += " AND po.payment_status=?"; params.append(filters["payment"])
    if filters.get("stock") in ("Yes", "No"):
        sql += " AND po.stock_updated=?"; params.append(
            1 if filters["stock"] == "Yes" else 0)
    if filters.get("status"):
        sql += " AND po.status=?"; params.append(filters["status"])
    sql += " GROUP BY po.id ORDER BY po.purchase_date DESC, po.id DESC"
    return _rows(db, sql, params)


def purchase_kpis(db):
    with sqlite3.connect(db) as conn:
        row = conn.execute("""
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN substr(purchase_date,1,7)=?
                                     THEN net_amount ELSE 0 END),0),
                   COALESCE(SUM(balance_amount),0),
                   COUNT(DISTINCT CASE WHEN status='Active' THEN supplier_code END),
                   COALESCE(MAX(purchase_date),'')
            FROM purchase_orders WHERE status<>'Cancelled'
        """, (date.today().strftime("%Y-%m"),)).fetchone()
        qty = conn.execute("""
            SELECT COALESCE(SUM(quantity),0) FROM purchase_order_items
            WHERE stock_updated=1
        """).fetchone()[0]
    return {
        "total": row[0] or 0, "month": row[1] or 0, "pending": row[2] or 0,
        "suppliers": row[3] or 0, "last": row[4] or "â€”", "stock": qty or 0,
    }


class PurchaseInvoiceDialog(QDialog):
    def __init__(self, db, current_user="Admin", parent=None, invoice=None,
                 prefill=None):
        super().__init__(parent)
        apply_app_icon(self)
        ensure_global_input_guard()
        self.db = db
        self.current_user = current_user
        self.invoice = invoice
        self.prefill = prefill or {}
        self.products = _rows(
            db, "SELECT * FROM products WHERE is_deleted=0 ORDER BY name")
        self.product_map = {
            f"{row['item_code']} Â· {row['name']}": row for row in self.products}
        self.suppliers = _rows(db, "SELECT * FROM suppliers ORDER BY name")
        self.supplier_map = {row["name"]: row for row in self.suppliers}
        self.setWindowTitle(
            "Edit Purchase Invoice" if invoice else "New Purchase Invoice")
        self.resize(1180, 760)
        root = QVBoxLayout(self)

        title = QLabel(self.windowTitle())
        title.setStyleSheet(
            f"font-size:21px;font-weight:800;color:{C['text']};")
        root.addWidget(title)

        header = _card(); grid = QGridLayout(header)
        grid.setContentsMargins(16, 14, 16, 14)
        self.supplier = QComboBox(); self.supplier.setEditable(True)
        self.supplier.addItem("")
        self.supplier.addItems(list(self.supplier_map))
        _apply_combo_delegate(self.supplier)
        self.supplier_code = QLabel("â€”"); self.gstin = QLabel("â€”")
        self.phone = QLabel("â€”"); self.terms = QLabel("â€”")
        self.balance = QLabel("â€”")
        self.invoice_no = QLineEdit()
        self.invoice_no.setPlaceholderText("Supplier invoice number")
        self.invoice_date = QDateEdit(QDate.currentDate())
        self.purchase_date = QDateEdit(QDate.currentDate())
        for widget in (self.invoice_date, self.purchase_date):
            widget.setCalendarPopup(True); widget.setDisplayFormat("dd-MM-yyyy")
        self.due_date = QLabel("â€”")
        self.notes = QLineEdit(); self.notes.setPlaceholderText("Optional notes")
        fields = [
            ("Supplier Name", self.supplier), ("Supplier Code", self.supplier_code),
            ("GSTIN", self.gstin), ("Phone", self.phone),
            ("Payment Terms", self.terms), ("Current Balance", self.balance),
            ("Invoice Number", self.invoice_no), ("Invoice Date", self.invoice_date),
            ("Purchase Date", self.purchase_date), ("Payment Due", self.due_date),
            ("Notes", self.notes),
        ]
        for index, (label, widget) in enumerate(fields):
            row, side = divmod(index, 2)
            grid.addWidget(QLabel(label), row, side * 2)
            grid.addWidget(widget, row, side * 2 + 1)
        root.addWidget(header)

        line_head = QHBoxLayout()
        line_head.addWidget(QLabel("Product Line Items"))
        line_head.addStretch()
        add_line = _button("+ Add Product")
        add_line.clicked.connect(self._add_line)
        line_head.addWidget(add_line)
        root.addLayout(line_head)

        self.lines = QTableWidget(0, 11)
        self.lines.setHorizontalHeaderLabels([
            "Product", "Code", "Category", "Size", "Color", "Qty",
            "Purchase Price", "Selling Price", "GST %", "Discount", "Remove"])
        self.lines.verticalHeader().setVisible(False)
        self.lines.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.lines.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.lines.setStyleSheet(TABLE_SS)
        root.addWidget(self.lines, 1)

        totals = _card(); totals_lay = QHBoxLayout(totals)
        self.update_stock = QCheckBox("Update stock immediately")
        self.update_stock.setChecked(True)
        self.paid = QDoubleSpinBox(); self.paid.setRange(0, 999999999)
        self.paid.setPrefix("â‚¹ "); self.paid.valueChanged.connect(self._recalc)
        self.gross_lbl = QLabel("â‚¹0.00"); self.gst_lbl = QLabel("â‚¹0.00")
        self.discount_lbl = QLabel("â‚¹0.00"); self.net_lbl = QLabel("â‚¹0.00")
        self.balance_lbl = QLabel("â‚¹0.00"); self.status_lbl = QLabel("Pending")
        totals_lay.addWidget(self.update_stock); totals_lay.addStretch()
        for label, widget in [
            ("Gross", self.gross_lbl), ("GST", self.gst_lbl),
            ("Discount", self.discount_lbl), ("Net", self.net_lbl),
            ("Paid", self.paid), ("Balance", self.balance_lbl),
            ("Status", self.status_lbl),
        ]:
            wrap = QVBoxLayout(); wrap.addWidget(QLabel(label)); wrap.addWidget(widget)
            totals_lay.addLayout(wrap)
        root.addWidget(totals)

        actions = QHBoxLayout(); actions.addStretch()
        cancel = _button("Cancel"); save = _button("Save Purchase Invoice", True)
        cancel.clicked.connect(self.reject); save.clicked.connect(self._save)
        actions.addWidget(cancel); actions.addWidget(save); root.addLayout(actions)

        self.supplier.currentTextChanged.connect(self._supplier_changed)
        self.purchase_date.dateChanged.connect(self._supplier_changed)
        self._add_line()
        self._apply_prefill()

    def _apply_prefill(self):
        if not self.prefill:
            return
        supplier_code = self.prefill.get("supplier_code")
        supplier = next(
            (row for row in self.suppliers if row.get("code") == supplier_code), None)
        if supplier:
            self.supplier.setCurrentText(supplier.get("name") or "")
        product_code = self.prefill.get("product_code")
        product_key = next(
            (key for key, row in self.product_map.items()
             if row.get("item_code") == product_code), None)
        if product_key:
            combo = self.lines.cellWidget(0, 0)
            combo.setCurrentText(product_key)
            self.lines.cellWidget(0, 5).setValue(
                int(self.prefill.get("quantity") or 1))
            price = float(self.prefill.get("purchase_price") or 0)
            if price:
                self.lines.cellWidget(0, 6).setValue(price)
        self._recalc()

    def _supplier_changed(self, *_):
        supplier = self.supplier_map.get(self.supplier.currentText(), {})
        self.supplier_code.setText(supplier.get("code") or "â€”")
        self.gstin.setText(supplier.get("gstin") or "â€”")
        self.phone.setText(
            supplier.get("phone") or supplier.get("mobile_number") or "â€”")
        days = int(supplier.get("payment_terms_days") or 0)
        self.terms.setText(f"{days} days")
        self.balance.setText(_money(supplier.get("current_balance")))
        due = self.purchase_date.date().addDays(days)
        self.due_date.setText(due.toString("dd-MM-yyyy"))

    def _spin(self, decimals=False):
        widget = QDoubleSpinBox() if decimals else QSpinBox()
        widget.setRange(0, 999999999)
        if decimals:
            widget.setDecimals(2)
        widget.setStyleSheet(_NO_ARROW)
        widget.valueChanged.connect(self._recalc)
        return widget

    def _add_line(self):
        row = self.lines.rowCount(); self.lines.insertRow(row)
        product = QComboBox(); product.setEditable(True)
        product.addItem(""); product.addItems(list(self.product_map))
        _apply_combo_delegate(product)
        product.currentTextChanged.connect(
            lambda _text, r=row: self._product_changed(r))
        self.lines.setCellWidget(row, 0, product)
        for col in range(1, 5):
            self.lines.setItem(row, col, QTableWidgetItem("â€”"))
        qty = self._spin(); price = self._spin(True); sell = self._spin(True)
        gst = self._spin(True); gst.setMaximum(100)
        discount = self._spin(True)
        self.lines.setCellWidget(row, 5, qty)
        self.lines.setCellWidget(row, 6, price)
        self.lines.setCellWidget(row, 7, sell)
        self.lines.setCellWidget(row, 8, gst)
        self.lines.setCellWidget(row, 9, discount)
        remove = QPushButton("âœ•"); remove.setFixedSize(28, 28)
        remove.clicked.connect(lambda _=False, r=row: self._remove_line(r))
        self.lines.setCellWidget(row, 10, remove)

    def _remove_line(self, row):
        if 0 <= row < self.lines.rowCount():
            self.lines.removeRow(row); self._recalc()

    def _product_changed(self, row):
        combo = self.lines.cellWidget(row, 0)
        product = self.product_map.get(combo.currentText(), {})
        values = [
            product.get("item_code"), product.get("category"),
            product.get("size"), product.get("color")]
        for col, value in enumerate(values, 1):
            self.lines.setItem(row, col, QTableWidgetItem(str(value or "â€”")))
        self.lines.cellWidget(row, 6).setValue(
            float(product.get("last_purchase_price")
                  or product.get("purchase_price") or 0))
        self.lines.cellWidget(row, 7).setValue(
            float(product.get("selling_price") or 0))
        gst = str(product.get("purchase_gst") or "0").replace("%", "")
        try: self.lines.cellWidget(row, 8).setValue(float(gst))
        except ValueError: pass
        self._recalc()

    def _line_data(self):
        result = []
        for row in range(self.lines.rowCount()):
            combo = self.lines.cellWidget(row, 0)
            product = self.product_map.get(combo.currentText(), {})
            qty = int(self.lines.cellWidget(row, 5).value())
            if not product or qty <= 0:
                continue
            price = self.lines.cellWidget(row, 6).value()
            selling = self.lines.cellWidget(row, 7).value()
            gst = self.lines.cellWidget(row, 8).value()
            discount = self.lines.cellWidget(row, 9).value()
            gross = qty * price
            gst_amount = gross * gst / 100
            result.append({
                "product": product, "qty": qty, "price": price,
                "selling": selling, "gst": gst, "discount": discount,
                "gross": gross, "gst_amount": gst_amount,
                "net": gross + gst_amount - discount,
            })
        return result

    def _recalc(self, *_):
        lines = self._line_data()
        gross = sum(x["gross"] for x in lines)
        gst = sum(x["gst_amount"] for x in lines)
        discount = sum(x["discount"] for x in lines)
        net = gross + gst - discount
        paid = min(self.paid.value(), net)
        balance = max(0, net - paid)
        status = "Paid" if net and balance <= 0 else (
            "Partial" if paid > 0 else "Pending")
        self.gross_lbl.setText(_money(gross)); self.gst_lbl.setText(_money(gst))
        self.discount_lbl.setText(_money(discount)); self.net_lbl.setText(_money(net))
        self.balance_lbl.setText(_money(balance)); self.status_lbl.setText(status)

    def _save(self):
        supplier = self.supplier_map.get(self.supplier.currentText())
        number = self.invoice_no.text().strip()
        lines = self._line_data()
        if not supplier:
            QMessageBox.warning(self, "Validation", "Select a supplier."); return
        if not number:
            QMessageBox.warning(self, "Validation", "Invoice number is required."); return
        if not lines:
            QMessageBox.warning(self, "Validation", "Add at least one product."); return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        gross = sum(x["gross"] for x in lines)
        gst_amount = sum(x["gst_amount"] for x in lines)
        discount = sum(x["discount"] for x in lines)
        net = gross + gst_amount - discount
        paid = min(self.paid.value(), net); balance = net - paid
        status = "Paid" if balance <= 0 else ("Partial" if paid else "Pending")
        stock_now = self.update_stock.isChecked()
        try:
            with sqlite3.connect(self.db) as conn:
                conn.execute("""
                    INSERT INTO purchase_orders(
                        invoice_number,supplier_code,supplier_name,invoice_date,
                        purchase_date,due_date,gross_amount,gst_amount,
                        discount_amount,net_amount,paid_amount,balance_amount,
                        payment_status,stock_updated,status,notes,created_by,
                        created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    number, supplier["code"], supplier["name"],
                    self.invoice_date.date().toString("yyyy-MM-dd"),
                    self.purchase_date.date().toString("yyyy-MM-dd"),
                    QDate.fromString(self.due_date.text(), "dd-MM-yyyy").toString(
                        "yyyy-MM-dd"),
                    gross, gst_amount, discount, net, paid, balance, status,
                    int(stock_now), "Active", self.notes.text().strip(),
                    self.current_user, now, now))
                for line in lines:
                    product = line["product"]; code = product["item_code"]
                    conn.execute("""
                        INSERT INTO purchase_order_items(
                            invoice_number,product_code,product_name,category,size,
                            color,quantity,purchase_price,selling_price,gst_rate,
                            discount_amount,line_total,net_line_amount,stock_updated)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        number, code, product.get("name"), product.get("category"),
                        product.get("size"), product.get("color"), line["qty"],
                        line["price"], line["selling"], line["gst"],
                        line["discount"], line["gross"], line["net"], int(stock_now)))
                    old_stock = int(product.get("stock") or 0)
                    new_stock = old_stock + line["qty"] if stock_now else old_stock
                    conn.execute("""
                        INSERT INTO purchase_invoice_logs(
                            product_code,supplier_code,supplier_name,invoice_number,
                            invoice_date,purchase_date,quantity,purchase_price,
                            selling_price,gst_rate,discount_amount,gross_amount,
                            gst_amount,net_amount,paid_amount,balance_amount,
                            payment_status,stock_after,notes,created_at,created_by)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        code, supplier["code"], supplier["name"], number,
                        self.invoice_date.date().toString("yyyy-MM-dd"),
                        self.purchase_date.date().toString("yyyy-MM-dd"),
                        line["qty"], line["price"], line["selling"], line["gst"],
                        line["discount"], line["gross"], line["gst_amount"],
                        line["net"], paid * line["net"] / net if net else 0,
                        balance * line["net"] / net if net else 0, status,
                        new_stock, self.notes.text().strip(), now, self.current_user))
                    if stock_now:
                        conn.execute("""
                            UPDATE products SET stock=?,purchase_price=?,
                                last_purchase_price=?,purchase_gst=?,selling_price=?,
                                last_stock_updated=?,updated_at=?,updated_by=?
                            WHERE item_code=?
                        """, (
                            new_stock, line["price"], line["price"],
                            f"{line['gst']:g}%", line["selling"], now, now,
                            self.current_user, code))
                        conn.execute("""
                            INSERT INTO stock_update_logs(
                                product_code,action_type,reference_number,
                                supplier_name,qty_in,qty_out,old_stock,new_stock,
                                reason,updated_by,notes,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            code, "Purchase Stock In", number, supplier["name"],
                            line["qty"], 0, old_stock, new_stock,
                            "Purchase Invoice", self.current_user,
                            self.notes.text().strip(), now))
                    conn.execute("""
                        INSERT INTO product_suppliers(
                            product_code,supplier_code,unit_price,last_received_price,
                            last_ordered_date,is_primary)
                        VALUES(?,?,?,?,?,1)
                        ON CONFLICT(product_code,supplier_code) DO UPDATE SET
                            unit_price=excluded.unit_price,
                            last_received_price=excluded.last_received_price,
                            last_ordered_date=excluded.last_ordered_date
                    """, (
                        code, supplier["code"], line["price"], line["price"],
                        self.purchase_date.date().toString("yyyy-MM-dd")))
                conn.execute("""
                    INSERT INTO supplier_ledger(
                        supplier_code,entry_date,entry_type,reference_number,
                        invoice_number,debit,credit,balance,payment_mode,notes,
                        created_by,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    supplier["code"],
                    self.purchase_date.date().toString("yyyy-MM-dd"),
                    "Purchase Invoice", number, number, net, paid, balance, "",
                    self.notes.text().strip(), self.current_user, now))
                conn.execute(
                    "UPDATE suppliers SET current_balance="
                    "COALESCE(current_balance,0)+? WHERE code=?",
                    (balance, supplier["code"]))
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self, "Duplicate Invoice", "This invoice number already exists.")
            return
        self.accept()


class PurchaseOrdersPage(QWidget):
    def __init__(self, db_name, current_user="Admin", parent=None):
        super().__init__(parent)
        ensure_global_input_guard()
        apply_app_icon(self)
        self.db = db_name; self.current_user = current_user
        init_purchase_tables(db_name)
        self.rows = []
        self.setStyleSheet(f"background:{C['bg_light']};")
        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("Purchase Invoice / Stock-In")
        title.setStyleSheet(
            f"font-size:23px;font-weight:800;color:{C['text']};")
        subtitle = QLabel(
            "Supplier invoices, product purchases, stock updates and payments")
        subtitle.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        title_wrap.addWidget(title); title_wrap.addWidget(subtitle)
        top.addLayout(title_wrap); top.addStretch()
        new_btn = _button("+ New Purchase Invoice", True)
        new_btn.clicked.connect(self._new_invoice); top.addWidget(new_btn)
        root.addLayout(top)

        self.kpi_labels = {}
        kpi_grid = QGridLayout(); kpi_grid.setSpacing(9)
        specs = [
            ("total", "Total Purchase Invoices", "ðŸ§¾", C["blue"]),
            ("month", "This Month Purchase", "ðŸ“…", "#5856D6"),
            ("pending", "Pending Payments", "â³", C["accent"]),
            ("stock", "Total Stock Added", "ðŸ“¦", C["success"]),
            ("suppliers", "Active Suppliers", "ðŸ­", C["warning"]),
            ("last", "Last Purchase", "ðŸ•’", "#AF52DE"),
        ]
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
            kpi_grid.addWidget(card, index // 3, index % 3)
        root.addLayout(kpi_grid)

        filters = _card(); fl = QHBoxLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Invoice no, supplier, product code or product nameâ€¦")
        self.search.setStyleSheet(FIELD_SS)
        self.supplier = QComboBox(); self.supplier.addItem("All Suppliers")
        self.payment = QComboBox()
        self.payment.addItems(["All Payments", "Paid", "Partial", "Pending"])
        self.stock = QComboBox()
        self.stock.addItems(["All Stock", "Yes", "No"])
        self.status = QComboBox()
        self.status.addItems(["All Status", "Active", "Cancelled"])
        for combo in (self.supplier, self.payment, self.stock, self.status):
            _apply_combo_delegate(combo)
            combo.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        fl.addWidget(QLabel("Advanced Filter"))
        fl.addWidget(self.search, 1)
        fl.addWidget(self.supplier); fl.addWidget(self.payment)
        fl.addWidget(self.stock); fl.addWidget(self.status)
        root.addWidget(filters)

        self.table = _table([
            "Invoice No", "Date", "Supplier", "Products", "Qty", "Net Amount",
            "Paid", "Balance", "Payment Status", "Stock Updated", "Created By",
            "Actions"])
        self.table.cellClicked.connect(self._cell_clicked)

        self.drawer = _card(); self.drawer.setFixedWidth(350); self.drawer.hide()
        dl = QVBoxLayout(self.drawer)
        drawer_top = QHBoxLayout()
        self.drawer_title = QLabel("Invoice Detail")
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
        self.drawer_items = _table([
            "Product", "Qty", "Purchase", "Selling", "Total"])
        dl.addWidget(self.drawer_items, 1)
        self.drawer_payment = QLabel("Payment history appears in Supplier Ledger.")
        self.drawer_payment.setWordWrap(True)
        dl.addWidget(self.drawer_payment)

        body = QHBoxLayout(); body.addWidget(self.table, 1); body.addWidget(self.drawer)
        root.addLayout(body, 1)
        self.refresh()

    def refresh(self, *_):
        suppliers = _rows(self.db, "SELECT name FROM suppliers ORDER BY name")
        current = self.supplier.currentText()
        self.supplier.blockSignals(True); self.supplier.clear()
        self.supplier.addItem("All Suppliers")
        self.supplier.addItems([row["name"] for row in suppliers])
        index = self.supplier.findText(current)
        self.supplier.setCurrentIndex(max(0, index))
        self.supplier.blockSignals(False)
        filters = {
            "search": self.search.text().strip(),
            "supplier": "" if self.supplier.currentText() == "All Suppliers"
                        else self.supplier.currentText(),
            "payment": "" if self.payment.currentText() == "All Payments"
                       else self.payment.currentText(),
            "stock": "" if self.stock.currentText() == "All Stock"
                     else self.stock.currentText(),
            "status": "" if self.status.currentText() == "All Status"
                      else self.status.currentText(),
        }
        self.rows = purchase_rows(self.db, filters)
        self.table.setRowCount(0)
        for row_data in self.rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = [
                row_data.get("invoice_number"), row_data.get("purchase_date"),
                row_data.get("supplier_name"), row_data.get("total_products"),
                row_data.get("total_quantity"), _money(row_data.get("net_amount")),
                _money(row_data.get("paid_amount")), _money(row_data.get("balance_amount")),
                row_data.get("payment_status"),
                "Yes" if row_data.get("stock_updated") else "No",
                row_data.get("created_by"), "ðŸ‘  ðŸ’³  ðŸ“¦  â›”"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or "â€”"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 8:
                    color = {
                        "Paid": C["success"], "Partial": C["warning"],
                        "Pending": C["accent"]}.get(str(value), C["text2"])
                    item.setForeground(QBrush(QColor(color)))
                self.table.setItem(row, col, item)
        kpis = purchase_kpis(self.db)
        for key, label in self.kpi_labels.items():
            value = kpis[key]
            label.setText(
                _money(value) if key in ("month", "pending")
                else f"{int(value):,}" if key in ("total", "stock", "suppliers")
                else str(value))

    def _new_invoice(self):
        dialog = PurchaseInvoiceDialog(self.db, self.current_user, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _cell_clicked(self, row, column):
        if not (0 <= row < len(self.rows)):
            return
        if column in (0, 11):
            self._show_drawer(self.rows[row])

    def _show_drawer(self, invoice):
        number = invoice.get("invoice_number", "")
        self.drawer_title.setText(f"Invoice Â· {number}")
        self.drawer_summary.setText(
            f"<b>Supplier:</b> {invoice.get('supplier_name') or 'â€”'}<br>"
            f"<b>Invoice Date:</b> {invoice.get('invoice_date') or 'â€”'}<br>"
            f"<b>Purchase Date:</b> {invoice.get('purchase_date') or 'â€”'}<br>"
            f"<b>Net:</b> {_money(invoice.get('net_amount'))}<br>"
            f"<b>Paid:</b> {_money(invoice.get('paid_amount'))}<br>"
            f"<b>Balance:</b> {_money(invoice.get('balance_amount'))}<br>"
            f"<b>Status:</b> {invoice.get('payment_status') or 'â€”'}<br>"
            f"<b>Stock Updated:</b> {'Yes' if invoice.get('stock_updated') else 'No'}")
        items = _rows(
            self.db, "SELECT * FROM purchase_order_items WHERE invoice_number=?",
            (number,))
        self.drawer_items.setRowCount(0)
        for data in items:
            row = self.drawer_items.rowCount(); self.drawer_items.insertRow(row)
            values = [
                data.get("product_name"), data.get("quantity"),
                _money(data.get("purchase_price")), _money(data.get("selling_price")),
                _money(data.get("net_line_amount"))]
            for col, value in enumerate(values):
                self.drawer_items.setItem(row, col, QTableWidgetItem(str(value)))
        self.drawer.show()


PurchaseOrdersPage.refresh_light = PurchaseOrdersPage.refresh

