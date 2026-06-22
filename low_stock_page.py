"""EvoAura Low Stock / Reorder Control Center."""

import sqlite3
from datetime import date, datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QComboBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QDialog, QSizePolicy,
)

from app_branding import apply_app_icon
from input_behavior import ensure_global_input_guard
from product_page import (
    C, FIELD_SS, _NO_ARROW, _apply_combo_delegate, init_product_table,
    PurchaseStockDialog,
)
from supplier_page import init_supplier_tables
from purchase_orders_page import PurchaseInvoiceDialog, init_purchase_tables


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
    return f"₹{float(value or 0):,.2f}"


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


def init_low_stock_tables(db):
    init_product_table(db)
    init_supplier_tables(db)
    init_purchase_tables(db)
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS low_stock_snoozes (
                product_code TEXT PRIMARY KEY,
                snoozed_until TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _sales_for_period(conn, code, days):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(invoice_items)")
        }
        invoice_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(invoices)")
        }
        if not columns or not invoice_columns:
            return 0
        code_col = next(
            (name for name in ("product_code", "item_code", "code")
             if name in columns), None)
        qty_col = next(
            (name for name in ("quantity", "qty") if name in columns), None)
        inv_item_col = next(
            (name for name in ("invoice_id", "invoice_number", "invoice_no")
             if name in columns), None)
        inv_col = next(
            (name for name in ("invoice_id", "invoice_number", "invoice_no")
             if name in invoice_columns), None)
        date_col = next(
            (name for name in ("date", "invoice_date", "created_at")
             if name in invoice_columns), None)
        if not all((code_col, qty_col, inv_item_col, inv_col, date_col)):
            return 0
        row = conn.execute(
            f"""SELECT COALESCE(SUM(ii.{qty_col}),0)
                FROM invoice_items ii
                JOIN invoices i ON i.{inv_col}=ii.{inv_item_col}
                WHERE ii.{code_col}=? AND date(i.{date_col})>=date(?)""",
            (code, cutoff),
        ).fetchone()
        return int(row[0] or 0)
    except sqlite3.Error:
        return 0


def get_reorder_rows(db, filters=None):
    filters = filters or {}
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        today = date.today().isoformat()
        rows = conn.execute("""
            SELECT p.*,
                   COALESCE(s.name,p.supplier_name,'') AS list_supplier,
                   COALESCE(ps.supplier_code,p.supplier_code,'') AS list_supplier_code,
                   COALESCE(NULLIF(ps.last_received_price,0),
                            NULLIF(ps.unit_price,0),
                            NULLIF(p.last_purchase_price,0),
                            p.purchase_price,0) AS effective_purchase_price,
                   COALESCE(ps.last_ordered_date,'') AS supplier_last_ordered,
                   COALESCE(ps.moq,p.min_order_qty,1) AS supplier_moq,
                   COALESCE((
                       SELECT invoice_number FROM purchase_invoice_logs pil
                       WHERE pil.product_code=p.item_code
                       ORDER BY purchase_date DESC,id DESC LIMIT 1
                   ),'') AS last_invoice_number,
                   COALESCE((
                       SELECT purchase_date FROM purchase_invoice_logs pil
                       WHERE pil.product_code=p.item_code
                       ORDER BY purchase_date DESC,id DESC LIMIT 1
                   ),ps.last_ordered_date,'') AS last_purchase_date
            FROM products p
            LEFT JOIN product_suppliers ps
              ON ps.id=(
                  SELECT linked.id FROM product_suppliers linked
                  WHERE linked.product_code=p.item_code
                  ORDER BY linked.is_primary DESC, linked.id DESC LIMIT 1
              )
            LEFT JOIN suppliers s ON s.code=ps.supplier_code
            LEFT JOIN low_stock_snoozes lss ON lss.product_code=p.item_code
            WHERE COALESCE(p.is_deleted,0)=0
              AND COALESCE(p.status,'Active')='Active'
              AND (COALESCE(p.stock,0)-COALESCE(p.damaged_stock,0)
                   -COALESCE(p.reserved_stock,0))<=COALESCE(p.reorder_level,0)
              AND COALESCE(p.reorder_level,0)>0
              AND (lss.snoozed_until IS NULL OR lss.snoozed_until<?)
            ORDER BY p.name
        """, (today,)).fetchall()
        result = []
        for source in rows:
            row = dict(source)
            available = max(
                0, int(row.get("stock") or 0)
                - int(row.get("damaged_stock") or 0)
                - int(row.get("reserved_stock") or 0))
            reorder_level = int(row.get("reorder_level") or 0)
            gap = max(0, reorder_level - available)
            configured = int(row.get("reorder_qty") or 0)
            moq = max(
                1, int(row.get("supplier_moq") or row.get("min_order_qty") or 1))
            suggested = max(configured, moq, gap)
            price = float(row.get("effective_purchase_price") or 0)
            sales_30 = _sales_for_period(conn, row["item_code"], 30)
            sales_90 = _sales_for_period(conn, row["item_code"], 90)
            if available <= 0:
                stock_status = "Out of Stock"
            elif available < reorder_level * 0.5:
                stock_status = "Critical"
            else:
                stock_status = "Low Stock"
            if available <= 0 or sales_30 >= max(1, reorder_level):
                priority = "High"
            elif sales_90 > 0:
                priority = "Medium"
            else:
                priority = "Low"
            row.update({
                "available_stock": available,
                "suggested_reorder_qty": suggested,
                "estimated_amount": suggested * price,
                "effective_purchase_price": price,
                "stock_status": stock_status,
                "priority": priority,
                "reorder_gap": gap,
                "sales_30": sales_30,
                "sales_90": sales_90,
            })
            result.append(row)

    def match(row):
        search = filters.get("search", "").casefold()
        if search and search not in " ".join(str(row.get(key) or "") for key in (
            "item_code", "name", "barcode")).casefold():
            return False
        for key, field in (
            ("category", "category"), ("brand", "brand"),
            ("supplier", "list_supplier"), ("status", "stock_status"),
            ("priority", "priority")):
            value = filters.get(key)
            if value and row.get(field) != value:
                return False
        minimum = float(filters.get("min_price") or 0)
        maximum = float(filters.get("max_price") or 0)
        price = float(row.get("effective_purchase_price") or 0)
        if minimum and price < minimum:
            return False
        if maximum and price > maximum:
            return False
        return True

    return [row for row in result if match(row)]


def get_reorder_kpis(rows):
    return {
        "low": sum(1 for row in rows if row["stock_status"] == "Low Stock"),
        "out": sum(1 for row in rows if row["stock_status"] == "Out of Stock"),
        "qty": sum(row["suggested_reorder_qty"] for row in rows),
        "value": sum(row["estimated_amount"] for row in rows),
        "suppliers": len({
            row["list_supplier_code"] for row in rows
            if row.get("list_supplier_code")}),
        "critical": sum(
            1 for row in rows if row["stock_status"] in ("Critical", "Out of Stock")),
    }


class LowStockPage(QWidget):
    def __init__(self, db_name, current_user="Admin", parent=None):
        super().__init__(parent)
        ensure_global_input_guard()
        apply_app_icon(self)
        self.db = db_name
        self.current_user = current_user
        self.rows = []
        init_low_stock_tables(db_name)
        self.setStyleSheet(f"background:{C['bg_light']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(10)
        top = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("Low Stock · Reorder Control Center")
        title.setStyleSheet(
            f"font-size:23px;font-weight:800;color:{C['text']};")
        subtitle = QLabel(
            "Decide what to order, how much to buy, and which supplier to contact")
        subtitle.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        title_wrap.addWidget(title); title_wrap.addWidget(subtitle)
        top.addLayout(title_wrap); top.addStretch()
        refresh_btn = _button("↻ Refresh")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        root.addLayout(top)

        self.kpi_labels = {}
        specs = [
            ("low", "Low Stock Items", "⚠️", C["warning"]),
            ("out", "Out of Stock", "⛔", C["accent"]),
            ("qty", "Reorder Qty Needed", "📦", C["blue"]),
            ("value", "Estimated Purchase Value", "💰", "#AF52DE"),
            ("suppliers", "Suppliers Involved", "🏭", "#00A67E"),
            ("critical", "Critical Items", "🔥", "#FF3B30"),
        ]
        grid = QGridLayout(); grid.setSpacing(9)
        for index, (key, label, icon, color) in enumerate(specs):
            card = _card(); card.setMinimumHeight(78)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(13, 9, 13, 9)
            heading = QLabel(f"{icon}  {label}")
            heading.setStyleSheet(
                f"color:{C['text3']};font-size:10px;font-weight:700;border:none;")
            value = QLabel("—")
            value.setStyleSheet(
                f"color:{C['text']};font-size:18px;font-weight:800;border:none;")
            layout.addWidget(heading); layout.addWidget(value)
            self.kpi_labels[key] = value
            grid.addWidget(card, index // 3, index % 3)
        root.addLayout(grid)

        filters = _card()
        filter_lay = QHBoxLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Product name, code or barcode…")
        self.search.setStyleSheet(FIELD_SS)
        self.category = QComboBox(); self.brand = QComboBox()
        self.supplier = QComboBox()
        self.status = QComboBox()
        self.status.addItems(["All Status", "Low Stock", "Critical", "Out of Stock"])
        self.priority = QComboBox()
        self.priority.addItems(["All Priority", "High", "Medium", "Low"])
        self.min_price = QDoubleSpinBox(); self.max_price = QDoubleSpinBox()
        for spin in (self.min_price, self.max_price):
            spin.setRange(0, 999999999); spin.setPrefix("₹ ")
            spin.setStyleSheet(_NO_ARROW); spin.valueChanged.connect(self.refresh)
        for combo in (
            self.category, self.brand, self.supplier, self.status, self.priority):
            _apply_combo_delegate(combo)
            combo.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        filter_lay.addWidget(QLabel("Advanced Filter"))
        filter_lay.addWidget(self.search, 1)
        filter_lay.addWidget(self.category)
        filter_lay.addWidget(self.brand)
        filter_lay.addWidget(self.supplier)
        filter_lay.addWidget(self.status)
        filter_lay.addWidget(self.priority)
        filter_lay.addWidget(self.min_price)
        filter_lay.addWidget(self.max_price)
        root.addWidget(filters)

        self.table = _table([
            "Product Code", "Product Name", "Category", "Brand", "Size", "Color",
            "Supplier", "Available Stock", "Reorder Level",
            "Suggested Reorder Qty", "Last Purchase Price", "Estimated Amount",
            "Last Purchase Date", "Stock Status", "Priority", "Actions"])
        self.table.cellClicked.connect(self._cell_clicked)

        self.drawer = _card()
        self.drawer.setMinimumWidth(350); self.drawer.setMaximumWidth(390)
        self.drawer.hide()
        drawer_lay = QVBoxLayout(self.drawer)
        drawer_top = QHBoxLayout()
        self.drawer_title = QLabel("Reorder Detail")
        self.drawer_title.setStyleSheet(
            f"font-size:17px;font-weight:800;color:{C['text']};border:none;")
        close = QPushButton("✕"); close.setFixedSize(28, 28)
        close.clicked.connect(self.drawer.hide)
        drawer_top.addWidget(self.drawer_title); drawer_top.addStretch()
        drawer_top.addWidget(close); drawer_lay.addLayout(drawer_top)
        self.drawer_image = QLabel("No Image")
        self.drawer_image.setFixedHeight(120)
        self.drawer_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drawer_image.setStyleSheet(
            f"background:{C['bg_panel']};border:1px dashed {C['border']};"
            "border-radius:10px;color:#8E8E93;")
        drawer_lay.addWidget(self.drawer_image)
        self.drawer_details = QLabel("—")
        self.drawer_details.setWordWrap(True)
        self.drawer_details.setTextFormat(Qt.TextFormat.RichText)
        self.drawer_details.setStyleSheet(
            f"font-size:12px;color:{C['text2']};border:none;")
        drawer_lay.addWidget(self.drawer_details)
        drawer_lay.addStretch()
        action_grid = QGridLayout()
        self.add_stock_btn = _button("📦 Add Stock")
        self.create_invoice_btn = _button("🧾 Create Purchase Invoice", True)
        self.view_product_btn = _button("👁 View Product")
        self.view_supplier_btn = _button("🏭 View Supplier")
        self.snooze_btn = _button("⏰ Snooze 7 Days")
        action_grid.addWidget(self.add_stock_btn, 0, 0)
        action_grid.addWidget(self.create_invoice_btn, 0, 1)
        action_grid.addWidget(self.view_product_btn, 1, 0)
        action_grid.addWidget(self.view_supplier_btn, 1, 1)
        action_grid.addWidget(self.snooze_btn, 2, 0, 1, 2)
        drawer_lay.addLayout(action_grid)
        self._selected = None
        self.add_stock_btn.clicked.connect(self._add_stock)
        self.create_invoice_btn.clicked.connect(self._create_invoice)
        self.view_product_btn.clicked.connect(self._view_product)
        self.view_supplier_btn.clicked.connect(self._view_supplier)
        self.snooze_btn.clicked.connect(self._snooze)

        body = QHBoxLayout()
        body.addWidget(self.table, 1); body.addWidget(self.drawer)
        root.addLayout(body, 1)
        self._reload_filter_options()
        self.refresh()

    def _reload_filter_options(self):
        with sqlite3.connect(self.db) as conn:
            categories = [row[0] for row in conn.execute(
                "SELECT DISTINCT category FROM products WHERE category<>'' ORDER BY category")]
            brands = [row[0] for row in conn.execute(
                "SELECT DISTINCT brand FROM products WHERE brand<>'' ORDER BY brand")]
            suppliers = [row[0] for row in conn.execute(
                "SELECT name FROM suppliers ORDER BY name")]
        for combo, label, values in (
            (self.category, "All Categories", categories),
            (self.brand, "All Brands", brands),
            (self.supplier, "All Suppliers", suppliers)):
            current = combo.currentText()
            combo.blockSignals(True); combo.clear(); combo.addItem(label)
            combo.addItems(values)
            index = combo.findText(current)
            combo.setCurrentIndex(max(0, index)); combo.blockSignals(False)

    def refresh(self, *_):
        filters = {
            "search": self.search.text().strip(),
            "category": "" if self.category.currentIndex() <= 0
                        else self.category.currentText(),
            "brand": "" if self.brand.currentIndex() <= 0 else self.brand.currentText(),
            "supplier": "" if self.supplier.currentIndex() <= 0
                        else self.supplier.currentText(),
            "status": "" if self.status.currentIndex() <= 0 else self.status.currentText(),
            "priority": "" if self.priority.currentIndex() <= 0
                        else self.priority.currentText(),
            "min_price": self.min_price.value(),
            "max_price": self.max_price.value(),
        }
        self.rows = get_reorder_rows(self.db, filters)
        self.table.setRowCount(0)
        for source in self.rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = [
                source.get("item_code"), source.get("name"), source.get("category"),
                source.get("brand"), source.get("size"), source.get("color"),
                source.get("list_supplier"), source.get("available_stock"),
                source.get("reorder_level"), source.get("suggested_reorder_qty"),
                _money(source.get("effective_purchase_price")),
                _money(source.get("estimated_amount")),
                source.get("last_purchase_date"), source.get("stock_status"),
                source.get("priority"), "👁  📦  🧾  ⏰"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or "—"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 13:
                    color = {
                        "Out of Stock": C["accent"], "Critical": "#FF3B30",
                        "Low Stock": C["warning"]}.get(str(value), C["text2"])
                    item.setForeground(QBrush(QColor(color)))
                if col == 14:
                    color = {
                        "High": C["accent"], "Medium": C["warning"],
                        "Low": C["success"]}.get(str(value), C["text2"])
                    item.setForeground(QBrush(QColor(color)))
                self.table.setItem(row, col, item)
        kpis = get_reorder_kpis(self.rows)
        for key, label in self.kpi_labels.items():
            value = kpis[key]
            label.setText(
                _money(value) if key == "value" else f"{int(value):,}")
        if self._selected:
            updated = next(
                (row for row in self.rows
                 if row["item_code"] == self._selected["item_code"]), None)
            if updated:
                self._show_drawer(updated)
            else:
                self.drawer.hide(); self._selected = None

    def _cell_clicked(self, row, column):
        if 0 <= row < len(self.rows):
            self._show_drawer(self.rows[row])

    def _show_drawer(self, product):
        self._selected = product
        self.drawer_title.setText(product.get("name") or "Reorder Detail")
        self.drawer_details.setText(
            f"<b>Code:</b> {product.get('item_code') or '—'}<br>"
            f"<b>Category / Brand:</b> {product.get('category') or '—'} / "
            f"{product.get('brand') or '—'}<br>"
            f"<b>Size / Color:</b> {product.get('size') or '—'} / "
            f"{product.get('color') or '—'}<br>"
            f"<b>Supplier:</b> {product.get('list_supplier') or '—'}<br><br>"
            f"<b>Available Stock:</b> {product.get('available_stock',0)}<br>"
            f"<b>Reorder Level:</b> {product.get('reorder_level',0)}<br>"
            f"<b>Suggested Qty:</b> {product.get('suggested_reorder_qty',0)}<br>"
            f"<b>Last Purchase Price:</b> "
            f"{_money(product.get('effective_purchase_price'))}<br>"
            f"<b>Estimated Amount:</b> {_money(product.get('estimated_amount'))}<br>"
            f"<b>Last Invoice:</b> {product.get('last_invoice_number') or '—'}<br>"
            f"<b>Last Purchase:</b> {product.get('last_purchase_date') or '—'}<br>"
            f"<b>Last 30 Days Sales:</b> {product.get('sales_30',0)}<br>"
            f"<b>Last 90 Days Sales:</b> {product.get('sales_90',0)}")
        image = product.get("image")
        self.drawer_image.clear()
        if image:
            pixmap = QPixmap(); pixmap.loadFromData(image)
            if not pixmap.isNull():
                self.drawer_image.setPixmap(pixmap.scaled(
                    315, 115, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            else:
                self.drawer_image.setText("No Image")
        else:
            self.drawer_image.setText("No Image")
        self.drawer.show()

    def _add_stock(self):
        if not self._selected:
            return
        product = self._selected
        dialog = PurchaseStockDialog(
            self.db, product["item_code"], product.get("name") or product["item_code"],
            int(product.get("stock") or 0), self.current_user, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _create_invoice(self):
        if not self._selected:
            return
        product = self._selected
        dialog = PurchaseInvoiceDialog(
            self.db, self.current_user, self,
            prefill={
                "supplier_code": product.get("list_supplier_code"),
                "product_code": product.get("item_code"),
                "quantity": product.get("suggested_reorder_qty"),
                "purchase_price": product.get("effective_purchase_price"),
            })
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _view_product(self):
        if not self._selected:
            return
        product = self._selected
        QMessageBox.information(
            self, "Product",
            f"{product.get('name')}\n\nCode: {product.get('item_code')}\n"
            f"Category: {product.get('category') or '—'}\n"
            f"Brand: {product.get('brand') or '—'}\n"
            f"Available Stock: {product.get('available_stock',0)}")

    def _view_supplier(self):
        if not self._selected:
            return
        code = self._selected.get("list_supplier_code")
        if not code:
            QMessageBox.information(
                self, "Supplier", "No supplier is linked to this product.")
            return
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM suppliers WHERE code=?", (code,)).fetchone()
        supplier = dict(row) if row else {}
        QMessageBox.information(
            self, "Supplier Profile",
            f"{supplier.get('name') or 'Supplier'}\n\n"
            f"Code: {code}\nPhone: {supplier.get('phone') or '—'}\n"
            f"GSTIN: {supplier.get('gstin') or '—'}\n"
            f"Balance: {_money(supplier.get('current_balance'))}")

    def _snooze(self):
        if not self._selected:
            return
        until = (date.today() + timedelta(days=7)).isoformat()
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                INSERT INTO low_stock_snoozes(
                    product_code,snoozed_until,reason,created_by,created_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(product_code) DO UPDATE SET
                    snoozed_until=excluded.snoozed_until,
                    reason=excluded.reason,created_by=excluded.created_by,
                    created_at=excluded.created_at
            """, (
                self._selected["item_code"], until, "Admin snoozed alert",
                self.current_user, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.drawer.hide(); self._selected = None; self.refresh()
