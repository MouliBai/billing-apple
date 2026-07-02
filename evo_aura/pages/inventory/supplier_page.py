"""
EvoAura Supplier Management â€” Textile / Men's Wear
===================================================
Supplier master, purchase/invoice tracking, supplier inventory and insights.
No batch, manufacture-date, expiry-date or FMCG/pharma fields are used.
"""

import datetime
import sqlite3
from collections import defaultdict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QMenu,
    QDateEdit,
    QVBoxLayout,
    QWidget,
)

from core.app_branding import apply_app_icon
from core.input_behavior import ensure_global_input_guard
from core.theme import C, FIELD_SS, LABEL_SS, SEC_HDR_SS
from core.ui_helpers import NO_ARROW as _NO_ARROW, apply_combo_delegate as _apply_combo_delegate


TABLE_SS = f"""
QTableWidget {{
    background:{C['bg_white']}; border:1px solid {C['border']};
    border-radius:10px; gridline-color:#ECECF0; font-size:12px;
    selection-background-color:#FFF0F2; selection-color:{C['text']};
}}
QHeaderView::section {{
    background:#F5F5F7; color:{C['text2']}; font-size:11px;
    font-weight:700; padding:9px 6px; border:none;
    border-bottom:1px solid {C['border']};
}}
QTableWidget::item {{ padding:7px; }}
"""

BTN_PRIMARY = f"""
QPushButton {{
    background:{C['accent']}; color:white; border:none; border-radius:9px;
    padding:8px 16px; font-size:12px; font-weight:700;
}}
QPushButton:hover {{ background:{C['accent_dark']}; }}
"""

BTN_SECONDARY = f"""
QPushButton {{
    background:white; color:{C['text']}; border:1px solid {C['border']};
    border-radius:9px; padding:8px 14px; font-size:12px; font-weight:600;
}}
QPushButton:hover {{ border-color:{C['accent']}; background:#FFF8F9; }}
"""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Database and analytics
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _rows(db, sql, params=()):
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except Exception as exc:
        print("supplier query:", exc)
        return []


def _row(db, sql, params=()):
    rows = _rows(db, sql, params)
    return rows[0] if rows else {}


def _money(value):
    return f"â‚¹{float(value or 0):,.2f}"


def _number(value):
    value = float(value or 0)
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"


def _gst_percent(text):
    try:
        return float(str(text or "0").replace("%", "").strip())
    except Exception:
        return 0.0


def init_supplier_tables(db):
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS suppliers (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            gstin TEXT DEFAULT '',
            contact_person TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            pincode TEXT DEFAULT '',
            payment_terms_days INTEGER DEFAULT 30,
            credit_limit REAL DEFAULT 0,
            current_balance REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            created_by TEXT DEFAULT 'system'
        );

        CREATE TABLE IF NOT EXISTS supplier_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            purchase_date TEXT DEFAULT '',
            discount_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            net_amount REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            balance_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(supplier_code, invoice_number)
        );

        CREATE TABLE IF NOT EXISTS supplier_invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            product_code TEXT NOT NULL,
            product_name TEXT DEFAULT '',
            category TEXT DEFAULT '',
            size TEXT DEFAULT '',
            color TEXT DEFAULT '',
            quantity REAL DEFAULT 0,
            purchase_price REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            total_value REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS supplier_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code TEXT NOT NULL,
            entry_date TEXT DEFAULT '',
            entry_type TEXT DEFAULT '',
            reference_number TEXT DEFAULT '',
            invoice_number TEXT DEFAULT '',
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            payment_mode TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS supplier_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code TEXT NOT NULL,
            activity_at TEXT DEFAULT CURRENT_TIMESTAMP,
            action TEXT DEFAULT '',
            reference TEXT DEFAULT '',
            old_value TEXT DEFAULT '',
            new_value TEXT DEFAULT '',
            user TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        );
        """)
        supplier_columns = {
            "contact_person": "TEXT DEFAULT ''",
            "mobile_number": "TEXT DEFAULT ''",
            "whatsapp_number": "TEXT DEFAULT ''",
            "pan_number": "TEXT DEFAULT ''",
            "city": "TEXT DEFAULT ''",
            "state": "TEXT DEFAULT ''",
            "pincode": "TEXT DEFAULT ''",
            "country": "TEXT DEFAULT 'India'",
            "address_line1": "TEXT DEFAULT ''",
            "address_line2": "TEXT DEFAULT ''",
            "payment_terms_days": "INTEGER DEFAULT 30",
            "payment_terms": "TEXT DEFAULT 'Net 30'",
            "credit_limit": "REAL DEFAULT 0",
            "current_balance": "REAL DEFAULT 0",
            "account_holder_name": "TEXT DEFAULT ''",
            "bank_name": "TEXT DEFAULT ''",
            "branch_name": "TEXT DEFAULT ''",
            "account_number": "TEXT DEFAULT ''",
            "ifsc": "TEXT DEFAULT ''",
            "upi_id": "TEXT DEFAULT ''",
            "default_lead_time": "INTEGER DEFAULT 0",
            "preferred_payment_method": "TEXT DEFAULT ''",
            "supplier_category": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT 'Active'",
            "notes": "TEXT DEFAULT ''",
            "created_by": "TEXT DEFAULT 'system'",
        }
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(suppliers)").fetchall()
        }
        for column, definition in supplier_columns.items():
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE suppliers ADD COLUMN {column} {definition}"
                )


def _supplier_product_rows(db, supplier):
    code = supplier.get("code", "")
    name = supplier.get("name", "")
    return _rows(db, """
        SELECT DISTINCT
            p.item_code AS product_code,
            p.name AS product_name,
            COALESCE(p.category,'') AS category,
            COALESCE(p.brand,'') AS brand,
            COALESCE(p.stock,0) AS stock,
            COALESCE(p.reserved_stock,0) AS reserved_stock,
            COALESCE(p.damaged_stock,0) AS damaged_stock,
            COALESCE(p.returned_stock,0) AS returned_stock,
            COALESCE(p.total_qty_sold,0) AS sold_qty,
            COALESCE(p.reorder_level,0) AS reorder_level,
            COALESCE(p.purchase_price,0) AS purchase_price,
            COALESCE(NULLIF(ps.unit_price,0), NULLIF(p.last_purchase_price,0),
                     p.purchase_price,0) AS last_purchase_price,
            COALESCE(p.selling_price,0) AS selling_price,
            COALESCE(ps.last_ordered_date,'') AS linked_purchase_date,
            COALESCE(ps.supplier_product_code,'') AS supplier_product_code,
            COALESCE(ps.moq,1) AS moq,
            COALESCE(p.status,'Active') AS status
        FROM products p
        LEFT JOIN product_suppliers ps
          ON ps.product_code=p.item_code AND ps.supplier_code=?
        WHERE COALESCE(p.is_deleted,0)=0
          AND (
              ps.supplier_code=?
              OR LOWER(COALESCE(p.supplier_name,''))=LOWER(?)
          )
        ORDER BY p.name
    """, (code, code, name))


def _variant_labels(db, product_codes):
    result = defaultdict(lambda: {"size": [], "color": []})
    if not product_codes:
        return result
    marks = ",".join("?" for _ in product_codes)
    rows = _rows(db, f"""
        SELECT product_code, variant_group, size
        FROM product_variants
        WHERE product_code IN ({marks}) AND COALESCE(stock,0)>=0
        ORDER BY product_code, size
    """, tuple(product_codes))
    for row in rows:
        target = "color" if row["variant_group"] == "Color" else "size"
        value = str(row.get("size") or "").strip()
        if value and value not in result[row["product_code"]][target]:
            result[row["product_code"]][target].append(value)
    return result


def _purchase_log_rows(db, product_codes):
    if not product_codes:
        return []
    marks = ",".join("?" for _ in product_codes)
    return _rows(db, f"""
        SELECT pl.*,
               pl.quantity AS stock_qty,
               pl.invoice_number AS invoice_no,
               CAST(pl.gst_rate AS TEXT) AS purchase_gst,
               p.name AS product_name, p.category,
               COALESCE(NULLIF(pl.selling_price,0),p.selling_price,0) AS selling_price
        FROM purchase_invoice_logs pl
        JOIN products p ON p.item_code=pl.product_code
        WHERE pl.product_code IN ({marks})
        ORDER BY pl.purchase_date DESC, pl.id DESC
    """, tuple(product_codes))


def get_supplier_inventory(db, supplier_code):
    supplier = _row(db, "SELECT * FROM suppliers WHERE code=?", (supplier_code,))
    products = _supplier_product_rows(db, supplier)
    codes = [row["product_code"] for row in products]
    variants = _variant_labels(db, codes)
    logs = _purchase_log_rows(db, codes)
    by_product = defaultdict(list)
    for log in logs:
        by_product[log["product_code"]].append(log)

    inventory = []
    for product in products:
        code = product["product_code"]
        purchases = by_product.get(code, [])
        total_purchased = sum(float(x.get("stock_qty") or 0) for x in purchases)
        if not total_purchased:
            total_purchased = float(product.get("stock") or 0) + float(
                product.get("sold_qty") or 0
            )
        weighted_qty = sum(float(x.get("stock_qty") or 0) for x in purchases)
        weighted_value = sum(
            float(x.get("stock_qty") or 0) * float(x.get("purchase_price") or 0)
            for x in purchases
        )
        average_price = (
            weighted_value / weighted_qty if weighted_qty
            else float(product.get("last_purchase_price") or 0)
        )
        last_log = purchases[0] if purchases else {}
        stock = float(product.get("stock") or 0)
        reserved = float(product.get("reserved_stock") or 0)
        available = max(0, stock - reserved)
        reorder = float(product.get("reorder_level") or 0)
        if available <= 0:
            stock_status = "Out of Stock"
        elif reorder > 0 and available <= reorder:
            stock_status = "Low Stock"
        else:
            stock_status = "In Stock"
        inventory.append({
            **product,
            "size": ", ".join(variants[code]["size"]) or "â€”",
            "color": ", ".join(variants[code]["color"]) or "â€”",
            "total_purchased_qty": total_purchased,
            "available_stock": available,
            "last_purchase_date": last_log.get("purchase_date")
                                  or product.get("linked_purchase_date") or "",
            "last_invoice_number": last_log.get("invoice_no") or "",
            "last_purchase_price": float(
                last_log.get("purchase_price")
                or product.get("last_purchase_price") or 0
            ),
            "average_purchase_price": average_price,
            "current_stock_value": available * average_price,
            "damaged_stock": float(product.get("damaged_stock") or 0),
            "returned_stock": float(product.get("returned_stock") or 0),
            "stock_status": stock_status,
        })
    return inventory


def get_supplier_purchases(db, supplier_code):
    supplier = _row(db, "SELECT * FROM suppliers WHERE code=?", (supplier_code,))
    inventory = get_supplier_inventory(db, supplier_code)
    codes = [row["product_code"] for row in inventory]
    grouped = {}

    for invoice in _rows(db, """
        SELECT * FROM supplier_invoices
        WHERE supplier_code=? ORDER BY purchase_date DESC, id DESC
    """, (supplier_code,)):
        item_summary = _row(db, """
            SELECT COUNT(DISTINCT product_code) AS products,
                   COALESCE(SUM(quantity),0) AS quantity,
                   COALESCE(SUM(total_value),0) AS purchase_value
            FROM supplier_invoice_items
            WHERE supplier_code=? AND invoice_number=?
        """, (supplier_code, invoice["invoice_number"]))
        grouped[invoice["invoice_number"]] = {
            "invoice_number": invoice["invoice_number"],
            "purchase_date": invoice.get("purchase_date") or "",
            "discount_amount": float(invoice.get("discount_amount") or 0),
            "tax_amount": float(invoice.get("tax_amount") or 0),
            "net_amount": float(invoice.get("net_amount") or 0),
            "paid_amount": float(invoice.get("paid_amount") or 0),
            "balance_amount": float(invoice.get("balance_amount") or 0),
            "payment_status": invoice.get("payment_status") or "Pending",
            "products": {
                f"saved-{index}"
                for index in range(int(item_summary.get("products") or 0))
            },
            "total_quantity": float(item_summary.get("quantity") or 0),
            "purchase_value": float(item_summary.get("purchase_value") or 0),
        }

    for log in _purchase_log_rows(db, codes):
        number = log.get("invoice_no") or "Unnumbered"
        invoice = grouped.setdefault(number, {
            "invoice_number": number,
            "purchase_date": log.get("purchase_date") or "",
            "discount_amount": 0.0, "tax_amount": 0.0,
            "net_amount": 0.0, "paid_amount": 0.0,
            "balance_amount": 0.0, "payment_status": "Pending",
            "products": set(), "total_quantity": 0.0, "purchase_value": 0.0,
        })
        qty = float(log.get("stock_qty") or 0)
        price = float(log.get("purchase_price") or 0)
        base = qty * price
        tax = base * _gst_percent(log.get("purchase_gst")) / 100
        invoice["products"].add(log.get("product_code"))
        invoice["total_quantity"] += qty
        invoice["purchase_value"] += base
        if not invoice["tax_amount"]:
            invoice["tax_amount"] += tax
        if not invoice["net_amount"]:
            invoice["net_amount"] += base + tax

    for invoice in grouped.values():
        if not invoice["balance_amount"] and invoice["net_amount"]:
            invoice["balance_amount"] = max(
                0, invoice["net_amount"] - invoice["paid_amount"]
            )
        if invoice["balance_amount"] <= 0 and invoice["net_amount"] > 0:
            invoice["payment_status"] = "Paid"
        elif invoice["paid_amount"] > 0:
            invoice["payment_status"] = "Partially Paid"
        invoice["total_products"] = len(invoice["products"])
    return sorted(
        grouped.values(),
        key=lambda row: (row.get("purchase_date") or "", row["invoice_number"]),
        reverse=True,
    )


def get_invoice_items(db, supplier_code, invoice_number):
    saved = _rows(db, """
        SELECT product_code, product_name, category, size, color, quantity,
               purchase_price, selling_price, total_value
        FROM supplier_invoice_items
        WHERE supplier_code=? AND invoice_number=? ORDER BY product_name
    """, (supplier_code, invoice_number))
    if saved:
        return saved

    supplier = _row(db, "SELECT * FROM suppliers WHERE code=?", (supplier_code,))
    products = _supplier_product_rows(db, supplier)
    codes = [row["product_code"] for row in products]
    if not codes:
        return []
    variants = _variant_labels(db, codes)
    marks = ",".join("?" for _ in codes)
    rows = _rows(db, f"""
        SELECT pl.product_code, p.name AS product_name, p.category,
               pl.quantity, pl.purchase_price,
               COALESCE(NULLIF(pl.selling_price,0),p.selling_price,0) AS selling_price,
               COALESCE(NULLIF(pl.net_amount,0),
                        pl.quantity * pl.purchase_price) AS total_value
        FROM purchase_invoice_logs pl
        JOIN products p ON p.item_code=pl.product_code
        WHERE pl.invoice_number=? AND pl.product_code IN ({marks})
        ORDER BY p.name
    """, (invoice_number, *codes))
    for row in rows:
        code = row["product_code"]
        row["size"] = ", ".join(variants[code]["size"]) or "â€”"
        row["color"] = ", ".join(variants[code]["color"]) or "â€”"
    return rows


def get_supplier_summary(db, supplier_code):
    inventory = get_supplier_inventory(db, supplier_code)
    purchases = get_supplier_purchases(db, supplier_code)
    total_value = sum(float(row.get("net_amount") or 0) for row in purchases)
    total_qty = sum(float(row.get("total_quantity") or 0) for row in purchases)
    pending = sum(float(row.get("balance_amount") or 0) for row in purchases)
    if not pending:
        supplier = _row(db, "SELECT current_balance FROM suppliers WHERE code=?",
                        (supplier_code,))
        pending = float(supplier.get("current_balance") or 0)
    return {
        "total_purchase_orders": len(purchases),
        "total_purchase_value": total_value,
        "total_quantity_purchased": total_qty,
        "total_products_purchased": len(inventory),
        "average_purchase_value": total_value / len(purchases) if purchases else 0,
        "last_purchase_date": purchases[0].get("purchase_date") if purchases else "",
        "pending_payment": pending,
        "current_stock_qty": sum(x["available_stock"] for x in inventory),
        "current_stock_value": sum(x["current_stock_value"] for x in inventory),
    }


def get_suppliers(db, search=""):
    like = f"%{search.strip()}%"
    suppliers = _rows(db, """
        SELECT DISTINCT s.*
        FROM suppliers s
        LEFT JOIN product_suppliers ps ON ps.supplier_code=s.code
        LEFT JOIN products p ON p.item_code=ps.product_code
                             OR LOWER(COALESCE(p.supplier_name,''))=LOWER(s.name)
        WHERE ?='' OR s.name LIKE ? OR s.code LIKE ?
          OR COALESCE(s.contact_person,'') LIKE ? OR COALESCE(s.phone,'') LIKE ?
          OR COALESCE(s.gstin,'') LIKE ? OR COALESCE(p.name,'') LIKE ?
        ORDER BY s.name
    """, (search.strip(), like, like, like, like, like, like))
    result = []
    for supplier in suppliers:
        summary = get_supplier_summary(db, supplier["code"])
        inventory = get_supplier_inventory(db, supplier["code"])
        estimated_profit = sum(
            max(
                0,
                float(item.get("selling_price") or 0)
                - float(item.get("average_purchase_price") or 0),
            ) * float(item.get("sold_qty") or 0)
            for item in inventory
        )
        result.append({**supplier, **summary, "estimated_profit": estimated_profit})
    return result


def save_supplier(db, data, user="system"):
    init_supplier_tables(db)
    code = data.get("code", "").strip()
    if not code:
        next_no = _row(db, """
            SELECT COALESCE(MAX(CAST(SUBSTR(code,4) AS INTEGER)),0)+1 AS n
            FROM suppliers WHERE code LIKE 'SUP%'
        """).get("n", 1)
        code = f"SUP{int(next_no):05d}"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db) as conn:
        old = conn.execute(
            "SELECT * FROM suppliers WHERE code=?", (code,)
        ).fetchone()
        conn.execute("""
            INSERT INTO suppliers
            (code,name,gstin,pan_number,contact_person,phone,mobile_number,
             whatsapp_number,email,address,address_line1,address_line2,city,state,
             pincode,country,payment_terms,payment_terms_days,credit_limit,
             current_balance,account_holder_name,bank_name,branch_name,
             account_number,ifsc,upi_id,default_lead_time,
             preferred_payment_method,supplier_category,status,notes,
             created_at,created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET
              name=excluded.name, gstin=excluded.gstin, pan_number=excluded.pan_number,
              contact_person=excluded.contact_person, phone=excluded.phone,
              mobile_number=excluded.mobile_number,
              whatsapp_number=excluded.whatsapp_number,
              email=excluded.email, address=excluded.address,
              address_line1=excluded.address_line1,
              address_line2=excluded.address_line2, city=excluded.city,
              state=excluded.state, pincode=excluded.pincode,
              country=excluded.country, payment_terms=excluded.payment_terms,
              payment_terms_days=excluded.payment_terms_days,
              credit_limit=excluded.credit_limit,
              current_balance=excluded.current_balance,
              account_holder_name=excluded.account_holder_name,
              bank_name=excluded.bank_name, branch_name=excluded.branch_name,
              account_number=excluded.account_number, ifsc=excluded.ifsc,
              upi_id=excluded.upi_id, default_lead_time=excluded.default_lead_time,
              preferred_payment_method=excluded.preferred_payment_method,
              supplier_category=excluded.supplier_category,
              status=excluded.status, notes=excluded.notes
        """, (
            code, data.get("name", ""), data.get("gstin", ""),
            data.get("pan_number", ""),
            data.get("contact_person", ""), data.get("phone", ""),
            data.get("mobile_number", ""), data.get("whatsapp_number", ""),
            data.get("email", ""), data.get("address", ""),
            data.get("address_line1", ""), data.get("address_line2", ""),
            data.get("city", ""), data.get("state", ""), data.get("pincode", ""),
            data.get("country", "India"), data.get("payment_terms", ""),
            int(data.get("payment_terms_days") or 0),
            float(data.get("credit_limit") or 0),
            float(data.get("current_balance") or 0),
            data.get("account_holder_name", ""), data.get("bank_name", ""),
            data.get("branch_name", ""), data.get("account_number", ""),
            data.get("ifsc", ""), data.get("upi_id", ""),
            int(data.get("default_lead_time") or 0),
            data.get("preferred_payment_method", ""),
            data.get("supplier_category", ""),
            data.get("status", "Active"), data.get("notes", ""), now, user,
        ))
        conn.execute("""
            INSERT INTO supplier_activity_log
            (supplier_code,activity_at,action,reference,old_value,new_value,user,notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            code, now, "Supplier Edited" if old else "Supplier Created", code,
            "Existing supplier" if old else "",
            data.get("name", ""), user, data.get("notes", ""),
        ))
    return code


def get_supplier_ledger(db, supplier_code):
    entries = _rows(db, """
        SELECT entry_date, entry_type, reference_number, invoice_number,
               debit, credit, balance, payment_mode, notes
        FROM supplier_ledger WHERE supplier_code=?
        ORDER BY entry_date DESC, id DESC
    """, (supplier_code,))
    if entries:
        return entries
    balance = 0.0
    generated = []
    for invoice in reversed(get_supplier_purchases(db, supplier_code)):
        debit = float(invoice.get("net_amount") or 0)
        credit = float(invoice.get("paid_amount") or 0)
        balance += debit - credit
        generated.append({
            "entry_date": invoice.get("purchase_date"), "entry_type": "Purchase Invoice",
            "reference_number": invoice.get("invoice_number"),
            "invoice_number": invoice.get("invoice_number"), "debit": debit,
            "credit": credit, "balance": balance, "payment_mode": "",
            "notes": invoice.get("payment_status"),
        })
    return list(reversed(generated))


def get_supplier_activity(db, supplier_code):
    return _rows(db, """
        SELECT activity_at, action, reference, old_value, new_value, user, notes
        FROM supplier_activity_log WHERE supplier_code=?
        ORDER BY activity_at DESC, id DESC
    """, (supplier_code,))


def get_supplier_list_kpis(db):
    suppliers = get_suppliers(db, "")
    today = datetime.date.today()
    month_prefix = today.strftime("%Y-%m")
    return {
        "total": len(suppliers),
        "active": sum(1 for row in suppliers if row.get("status") == "Active"),
        "purchase_value": sum(float(row.get("total_purchase_value") or 0)
                              for row in suppliers),
        "pending": sum(float(row.get("pending_payment") or 0)
                       for row in suppliers),
        "stock_value": sum(float(row.get("current_stock_value") or 0)
                           for row in suppliers),
        "month_purchase": sum(
            float(invoice.get("net_amount") or 0)
            for row in suppliers
            for invoice in get_supplier_purchases(db, row.get("code", ""))
            if str(invoice.get("purchase_date") or "").startswith(month_prefix)
        ),
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UI helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _button(text, primary=False):
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(BTN_PRIMARY if primary else BTN_SECONDARY)
    return button


def _card():
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:{C['bg_white']};border:1px solid {C['border']};"
        "border-radius:12px;}}"
    )
    return frame


def _table(headers, stretch=True):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setStyleSheet(TABLE_SS)
    if stretch:
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    else:
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setStretchLastSection(True)
    return table


def _fill_table(table, rows, columns, currency_columns=(), status_column=None):
    table.setRowCount(0)
    for row_data in rows:
        row = table.rowCount()
        table.insertRow(row)
        for column, key in enumerate(columns):
            value = row_data.get(key, "")
            if column in currency_columns:
                text = _money(value)
            elif isinstance(value, float):
                text = _number(value)
            else:
                text = str(value if value not in (None, "") else "â€”")
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status_column == column:
                colors = {
                    "Paid": C["success"], "In Stock": C["success"],
                    "Pending": C["warning"], "Partially Paid": C["warning"],
                    "Low Stock": C["warning"], "Out of Stock": C.get("danger", "#E53935"),
                }
                item.setForeground(QColor(colors.get(text, C["text"])))
                font = item.font(); font.setBold(True); item.setFont(font)
            table.setItem(row, column, item)
        table.setRowHeight(row, 42)


def _stat_card(title, value, color=None):
    frame = _card()
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    title_label = QLabel(title)
    title_label.setStyleSheet(
        f"font-size:10px;font-weight:700;color:{C['text3']};"
        "background:transparent;border:none;"
    )
    value_label = QLabel(str(value))
    value_label.setWordWrap(True)
    value_label.setStyleSheet(
        f"font-size:17px;font-weight:700;color:{color or C['text']};"
        "background:transparent;border:none;"
    )
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    return frame


class InvoiceDetailDialog(QDialog):
    def __init__(self, db, supplier_code, invoice_number, parent=None):
        super().__init__(parent)
        apply_app_icon(self)
        self.setWindowTitle(f"Invoice {invoice_number}")
        self.resize(1120, 560)
        root = QVBoxLayout(self)
        title = QLabel(f"Invoice Details  Â·  {invoice_number}")
        title.setStyleSheet(
            f"font-size:20px;font-weight:700;color:{C['text']};padding:8px;"
        )
        root.addWidget(title)
        table = _table([
            "Product Code", "Product Name", "Category", "Size", "Color",
            "Quantity Purchased", "Purchase Price", "Selling Price", "Total Value",
        ], stretch=False)
        items = get_invoice_items(db, supplier_code, invoice_number)
        _fill_table(
            table, items,
            ["product_code", "product_name", "category", "size", "color",
             "quantity", "purchase_price", "selling_price", "total_value"],
            currency_columns=(6, 7, 8),
        )
        root.addWidget(table)
        close = _button("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(close)
        root.addLayout(row)


class ProductDetailDialog(QDialog):
    def __init__(self, supplier_name, product, parent=None):
        super().__init__(parent)
        apply_app_icon(self)
        self.setWindowTitle(product.get("product_name") or "Product Detail")
        self.resize(1050, 440)
        root = QVBoxLayout(self)
        title = QLabel(f"Inventory Detail  Â·  {product.get('product_name','')}")
        title.setStyleSheet(
            f"font-size:20px;font-weight:700;color:{C['text']};padding:8px;"
        )
        root.addWidget(title)
        table = _table([
            "Product Code", "Product Name", "Category", "Brand", "Size", "Color",
            "Supplier Name", "Total Purchased Qty", "Total Sold Qty",
            "Available Stock", "Current Purchase Price", "Current Selling Price",
            "Total Stock Value", "Last Purchase Date", "Last Invoice Number",
        ], stretch=False)
        detail = dict(product)
        detail["supplier_name"] = supplier_name
        _fill_table(
            table, [detail],
            ["product_code", "product_name", "category", "brand", "size", "color",
             "supplier_name", "total_purchased_qty", "sold_qty", "available_stock",
             "last_purchase_price", "selling_price", "current_stock_value",
             "last_purchase_date", "last_invoice_number"],
            currency_columns=(10, 11, 12),
        )
        root.addWidget(table)
        close = _button("Close"); close.clicked.connect(self.accept)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(close)
        root.addLayout(row)


class SupplierFormWidget(QWidget):
    saved = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, db_name, current_user="Admin", parent=None):
        super().__init__(parent)
        ensure_global_input_guard()
        self.db_name = db_name
        self.current_user = current_user
        self.edit_code = None
        self.setStyleSheet(f"background:{C['bg_light']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)

        top = QHBoxLayout()
        self.title = QLabel("Add Supplier")
        self.title.setStyleSheet(
            f"font-size:22px;font-weight:700;color:{C['text']};"
        )
        cancel = _button("Cancel")
        save = _button("Save Supplier", True)
        cancel.clicked.connect(self.cancelled)
        save.clicked.connect(self._save)
        top.addWidget(self.title); top.addStretch()
        top.addWidget(cancel); top.addWidget(save)
        root.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(4, 10, 4, 10)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1); grid.setColumnStretch(3, 1)

        def line(placeholder=""):
            widget = QLineEdit()
            widget.setPlaceholderText(placeholder)
            widget.setFixedHeight(38)
            widget.setStyleSheet(FIELD_SS)
            return widget

        self.code = line("Auto-generated if blank")
        self.name = line("Supplier business name")
        self.contact = line("Contact person")
        self.phone = line("Phone number")
        self.whatsapp = line("WhatsApp number")
        self.email = line("Email")
        self.gstin = line("GSTIN")
        self.pan = line("PAN number")
        self.category = line("Textile, garments, accessoriesâ€¦")
        self.address = line("Address line 1")
        self.address2 = line("Address line 2")
        self.city = line("City")
        self.state = line("State")
        self.pincode = line("PIN code")
        self.country = line("Country"); self.country.setText("India")
        self.terms = QSpinBox(); self.terms.setRange(0, 365)
        self.terms.setSuffix(" days"); self.terms.setFixedHeight(38)
        self.terms.setStyleSheet(_NO_ARROW)
        self.lead_time = QSpinBox(); self.lead_time.setRange(0, 365)
        self.lead_time.setSuffix(" days"); self.lead_time.setFixedHeight(38)
        self.lead_time.setStyleSheet(_NO_ARROW)
        self.credit = QDoubleSpinBox(); self.credit.setRange(0, 999999999)
        self.credit.setPrefix("â‚¹ "); self.credit.setFixedHeight(38)
        self.credit.setStyleSheet(_NO_ARROW)
        self.balance = QDoubleSpinBox(); self.balance.setRange(0, 999999999)
        self.balance.setPrefix("â‚¹ "); self.balance.setFixedHeight(38)
        self.balance.setStyleSheet(_NO_ARROW)
        self.status = QComboBox(); self.status.addItems(
            ["Active", "Inactive", "Blacklisted"]
        )
        self.status.setFixedHeight(38); _apply_combo_delegate(self.status)
        self.payment_method = QComboBox()
        self.payment_method.addItems([
            "", "Bank Transfer", "UPI", "Cash", "Cheque", "Card", "Credit"])
        self.payment_method.setFixedHeight(38)
        _apply_combo_delegate(self.payment_method)
        self.account_holder = line("Account holder name")
        self.bank_name = line("Bank name")
        self.branch = line("Branch name")
        self.account_number = line("Account number")
        self.ifsc = line("IFSC code")
        self.upi = line("UPI ID")
        self.notes = QTextEdit(); self.notes.setFixedHeight(80)
        self.notes.setPlaceholderText("Supplier notes")
        self.notes.setStyleSheet(FIELD_SS)

        sections = [
            ("Basic Information", [
                ("Supplier Code", self.code), ("Supplier Name *", self.name),
                ("Contact Person", self.contact), ("Phone", self.phone),
                ("WhatsApp Number", self.whatsapp), ("Email", self.email),
                ("GSTIN", self.gstin), ("PAN Number", self.pan),
                ("Supplier Category", self.category), ("Status", self.status),
            ]),
            ("Address Information", [
                ("Address Line 1", self.address), ("Address Line 2", self.address2),
                ("City", self.city), ("State", self.state),
                ("PIN Code", self.pincode), ("Country", self.country),
            ]),
            ("Banking Information", [
                ("Account Holder", self.account_holder), ("Bank Name", self.bank_name),
                ("Branch", self.branch), ("Account Number", self.account_number),
                ("IFSC Code", self.ifsc), ("UPI ID", self.upi),
            ]),
            ("Purchase Configuration", [
                ("Payment Terms", self.terms), ("Credit Limit", self.credit),
                ("Current Balance", self.balance),
                ("Default Lead Time", self.lead_time),
                ("Preferred Payment", self.payment_method),
            ]),
        ]
        grid_row = 0
        for section_name, fields in sections:
            header = QLabel(section_name)
            header.setStyleSheet(
                f"font-size:14px;font-weight:800;color:{C['text']};"
                f"padding:10px 2px 5px;border-bottom:1px solid {C['border']};")
            grid.addWidget(header, grid_row, 0, 1, 4)
            grid_row += 1
            for index, (label, widget) in enumerate(fields):
                row, side = grid_row + index // 2, index % 2
                label_widget = QLabel(label); label_widget.setStyleSheet(LABEL_SS)
                grid.addWidget(label_widget, row, side * 2)
                grid.addWidget(widget, row, side * 2 + 1)
            grid_row += (len(fields) + 1) // 2
        notes_row = grid_row
        notes_label = QLabel("Notes"); notes_label.setStyleSheet(LABEL_SS)
        grid.addWidget(notes_label, notes_row, 0)
        grid.addWidget(self.notes, notes_row, 1, 1, 3)
        scroll.setWidget(body)
        root.addWidget(scroll)

    def load_for_add(self):
        self.edit_code = None
        self.title.setText("Add Supplier")
        for field in (
            self.code, self.name, self.contact, self.phone, self.email,
            self.whatsapp, self.gstin, self.pan, self.category,
            self.address, self.address2, self.city, self.state, self.pincode,
            self.account_holder, self.bank_name, self.branch,
            self.account_number, self.ifsc, self.upi,
        ):
            field.clear()
        self.country.setText("India")
        self.terms.setValue(30)
        self.lead_time.setValue(0)
        self.credit.setValue(0); self.balance.setValue(0)
        self.status.setCurrentIndex(0); self.payment_method.setCurrentIndex(0)
        self.notes.clear()
        self.code.setReadOnly(False)

    def load_for_edit(self, code):
        self.edit_code = code
        supplier = _row(self.db_name, "SELECT * FROM suppliers WHERE code=?", (code,))
        self.title.setText(f"Edit Supplier  Â·  {code}")
        self.code.setText(code); self.code.setReadOnly(True)
        self.name.setText(supplier.get("name", ""))
        self.contact.setText(supplier.get("contact_person", ""))
        self.phone.setText(supplier.get("phone", ""))
        self.whatsapp.setText(supplier.get("whatsapp_number", ""))
        self.email.setText(supplier.get("email", ""))
        self.gstin.setText(supplier.get("gstin", ""))
        self.pan.setText(supplier.get("pan_number", ""))
        self.category.setText(supplier.get("supplier_category", ""))
        self.address.setText(
            supplier.get("address_line1") or supplier.get("address", ""))
        self.address2.setText(supplier.get("address_line2", ""))
        self.city.setText(supplier.get("city", ""))
        self.state.setText(supplier.get("state", ""))
        self.pincode.setText(supplier.get("pincode", ""))
        self.country.setText(supplier.get("country") or "India")
        self.terms.setValue(int(supplier.get("payment_terms_days") or 0))
        self.lead_time.setValue(int(supplier.get("default_lead_time") or 0))
        self.credit.setValue(float(supplier.get("credit_limit") or 0))
        self.balance.setValue(float(supplier.get("current_balance") or 0))
        self.account_holder.setText(supplier.get("account_holder_name", ""))
        self.bank_name.setText(supplier.get("bank_name", ""))
        self.branch.setText(supplier.get("branch_name", ""))
        self.account_number.setText(supplier.get("account_number", ""))
        self.ifsc.setText(supplier.get("ifsc", ""))
        self.upi.setText(supplier.get("upi_id", ""))
        payment_index = self.payment_method.findText(
            supplier.get("preferred_payment_method") or "")
        self.payment_method.setCurrentIndex(max(0, payment_index))
        index = self.status.findText(supplier.get("status") or "Active")
        self.status.setCurrentIndex(max(0, index))
        self.notes.setPlainText(supplier.get("notes", ""))

    def _save(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Validation", "Supplier name is required.")
            self.name.setFocus()
            return
        code = save_supplier(self.db_name, {
            "code": self.edit_code or self.code.text().strip(),
            "name": self.name.text().strip(),
            "contact_person": self.contact.text().strip(),
            "phone": self.phone.text().strip(),
            "mobile_number": self.phone.text().strip(),
            "whatsapp_number": self.whatsapp.text().strip(),
            "email": self.email.text().strip(),
            "gstin": self.gstin.text().strip(),
            "pan_number": self.pan.text().strip(),
            "supplier_category": self.category.text().strip(),
            "address": self.address.text().strip(),
            "address_line1": self.address.text().strip(),
            "address_line2": self.address2.text().strip(),
            "city": self.city.text().strip(),
            "state": self.state.text().strip(),
            "pincode": self.pincode.text().strip(),
            "country": self.country.text().strip() or "India",
            "payment_terms": f"Net {self.terms.value()}",
            "payment_terms_days": self.terms.value(),
            "credit_limit": self.credit.value(),
            "current_balance": self.balance.value(),
            "account_holder_name": self.account_holder.text().strip(),
            "bank_name": self.bank_name.text().strip(),
            "branch_name": self.branch.text().strip(),
            "account_number": self.account_number.text().strip(),
            "ifsc": self.ifsc.text().strip().upper(),
            "upi_id": self.upi.text().strip(),
            "default_lead_time": self.lead_time.value(),
            "preferred_payment_method": self.payment_method.currentText(),
            "status": self.status.currentText(),
            "notes": self.notes.toPlainText().strip(),
        }, self.current_user)
        self.saved.emit(code)


class SupplierDetailWidget(QWidget):
    back_requested = pyqtSignal()
    edit_requested = pyqtSignal(str)

    def __init__(self, db_name, parent=None):
        super().__init__(parent)
        self.db_name = db_name
        self.supplier_code = ""
        self.inventory_rows = []
        self.purchase_rows = []
        self.setStyleSheet("background:transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        top = QHBoxLayout()
        back = _button("â† Suppliers")
        back.clicked.connect(self.back_requested)
        self.title = QLabel("Supplier Detail")
        self.title.setStyleSheet(
            f"font-size:23px;font-weight:700;color:{C['text']};"
        )
        edit = _button("Edit Supplier")
        edit.clicked.connect(lambda: self.edit_requested.emit(self.supplier_code))
        top.addWidget(back); top.addSpacing(10); top.addWidget(self.title)
        top.addStretch(); top.addWidget(edit)
        root.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent;")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 8, 0, 0)
        self.body_layout.setSpacing(14)

        self.info_card = _card()
        self.info_grid = QGridLayout(self.info_card)
        self.info_grid.setContentsMargins(18, 16, 18, 16)
        self.info_grid.setHorizontalSpacing(24)
        self.info_grid.setVerticalSpacing(10)
        self.body_layout.addWidget(self.info_card)

        self.stats_wrap = QWidget()
        self.stats_grid = QGridLayout(self.stats_wrap)
        self.stats_grid.setContentsMargins(0, 0, 0, 0)
        self.stats_grid.setSpacing(10)
        self.body_layout.addWidget(self.stats_wrap)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane{{border:1px solid {C['border']};border-radius:10px;
                background:white;top:-1px;}}
            QTabBar::tab{{padding:10px 18px;background:#F5F5F7;color:{C['text2']};
                border:1px solid {C['border']};}}
            QTabBar::tab:selected{{background:{C['accent']};color:white;font-weight:700;}}
        """)
        self.products_table = _table([
            "Product Code", "Product Name", "Category", "Brand", "Size", "Color",
            "Supplier Product Code", "MOQ", "Last Purchase Price",
            "Average Purchase Price", "Total Purchased Qty", "Available Stock",
            "Last Purchase Date", "Status", "Actions",
        ], stretch=False)
        self.products_table.cellClicked.connect(self._open_product)
        products_page = QWidget(); products_layout = QVBoxLayout(products_page)
        products_layout.addWidget(self.products_table)
        self.tabs.addTab(products_page, "PRODUCTS SUPPLIED")

        self.purchase_table = _table([
            "Invoice Number", "Invoice Date", "Purchase Date", "Total Products",
            "Total Qty", "Purchase Value", "GST Amount", "Discount", "Net Amount",
            "Paid Amount", "Balance Amount", "Payment Status", "Actions",
        ], stretch=False)
        self.purchase_table.cellClicked.connect(self._open_invoice)
        purchase_page = QWidget(); purchase_layout = QVBoxLayout(purchase_page)
        invoice_actions = QHBoxLayout()
        invoice_hint = QLabel("Click an invoice number to view product details.")
        invoice_hint.setStyleSheet(f"font-size:11px;color:{C['text3']};border:none;")
        invoice_actions.addWidget(invoice_hint); invoice_actions.addStretch()
        self.add_payment_btn = _button("+ Add Payment")
        self.add_payment_btn.clicked.connect(self._add_payment)
        invoice_actions.addWidget(self.add_payment_btn)
        purchase_layout.addLayout(invoice_actions)
        purchase_layout.addWidget(self.purchase_table)
        self.tabs.addTab(purchase_page, "PURCHASE INVOICES")

        self.inventory_table = _table([
            "Product Code", "Product Name", "Category", "Brand", "Size", "Color",
            "Total Purchased Qty", "Total Sold Qty", "Available Stock",
            "Damaged Stock", "Returned Stock", "Last Invoice Number",
            "Last Purchase Date", "Last Purchase Price", "Stock Value", "Stock Status",
        ], stretch=False)
        self.inventory_table.cellClicked.connect(self._open_product)
        inventory_page = QWidget(); inventory_layout = QVBoxLayout(inventory_page)
        inventory_layout.addWidget(self.inventory_table)
        self.tabs.addTab(inventory_page, "SUPPLIER INVENTORY")

        self.ledger_table = _table([
            "Date", "Type", "Reference Number", "Invoice Number", "Debit",
            "Credit", "Balance", "Payment Mode", "Notes",
        ], stretch=False)
        ledger_page = QWidget(); ledger_layout = QVBoxLayout(ledger_page)
        ledger_layout.addWidget(self.ledger_table)
        self.tabs.addTab(ledger_page, "PAYMENT / LEDGER")

        self.activity_table = _table([
            "Date & Time", "Action", "Reference", "Old Value", "New Value",
            "User", "Notes",
        ], stretch=False)
        activity_page = QWidget(); activity_layout = QVBoxLayout(activity_page)
        activity_layout.addWidget(self.activity_table)
        self.tabs.addTab(activity_page, "ACTIVITY LOG")
        self.body_layout.addWidget(self.tabs)
        scroll.setWidget(body)
        root.addWidget(scroll)

    def load_supplier(self, supplier_code):
        self.supplier_code = supplier_code
        supplier = _row(
            self.db_name, "SELECT * FROM suppliers WHERE code=?", (supplier_code,)
        )
        self.title.setText(
            f"{supplier.get('name','Supplier')}  Â·  {supplier_code}"
        )
        while self.info_grid.count():
            item = self.info_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        info = [
            ("Supplier Code", supplier_code), ("Supplier Name", supplier.get("name")),
            ("Contact Person", supplier.get("contact_person")),
            ("Phone", supplier.get("phone")), ("Email", supplier.get("email")),
            ("GSTIN", supplier.get("gstin")), ("Address", supplier.get("address")),
            ("City", supplier.get("city")), ("State", supplier.get("state")),
            ("Payment Terms", f"{supplier.get('payment_terms_days') or 0} days"),
            ("Credit Limit", _money(supplier.get("credit_limit"))),
            ("Current Balance", _money(supplier.get("current_balance"))),
            ("Status", supplier.get("status") or "Active"),
        ]
        for index, (label, value) in enumerate(info):
            row, column = divmod(index, 3)
            wrap = QWidget(); layout = QVBoxLayout(wrap)
            layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(2)
            name = QLabel(label); name.setStyleSheet(
                f"font-size:10px;font-weight:700;color:{C['text3']};border:none;"
            )
            data = QLabel(str(value or "â€”")); data.setWordWrap(True)
            data.setStyleSheet(
                f"font-size:12px;font-weight:600;color:{C['text']};border:none;"
            )
            layout.addWidget(name); layout.addWidget(data)
            self.info_grid.addWidget(wrap, row, column)

        summary = get_supplier_summary(self.db_name, supplier_code)
        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        stats = [
            ("Total Purchase Orders", summary["total_purchase_orders"]),
            ("Total Purchase Value", _money(summary["total_purchase_value"])),
            ("Total Quantity Purchased", _number(summary["total_quantity_purchased"])),
            ("Total Products Purchased", summary["total_products_purchased"]),
            ("Average Purchase Value", _money(summary["average_purchase_value"])),
            ("Last Purchase Date", summary["last_purchase_date"] or "â€”"),
            ("Pending Payment Amount", _money(summary["pending_payment"])),
        ]
        for index, (label, value) in enumerate(stats):
            self.stats_grid.addWidget(
                _stat_card(label, value, C["accent"] if index == 6 else None),
                index // 4, index % 4,
            )

        self.purchase_rows = get_supplier_purchases(self.db_name, supplier_code)
        _fill_table(
            self.purchase_table, self.purchase_rows,
            ["invoice_number", "purchase_date", "total_products", "total_quantity",
             "purchase_value", "discount_amount", "tax_amount", "net_amount",
             "paid_amount", "balance_amount", "payment_status"],
            currency_columns=(4, 5, 6, 7, 8, 9), status_column=10,
        )
        self.inventory_rows = get_supplier_inventory(self.db_name, supplier_code)
        _fill_table(
            self.inventory_table, self.inventory_rows,
            ["product_code", "product_name", "category", "brand", "size", "color",
             "total_purchased_qty", "sold_qty", "available_stock", "reserved_stock",
             "last_purchase_date", "last_purchase_price", "average_purchase_price",
             "selling_price", "current_stock_value", "reorder_level", "stock_status"],
            currency_columns=(11, 12, 13, 14), status_column=16,
        )
        self._load_control_center()

    def _load_control_center(self):
        """Populate the five textile supplier-control tabs."""
        supplier_code = self.supplier_code
        supplier = _row(
            self.db_name, "SELECT * FROM suppliers WHERE code=?", (supplier_code,))
        while self.info_grid.count():
            item = self.info_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        address = " ".join(filter(None, [
            supplier.get("address_line1") or supplier.get("address"),
            supplier.get("address_line2"),
        ]))
        account = "".join(
            ch for ch in str(supplier.get("account_number") or "") if ch.isalnum())
        info = [
            ("Supplier Code", supplier_code), ("Supplier Name", supplier.get("name")),
            ("Contact Person", supplier.get("contact_person")),
            ("Phone", supplier.get("phone")), ("Email", supplier.get("email")),
            ("GSTIN", supplier.get("gstin")), ("PAN", supplier.get("pan_number")),
            ("Address", address), ("City", supplier.get("city")),
            ("State", supplier.get("state")),
            ("Payment Terms", f"{supplier.get('payment_terms_days') or 0} days"),
            ("Credit Limit", _money(supplier.get("credit_limit"))),
            ("Outstanding Balance", _money(supplier.get("current_balance"))),
            ("Status", supplier.get("status") or "Active"),
            ("Account Holder", supplier.get("account_holder_name")),
            ("Bank", supplier.get("bank_name")),
            ("Branch", supplier.get("branch_name")),
            ("Account Number", f"XXXX XXXX {account[-4:]}" if account else "â€”"),
            ("IFSC Code", supplier.get("ifsc")),
            ("UPI ID", supplier.get("upi_id")),
            ("Preferred Payment", supplier.get("preferred_payment_method")),
        ]
        for index, (label, value) in enumerate(info):
            row, column = divmod(index, 3)
            wrap = QWidget(); layout = QVBoxLayout(wrap)
            layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(2)
            name = QLabel(label)
            name.setStyleSheet(
                f"font-size:10px;font-weight:700;color:{C['text3']};border:none;")
            data = QLabel(str(value or "â€”")); data.setWordWrap(True)
            data.setStyleSheet(
                f"font-size:12px;font-weight:600;color:{C['text']};border:none;")
            layout.addWidget(name); layout.addWidget(data)
            self.info_grid.addWidget(wrap, row, column)

        summary = get_supplier_summary(self.db_name, supplier_code)
        self.inventory_rows = get_supplier_inventory(self.db_name, supplier_code)
        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        average_price = (
            sum(float(row.get("average_purchase_price") or 0)
                for row in self.inventory_rows) / len(self.inventory_rows)
            if self.inventory_rows else 0)
        stats = [
            ("Total Products Supplied", summary["total_products_purchased"]),
            ("Total Purchase Qty", _number(summary["total_quantity_purchased"])),
            ("Total Purchase Value", _money(summary["total_purchase_value"])),
            ("Available Stock Qty", _number(summary["current_stock_qty"])),
            ("Current Stock Value", _money(summary["current_stock_value"])),
            ("Pending Payment", _money(summary["pending_payment"])),
            ("Last Purchase Date", summary["last_purchase_date"] or "â€”"),
            ("Average Purchase Price", _money(average_price)),
        ]
        for index, metric in enumerate(stats):
            self.stats_grid.addWidget(
                _stat_card(*metric, C["accent"] if index == 5 else None),
                index // 4, index % 4)

        for product in self.inventory_rows:
            product["actions"] = "View Â· Stock Â· Logs"
        _fill_table(
            self.products_table, self.inventory_rows,
            ["product_code", "product_name", "category", "brand", "size", "color",
             "supplier_product_code", "moq", "last_purchase_price",
             "average_purchase_price", "total_purchased_qty", "available_stock",
             "last_purchase_date", "status", "actions"],
            currency_columns=(8, 9), status_column=13)

        self.purchase_rows = get_supplier_purchases(self.db_name, supplier_code)
        for invoice in self.purchase_rows:
            invoice["invoice_date"] = invoice.get("invoice_date") or invoice.get(
                "purchase_date")
            invoice["actions"] = "View Â· Payment"
        _fill_table(
            self.purchase_table, self.purchase_rows,
            ["invoice_number", "invoice_date", "purchase_date", "total_products",
             "total_quantity", "purchase_value", "tax_amount", "discount_amount",
             "net_amount", "paid_amount", "balance_amount", "payment_status",
             "actions"],
            currency_columns=(5, 6, 7, 8, 9, 10), status_column=11)
        _fill_table(
            self.inventory_table, self.inventory_rows,
            ["product_code", "product_name", "category", "brand", "size", "color",
             "total_purchased_qty", "sold_qty", "available_stock", "damaged_stock",
             "returned_stock", "last_invoice_number", "last_purchase_date",
             "last_purchase_price", "current_stock_value", "stock_status"],
            currency_columns=(13, 14), status_column=15)
        _fill_table(
            self.ledger_table, get_supplier_ledger(self.db_name, supplier_code),
            ["entry_date", "entry_type", "reference_number", "invoice_number",
             "debit", "credit", "balance", "payment_mode", "notes"],
            currency_columns=(4, 5, 6))
        _fill_table(
            self.activity_table, get_supplier_activity(self.db_name, supplier_code),
            ["activity_at", "action", "reference", "old_value", "new_value",
             "user", "notes"])

    def _add_payment(self):
        if not self.purchase_rows:
            QMessageBox.information(
                self, "Add Payment", "No purchase invoice is available.")
            return
        selected = self.purchase_table.currentRow()
        invoice = self.purchase_rows[
            selected if 0 <= selected < len(self.purchase_rows) else 0]
        dialog = QDialog(self)
        apply_app_icon(dialog)
        dialog.setWindowTitle("Add Supplier Payment")
        dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog)
        form = QGridLayout()
        invoice_box = QComboBox()
        invoice_box.addItems([
            row.get("invoice_number") or "Unnumbered" for row in self.purchase_rows])
        invoice_box.setCurrentText(invoice.get("invoice_number") or "Unnumbered")
        amount = QDoubleSpinBox(); amount.setRange(0, 999999999)
        amount.setDecimals(2); amount.setPrefix("â‚¹ ")
        amount.setValue(float(invoice.get("balance_amount") or 0))
        payment_mode = QComboBox()
        payment_mode.addItems(
            ["Bank Transfer", "UPI", "Cash", "Cheque", "Card"])
        reference = QLineEdit(); reference.setPlaceholderText("Payment reference")
        notes = QLineEdit(); notes.setPlaceholderText("Optional notes")
        for row, (label, widget) in enumerate([
            ("Invoice", invoice_box), ("Amount", amount),
            ("Payment Mode", payment_mode), ("Reference", reference),
            ("Notes", notes),
        ]):
            form.addWidget(QLabel(label), row, 0)
            form.addWidget(widget, row, 1)
        layout.addLayout(form)
        actions = QHBoxLayout(); actions.addStretch()
        cancel = _button("Cancel"); save = _button("Save Payment", True)
        cancel.clicked.connect(dialog.reject); save.clicked.connect(dialog.accept)
        actions.addWidget(cancel); actions.addWidget(save); layout.addLayout(actions)
        if dialog.exec() != QDialog.DialogCode.Accepted or amount.value() <= 0:
            return
        selected_invoice = next(
            (row for row in self.purchase_rows
             if (row.get("invoice_number") or "Unnumbered")
             == invoice_box.currentText()), invoice)
        paid = min(
            amount.value(), float(selected_invoice.get("balance_amount") or 0))
        if paid <= 0:
            return
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_paid = float(selected_invoice.get("paid_amount") or 0) + paid
        new_balance = max(
            0, float(selected_invoice.get("net_amount") or 0) - new_paid)
        status = "Paid" if new_balance <= 0 else "Partially Paid"
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                UPDATE purchase_invoice_logs
                SET paid_amount=?, balance_amount=?, payment_status=?
                WHERE supplier_code=? AND invoice_number=?
            """, (new_paid, new_balance, status, self.supplier_code,
                  invoice_box.currentText()))
            previous = conn.execute(
                "SELECT COALESCE(balance,0) FROM supplier_ledger "
                "WHERE supplier_code=? ORDER BY id DESC LIMIT 1",
                (self.supplier_code,)).fetchone()
            ledger_balance = max(0, float(previous[0] if previous else 0) - paid)
            conn.execute("""
                INSERT INTO supplier_ledger
                (supplier_code,entry_date,entry_type,reference_number,
                 invoice_number,debit,credit,balance,payment_mode,notes,
                 created_by,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                self.supplier_code, now[:10], "Payment Made",
                reference.text().strip(), invoice_box.currentText(),
                0, paid, ledger_balance, payment_mode.currentText(),
                notes.text().strip(), "Admin", now))
            conn.execute("""
                INSERT INTO supplier_activity_log
                (supplier_code,activity_at,action,reference,old_value,
                 new_value,user,notes)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                self.supplier_code, now, "Payment Added",
                invoice_box.currentText(),
                _money(selected_invoice.get("balance_amount")), _money(new_balance),
                "Admin", notes.text().strip()))
            conn.execute(
                "UPDATE suppliers SET current_balance=? WHERE code=?",
                (sum(
                    max(0, float(row.get("balance_amount") or 0)
                        - (paid if row is selected_invoice else 0))
                    for row in self.purchase_rows), self.supplier_code))
        self.load_supplier(self.supplier_code)
        self.tabs.setCurrentIndex(3)

    def _open_invoice(self, row, column):
        if column == 0 and 0 <= row < len(self.purchase_rows):
            InvoiceDetailDialog(
                self.db_name, self.supplier_code,
                self.purchase_rows[row]["invoice_number"], self
            ).exec()

    def _open_product(self, row, column):
        if column in (0, 1) and 0 <= row < len(self.inventory_rows):
            supplier = _row(
                self.db_name, "SELECT name FROM suppliers WHERE code=?",
                (self.supplier_code,)
            )
            ProductDetailDialog(
                supplier.get("name", ""), self.inventory_rows[row], self
            ).exec()

    def _load_insights(self, supplier, summary):
        while self.insights_layout.count():
            item = self.insights_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        inventory = self.inventory_rows
        fast = sorted(inventory, key=lambda x: x.get("sold_qty", 0), reverse=True)
        slow = sorted(
            [x for x in inventory if x.get("sold_qty", 0) > 0],
            key=lambda x: x.get("sold_qty", 0)
        )
        dead = [x for x in inventory
                if x.get("available_stock", 0) > 0 and x.get("sold_qty", 0) <= 0]
        low = [x for x in inventory if x.get("stock_status") in
               ("Low Stock", "Out of Stock")]
        most_ordered = max(
            inventory, key=lambda x: x.get("total_purchased_qty", 0), default={}
        )
        profit_product = max(
            inventory,
            key=lambda x: (
                float(x.get("selling_price") or 0)
                - float(x.get("average_purchase_price") or 0)
            ) * float(x.get("sold_qty") or 0),
            default={}
        )
        cards = QWidget(); grid = QGridLayout(cards)
        grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(10)
        metrics = [
            ("Most Ordered Product", most_ordered.get("product_name") or "â€”"),
            ("Most Profitable Product", profit_product.get("product_name") or "â€”"),
            ("Fast Moving Products", len([x for x in fast if x.get("sold_qty", 0)>0])),
            ("Slow Moving Products", len(slow)),
            ("Dead Stock Products", len(dead)),
            ("Low Stock Alerts", len(low)),
            ("Pending Payment Alert", _money(summary["pending_payment"])),
            ("Current Supplier Stock Value", _money(summary["current_stock_value"])),
        ]
        for index, metric in enumerate(metrics):
            grid.addWidget(_stat_card(*metric), index // 4, index % 4)
        self.insights_layout.addWidget(cards)

        alert_table = _table(
            ["Insight", "Product", "Qty / Value", "Action Required"], stretch=True
        )
        alerts = []
        for row in fast[:5]:
            if row.get("sold_qty", 0) > 0:
                alerts.append({
                    "insight": "Fast Moving", "product": row["product_name"],
                    "value": _number(row["sold_qty"]), "action": "Maintain stock",
                })
        for row in slow[:5]:
            alerts.append({
                "insight": "Slow Moving", "product": row["product_name"],
                "value": _number(row["sold_qty"]), "action": "Review pricing",
            })
        for row in dead[:5]:
            alerts.append({
                "insight": "Dead Stock", "product": row["product_name"],
                "value": _number(row["available_stock"]), "action": "Promote / clear",
            })
        for row in low[:5]:
            alerts.append({
                "insight": row["stock_status"], "product": row["product_name"],
                "value": _number(row["available_stock"]), "action": "Reorder",
            })
        _fill_table(alert_table, alerts, ["insight", "product", "value", "action"])
        self.insights_layout.addWidget(alert_table)

        trend_card = _card(); trend_layout = QVBoxLayout(trend_card)
        heading = QLabel("Supplier Purchase Trend  Â·  Monthly / Yearly Summary")
        heading.setStyleSheet(SEC_HDR_SS)
        trend_layout.addWidget(heading)
        trend_table = _table(
            ["Period", "Invoices", "Quantity Purchased", "Purchase Value"], True
        )
        periods = defaultdict(lambda: {"invoices": 0, "qty": 0.0, "value": 0.0})
        years = defaultdict(lambda: {"invoices": 0, "qty": 0.0, "value": 0.0})
        for purchase in self.purchase_rows:
            date = str(purchase.get("purchase_date") or "")
            period = date[:7] if len(date) >= 7 else "Unknown"
            year = date[:4] if len(date) >= 4 else "Unknown"
            periods[period]["invoices"] += 1
            periods[period]["qty"] += float(purchase.get("total_quantity") or 0)
            periods[period]["value"] += float(purchase.get("net_amount") or 0)
            years[year]["invoices"] += 1
            years[year]["qty"] += float(purchase.get("total_quantity") or 0)
            years[year]["value"] += float(purchase.get("net_amount") or 0)
        trend_rows = [
            {"period": f"Month Â· {period}", **data}
            for period, data in sorted(periods.items(), reverse=True)
        ] + [
            {"period": f"Year Â· {year}", **data}
            for year, data in sorted(years.items(), reverse=True)
        ]
        _fill_table(
            trend_table, trend_rows, ["period", "invoices", "qty", "value"],
            currency_columns=(3,)
        )
        trend_table.setMinimumHeight(210)
        trend_layout.addWidget(trend_table)
        self.insights_layout.addWidget(trend_card)


class SupplierListWidget(QWidget):
    add_requested = pyqtSignal()
    edit_requested = pyqtSignal(str)
    view_requested = pyqtSignal(str)

    def __init__(self, db_name, company_name="", parent=None):
        super().__init__(parent)
        self.db_name = db_name
        self.rows = []
        self.setStyleSheet(f"background:{C['bg_light']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 20)
        top = QHBoxLayout()
        title = QLabel("Supplier Management")
        title.setStyleSheet(
            f"font-size:25px;font-weight:700;color:{C['text']};"
        )
        subtitle = QLabel("Textile purchases, invoices, stock and supplier performance")
        subtitle.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        title_wrap = QVBoxLayout(); title_wrap.addWidget(title); title_wrap.addWidget(subtitle)
        add = _button("+ Add Supplier", True); add.clicked.connect(self.add_requested)
        top.addLayout(title_wrap); top.addStretch(); top.addWidget(add)
        root.addLayout(top)

        search_card = _card(); search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(14, 10, 14, 10)
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search supplier name, code, contact person, phone, GSTIN or product nameâ€¦"
        )
        self.search.setFixedHeight(38); self.search.setStyleSheet(FIELD_SS)
        self.search.textChanged.connect(self.refresh)
        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["All Status", "Active", "Inactive", "Blacklisted"])
        self.status_filter.setFixedHeight(38)
        _apply_combo_delegate(self.status_filter)
        self.status_filter.currentTextChanged.connect(self.refresh)
        search_layout.addWidget(QLabel("ðŸ”Ž")); search_layout.addWidget(self.search)
        advanced = QLabel("Advanced Filter")
        advanced.setStyleSheet(
            f"font-size:12px;font-weight:800;color:{C['text']};border:none;")
        search_layout.insertWidget(0, advanced)
        search_layout.addWidget(self.status_filter)
        root.addWidget(search_card)

        self.performance_wrap = QWidget()
        self.performance_grid = QGridLayout(self.performance_wrap)
        self.performance_grid.setContentsMargins(0, 0, 0, 0)
        self.performance_grid.setSpacing(10)
        root.addWidget(self.performance_wrap)

        self.table = _table([
            "Supplier Code", "Supplier Name", "Contact Person", "Phone", "GSTIN",
            "City", "Total Products Supplied", "Total Purchase Value",
            "Available Stock Qty", "Stock Value", "Last Purchase Date",
            "Pending Balance", "Status", "Actions",
        ], stretch=False)
        self.table.cellClicked.connect(self._cell_action)
        self.table.cellDoubleClicked.connect(self._view)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._edit_selected)
        root.addWidget(self.table)
        self.count = QLabel()
        self.count.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        root.addWidget(self.count)
        self.refresh()

    def refresh(self, *_args):
        self.rows = get_suppliers(self.db_name, self.search.text())
        performance_rows = (
            self.rows if not self.search.text().strip()
            else get_suppliers(self.db_name, "")
        )
        while self.performance_grid.count():
            item = self.performance_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        top_purchased = max(
            performance_rows,
            key=lambda row: row.get("total_quantity_purchased", 0),
            default={}
        )
        highest_value = max(
            performance_rows,
            key=lambda row: row.get("total_purchase_value", 0),
            default={}
        )
        most_profitable = max(
            performance_rows,
            key=lambda row: row.get("estimated_profit", 0),
            default={}
        )
        pending_alerts = sum(
            1 for row in performance_rows
            if float(row.get("pending_payment") or 0) > 0
        )
        performance = [
            ("Top Purchased Supplier", top_purchased.get("name") or "â€”"),
            ("Highest Purchase Value Supplier", highest_value.get("name") or "â€”"),
            ("Most Profitable Supplier", most_profitable.get("name") or "â€”"),
            ("Pending Payment Alerts", pending_alerts),
        ]
        for index, metric in enumerate(performance):
            self.performance_grid.addWidget(_stat_card(*metric), 0, index)
        _fill_table(
            self.table, self.rows,
            ["code", "name", "contact_person", "phone", "city",
             "total_products_purchased", "total_purchase_value",
             "current_stock_qty", "current_stock_value",
             "last_purchase_date", "pending_payment", "status"],
            currency_columns=(6, 8, 10), status_column=11,
        )
        self.count.setText(
            f"{len(self.rows)} supplier{'s' if len(self.rows) != 1 else ''}"
        )

    def refresh(self, *_args):
        self.rows = get_suppliers(self.db_name, self.search.text())
        selected_status = self.status_filter.currentText()
        if selected_status != "All Status":
            self.rows = [
                row for row in self.rows if row.get("status") == selected_status]
        while self.performance_grid.count():
            item = self.performance_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        kpis = get_supplier_list_kpis(self.db_name)
        performance = [
            ("Total Suppliers", kpis["total"]),
            ("Active Suppliers", kpis["active"]),
            ("Total Purchase Value", _money(kpis["purchase_value"])),
            ("Pending Payment", _money(kpis["pending"])),
            ("Total Stock Value", _money(kpis["stock_value"])),
            ("This Month Purchases", _money(kpis["month_purchase"])),
        ]
        for index, metric in enumerate(performance):
            self.performance_grid.addWidget(
                _stat_card(*metric, C["accent"] if index == 3 else None),
                index // 3, index % 3)
        for row in self.rows:
            row["actions"] = "View Â· Edit Â· Products Â· Invoices Â· Ledger Â· Add Stock"
        _fill_table(
            self.table, self.rows,
            ["code", "name", "contact_person", "phone", "gstin", "city",
             "total_products_purchased", "total_purchase_value",
             "current_stock_qty", "current_stock_value",
             "last_purchase_date", "pending_payment", "status", "actions"],
            currency_columns=(7, 9, 11), status_column=12)
        self.count.setText(
            f"{len(self.rows)} supplier{'s' if len(self.rows) != 1 else ''}")

    def _view(self, row, _column):
        if 0 <= row < len(self.rows):
            self.view_requested.emit(self.rows[row]["code"])

    def _edit_selected(self, _point):
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            self.edit_requested.emit(self.rows[row]["code"])

    def _cell_action(self, row, column):
        if column == 13 and 0 <= row < len(self.rows):
            self.view_requested.emit(self.rows[row]["code"])


class SupplierPage(QWidget):
    def __init__(self, db_name, company_name="", on_back=None,
                 current_user="Admin", parent=None):
        super().__init__(parent)
        ensure_global_input_guard()
        apply_app_icon(self)
        self.db_name = db_name
        self.current_user = current_user
        init_supplier_tables(db_name)
        self.setStyleSheet(f"background:{C['bg_light']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.list_page = SupplierListWidget(db_name, company_name)
        self.detail_page = None
        self.form_page = None
        self.stack.addWidget(self.list_page)

        self.list_page.add_requested.connect(self._add)
        self.list_page.edit_requested.connect(self._edit)
        self.list_page.view_requested.connect(self._view)

    def _ensure_form_page(self):
        if self.form_page is None:
            self.form_page = SupplierFormWidget(self.db_name, self.current_user)
            self.form_page.cancelled.connect(self._show_list)
            self.form_page.saved.connect(self._saved)
            self.stack.addWidget(self.form_page)
        return self.form_page

    def _ensure_detail_page(self):
        if self.detail_page is None:
            self.detail_page = SupplierDetailWidget(self.db_name)
            self.detail_page.back_requested.connect(self._show_list)
            self.detail_page.edit_requested.connect(self._edit)
            self.stack.addWidget(self.detail_page)
        return self.detail_page

    def _show_list(self):
        self.list_page.refresh()
        self.stack.setCurrentWidget(self.list_page)

    def _add(self):
        form_page = self._ensure_form_page()
        form_page.load_for_add()
        self.stack.setCurrentWidget(form_page)

    def _edit(self, code):
        form_page = self._ensure_form_page()
        form_page.load_for_edit(code)
        self.stack.setCurrentWidget(form_page)

    def _view(self, code):
        detail_page = self._ensure_detail_page()
        detail_page.load_supplier(code)
        self.stack.setCurrentWidget(detail_page)

    def _saved(self, code):
        self.list_page.refresh()
        detail_page = self._ensure_detail_page()
        detail_page.load_supplier(code)
        self.stack.setCurrentWidget(detail_page)

    def refresh(self):
        self.list_page.refresh()

    def refresh_light(self):
        self.list_page.refresh()

