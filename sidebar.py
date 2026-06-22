"""
sidebar.py  —  Evo Aura  •  Apple-Style Collapsible Sidebar
============================================================
PyQt6  |  Phosphor Icons (MIT)  |  macOS / Apple Music aesthetic

Usage:
    from sidebar import Sidebar
    sidebar = Sidebar(on_navigate=lambda key: print(key))
    # Toggle expand/collapse:
    sidebar.toggle()

Icon PNGs are loaded from ./icons/ folder (created by icon downloader).
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QApplication, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QStackedWidget
)
from PyQt6.QtGui  import (
    QFont, QColor, QPixmap, QPainter, QIcon
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QVariantAnimation, QEasingCurve,
    QPoint, QSize, QRect, pyqtSignal
)
from input_behavior import ensure_global_input_guard
from app_branding import apply_app_icon

# ─────────────────────────────────────────────────────────────
#  DESIGN TOKENS  —  Apple Music / macOS Light
# ─────────────────────────────────────────────────────────────
C = dict(
    sidebar_bg      = "#F2F2F7",        # sidebar background
    sidebar_border  = "#D2D2D7",        # right edge border
    item_hover      = "#E5E5EA",        # hover tint
    item_active_bg  = "rgba(250,45,72,0.10)",
    item_active_bd  = "#FA2D48",        # left border
    text_primary    = "#1D1D1F",        # label text
    text_secondary  = "#6E6E73",        # section header text
    text_disabled   = "#A1A1A6",        # hint
    accent          = "#FA2D48",        # Apple Music pink/red
    flyout_bg       = "#FFFFFF",
    flyout_border   = "#D2D2D7",
    divider         = "#D2D2D7",
    brand_bg        = "rgba(250,45,72,0.08)",
    brand_border    = "rgba(250,45,72,0.22)",
)

SIDEBAR_FONT = "Segoe Print"
SECTION_FONT_SIZE = 15
ITEM_FONT_SIZE = 10
PRIMARY_FONT_SIZE = 15
META_FONT_SIZE = 9
FONT = "'Segoe Print', 'Segoe UI', Arial"

ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")

SIDEBAR_EXPANDED  = 260
SIDEBAR_COLLAPSED = 64


# ─────────────────────────────────────────────────────────────
#  NAV STRUCTURE
# ─────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("", [
        ("home",     "Dashboard",        "home"),
    ]),
    ("Sales", [
        ("new_sale",          "New Sale",          "sale"),
        ("returns",       "Returns",           "returns"),
        ("bill_view",     "Bill View",         "bill_view"),
    ]),
    ("Inventory", [
        ("product",      "Products",          "products"),
        ("purchase_orders","Purchase Invoices", "purchase_orders"),
        ("suppliers",     "Suppliers",         "suppliers"),
        ("low_stock",     "Low Stock",         "low_stock"),
    ]),
    ("Customers", [
        ("customer",     "Customers",         "customers"),
        ("credit",        "Credit Mgmt",       "credit"),
        ("loyalty",       "Loyalty",           "loyalty"),
    ]),
    ("Finance", [
        ("pl_summarys",    "P & L Summary",     "pl_summary"),
        ("expense",       "Expense Tracking",  "expenses"),
        ("gst",           "GST Breakdown",     "gst"),
        ("cashflow",      "Cash Flow",         "cashflow"),
    ]),
    ("Reports", [
        ("daybook",       "Day Book",          "day_book"),
        ("stock_reports",  "Stock Report",      "stock_report"),
        ("trial_balance", "Trial Balance",     "trial_balance"),
        ("export",        "Export",            "export"),
    ]),
    ("Settings", [
        ("company",       "Company",           "company_settings"),
        ("users_roles",   "Users & Roles",     "users"),
        ("securitys",      "Security",          "security"),
        ("audit",         "Audit Log",         "audit_log"),
    ]),
]

# Section → icon key mapping (for collapsed header)
_SECTION_ICON = {
    "Sales":     "sales",
    "Inventory": "products",
    "Customers": "customers",
    "Finance":   "pl_summary",
    "Reports":   "stock_report",
    "Settings":  "security",
}


# ─────────────────────────────────────────────────────────────
#  ICON LOADER  — loads PNG and tints it programmatically
# ─────────────────────────────────────────────────────────────

def _load_icon(key: str, size: int = 18, color: str = "#1D1D1F") -> QIcon:
    """Load PNG from icons/ and tint to `color`."""
    path = os.path.join(ICONS_DIR, f"{key}.png")
    if not os.path.exists(path):
        return QIcon()

    pix = QPixmap(path).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )

    # Tint: paint a solid colour with SourceIn composition
    tinted = QPixmap(pix.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pix)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()

    return QIcon(tinted)


def _pixmap(key: str, size: int = 18, color: str = "#1D1D1F") -> QPixmap:
    path = os.path.join(ICONS_DIR, f"{key}.png")
    if not os.path.exists(path):
        return QPixmap()
    pix = QPixmap(path).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )
    # Sample corners to detect whether icon has a real alpha channel
    from PyQt6.QtGui import QImage
    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    step_x = max(1, w // 8)
    step_y = max(1, h // 8)
    has_alpha = any(
        (img.pixel(x, y) >> 24) < 255
        for x in range(0, w, step_x)
        for y in range(0, h, step_y)
    )
    tinted = QPixmap(pix.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    if has_alpha:
        # Transparent PNG: SourceIn tints the alpha shape with target color
        painter.drawPixmap(0, 0, pix)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color))
    else:
        # Solid PNG (no alpha channel): fill color then multiply icon luminance
        painter.fillRect(tinted.rect(), QColor(color))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.drawPixmap(0, 0, pix)
    painter.end()
    return tinted


# ─────────────────────────────────────────────────────────────
#  NAV BUTTON  — icon-only or icon + label
# ─────────────────────────────────────────────────────────────

class _NavButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon_key: str, label: str, active: bool = False,
                 primary: bool = False):
        super().__init__()
        self._icon_key = icon_key
        self._label    = label
        self._active   = active
        self._primary  = primary
        self._hovered  = False
        self._expanded = True

        self.setFixedHeight(42 if primary else 34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 0, 10, 0)
        self._layout.setSpacing(10)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(24, 24)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background:transparent;border:none;")

        self._text_lbl = QLabel(label)
        self._text_lbl.setFont(QFont(
            SIDEBAR_FONT,
            PRIMARY_FONT_SIZE if primary else ITEM_FONT_SIZE,
            QFont.Weight.DemiBold if primary else QFont.Weight.Normal,
        ))
        self._text_lbl.setStyleSheet(f"background:transparent;border:none;color:{C['text_primary']};")
        self._text_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._layout.addWidget(self._icon_lbl)
        self._layout.addWidget(self._text_lbl)
        self._layout.addStretch()

        self._refresh()

    def set_active(self, active: bool):
        self._active = active
        self._refresh()

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self._text_lbl.setVisible(expanded)
        if expanded:
            # Restore left-aligned layout: margins + trailing stretch
            self._icon_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            # Remove any centering stretches (index 0 if present)
            if self._layout.count() > 0:
                first = self._layout.itemAt(0)
                if first and first.spacerItem():
                    self._layout.takeAt(0)
            # Ensure trailing stretch exists
            last = self._layout.itemAt(self._layout.count() - 1)
            if not (last and last.spacerItem()):
                self._layout.addStretch()
            self._layout.setContentsMargins(10, 0, 10, 0)
            self._layout.setSpacing(10)
            self.setFixedHeight(42 if self._primary else 34)
            self.setToolTip("")
        else:
            # Centering: remove trailing stretch, add leading stretch, zero margins
            last = self._layout.itemAt(self._layout.count() - 1)
            if last and last.spacerItem():
                self._layout.takeAt(self._layout.count() - 1)
            first = self._layout.itemAt(0)
            if not (first and first.spacerItem()):
                self._layout.insertStretch(0, 1)
            self._layout.addStretch(1)
            self._layout.setContentsMargins(0, 0, 0, 0)
            self._layout.setSpacing(0)
            self.setFixedHeight(44)
            self.setToolTip(self._label)
        self._refresh()

    def _refresh(self):
        col = C["accent"] if self._active else C["text_primary"]
        px  = _pixmap(self._icon_key, 24, col)
        if not px.isNull():
            self._icon_lbl.setFixedSize(24, 24)
            self._icon_lbl.setPixmap(px)
        weight = "700" if self._active else ("600" if self._primary else "400")
        sz = PRIMARY_FONT_SIZE if self._primary else ITEM_FONT_SIZE
        self._text_lbl.setStyleSheet(
            f"background:transparent;border:none;color:{col};"
            f"font-family:'{SIDEBAR_FONT}';font-weight:{weight};font-size:{sz}pt;"
        )
        self.update()

    def paintEvent(self, e):
        from PyQt6.QtGui import QPainter, QBrush, QPen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(2, 1, -2, -1)

        if self._active:
            painter.setBrush(QBrush(QColor(250, 45, 72, 25)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r, 8, 8)
            # Left accent bar
            bar = QRect(2, 8, 3, self.height() - 16)
            painter.setBrush(QBrush(QColor(C["accent"])))
            painter.drawRoundedRect(bar, 2, 2)
        elif self._hovered:
            painter.setBrush(QBrush(QColor(C["item_hover"])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r, 8, 8)

    def enterEvent(self, e):
        self._hovered = True
        self._refresh()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self._refresh()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


# ─────────────────────────────────────────────────────────────
#  FLYOUT ROW  — single item inside the flyout popup
# ─────────────────────────────────────────────────────────────

class _FlyoutRow(QWidget):
    def __init__(self, icon_key, label, key, is_active, on_nav, flyout):
        super().__init__()
        self._on_nav    = on_nav
        self._flyout    = flyout
        self._key       = key
        self._icon_key  = icon_key
        self._is_active = is_active

        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        rl = QHBoxLayout(self)
        rl.setContentsMargins(8, 0, 8, 0)
        rl.setSpacing(10)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(18, 18)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background:transparent;border:none;")

        self._text_lbl = QLabel(label)
        self._text_lbl.setFont(QFont(SIDEBAR_FONT, ITEM_FONT_SIZE))

        rl.addWidget(self._icon_lbl)
        rl.addWidget(self._text_lbl)
        rl.addStretch()

        self._apply_style(hovered=False)

    def _apply_style(self, hovered: bool):
        if self._is_active:
            bg  = "rgba(250,45,72,0.10)"
            col = C["accent"]
            fw  = "600"
        elif hovered:
            bg  = C["item_hover"]
            col = C["text_primary"]
            fw  = "400"
        else:
            bg  = "transparent"
            col = C["text_primary"]
            fw  = "400"

        self.setStyleSheet(f"background:{bg};border:none;border-radius:8px;")
        px = _pixmap(self._icon_key, 16, col)
        if not px.isNull():
            self._icon_lbl.setPixmap(px)
        self._text_lbl.setStyleSheet(
            f"color:{col};background:transparent;border:none;font-weight:{fw};"
            f"font-family:'{SIDEBAR_FONT}';font-size:{ITEM_FONT_SIZE}pt;"
        )

    def enterEvent(self, e):
        self._apply_style(hovered=True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._apply_style(hovered=False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._on_nav(self._key)
            self._flyout.hide()
        super().mousePressEvent(e)


# ─────────────────────────────────────────────────────────────
#  FLYOUT POPUP  (collapsed sidebar)
# ─────────────────────────────────────────────────────────────

class _FlyoutMenu(QWidget):
    """Flyout popup shown beside section headers when sidebar is collapsed."""

    def __init__(self, parent_window, title, items, on_nav, active_key):
        super().__init__(
            parent_window,
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint
        )
        # WA_StyledBackground makes Qt honour background in paintEvent for QWidget
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # WA_TranslucentBackground prevents OS painting solid black behind frameless window
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(150)
        self._hide_timer.timeout.connect(self.hide)

        self.setFixedWidth(210)
        self.setStyleSheet("background:transparent;")

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 35))
        self.setGraphicsEffect(shadow)

        # Inner card — white bg, rounded border, clips children correctly
        self._card = QFrame(self)
        self._card.setStyleSheet(f"""
            QFrame {{
                background    : {C['flyout_bg']};
                border-radius : 12px;
            }}
        """)
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        lay = QVBoxLayout(self._card)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(2)

        if title:
            hdr = QLabel(title.upper())
            hdr.setFont(QFont(
                SIDEBAR_FONT, ITEM_FONT_SIZE, QFont.Weight.DemiBold))
            hdr.setStyleSheet(
                f"color:{C['text_disabled']};background:transparent;border:none;"
                f"padding:2px 6px 6px 6px;letter-spacing:1.1px;"
            )
            lay.addWidget(hdr)
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(
                f"background:{C['divider']};border:none;margin:0 4px 4px 4px;")
            lay.addWidget(sep)

        self._rows = []
        for icon_key, label, key in items:
            is_active = (key == active_key)
            row = _FlyoutRow(icon_key, label, key, is_active, on_nav, self)
            lay.addWidget(row)
            self._rows.append(row)

        # Outer layout wraps the card with a small margin for shadow room
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(self._card)

    def set_active_key(self, active_key: str):
        """Refresh row accent states when the active page changes."""
        for row in self._rows:
            row._is_active = (row._key == active_key)
            row._apply_style(hovered=False)

    def show_beside(self, trigger_widget: QWidget):
        self._hide_timer.stop()
        gp = trigger_widget.mapToGlobal(QPoint(0, 0))
        self.move(gp.x() + trigger_widget.width() + 6, gp.y() - 10)
        self.adjustSize()
        self.raise_()
        self.show()

    def keep_open(self):     self._hide_timer.stop()
    def schedule_hide(self): self._hide_timer.start()

    def enterEvent(self, e):
        self._hide_timer.stop()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hide_timer.start()
        super().leaveEvent(e)


# ─────────────────────────────────────────────────────────────
#  NAV GROUP WIDGET
# ─────────────────────────────────────────────────────────────

class _NavGroup(QWidget):

    def __init__(self, title, items, buttons_dict, on_nav,
                 active_key, start_expanded=True):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self._title            = title
        self._items            = items
        self._on_nav           = on_nav
        self._buttons_dict     = buttons_dict
        self._active_key       = active_key
        self._group_expanded   = start_expanded
        self._sidebar_expanded = True
        self._flyout           = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 2, 0, 2)
        root.setSpacing(0)

        # ── Section header (titled groups only) ───────────────
        if title:
            self._hdr = QWidget()
            self._hdr.setFixedHeight(48)
            self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)
            self._hdr.setStyleSheet("background:transparent;border:none;")
            self._hdr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            self._hdr_layout = QHBoxLayout(self._hdr)
            self._hdr_layout.setContentsMargins(12, 0, 10, 0)
            self._hdr_layout.setSpacing(8)

            self._hdr_icon = QLabel()
            self._hdr_icon.setFixedSize(24, 24)
            self._hdr_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hdr_icon.setStyleSheet("background:transparent;border:none;")

            self._hdr_text = QLabel(title)
            self._hdr_text.setFont(QFont(
                SIDEBAR_FONT, SECTION_FONT_SIZE, QFont.Weight.DemiBold))
            self._hdr_text.setStyleSheet(
                f"color:{C['text_primary']};background:transparent;border:none;"
                f"font-family:'{SIDEBAR_FONT}';font-size:{SECTION_FONT_SIZE}pt;"
            )
            self._hdr_text.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

            self._chevron = QLabel("▾")
            self._chevron.setFont(QFont(SIDEBAR_FONT, 9))
            self._chevron.setStyleSheet(f"color:{C['text_disabled']};background:transparent;border:none;")

            self._hdr_layout.addWidget(self._hdr_icon)
            self._hdr_layout.addWidget(self._hdr_text)
            self._hdr_layout.addStretch()
            self._hdr_layout.addWidget(self._chevron)

            self._hdr.mousePressEvent = lambda e: self._toggle_group()
            self._hdr.enterEvent      = lambda e: self._on_hdr_enter(e)
            self._hdr.leaveEvent      = lambda e: self._on_hdr_leave(e)

            root.addWidget(self._hdr)
        else:
            self._hdr = None

        # ── Items container ───────────────────────────────────
        self._items_w = QWidget()
        self._items_w.setStyleSheet("background:transparent;")
        items_lay = QVBoxLayout(self._items_w)
        items_lay.setContentsMargins(0, 0, 0, 4)
        items_lay.setSpacing(1)

        for icon_key, label, key in items:
            btn = _NavButton(
                icon_key, label, active=(key == active_key),
                primary=not bool(title))
            btn.clicked.connect(lambda k=key: on_nav(k))
            items_lay.addWidget(btn)
            buttons_dict[key] = btn

        root.addWidget(self._items_w)

        # ── Collapsed icon for untitled groups (Dashboard) ────
        # Groups with no title have no _hdr, so when the sidebar collapses
        # the items are hidden and nothing is visible.  This standalone icon
        # button keeps Dashboard reachable and shows the active accent.
        if not title:
            self._collapsed_btn = QWidget()
            self._collapsed_btn.setFixedHeight(44)
            self._collapsed_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._collapsed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._collapsed_btn.setStyleSheet("background:transparent;border:none;")

            cb_lay = QHBoxLayout(self._collapsed_btn)
            cb_lay.setContentsMargins(0, 0, 0, 0)
            cb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self._collapsed_icon_lbl = QLabel()
            self._collapsed_icon_lbl.setFixedSize(22, 22)
            self._collapsed_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._collapsed_icon_lbl.setStyleSheet("background:transparent;border:none;")
            cb_lay.addWidget(self._collapsed_icon_lbl)

            self._collapsed_btn.mousePressEvent = lambda e: self._on_collapsed_click()
            self._collapsed_btn.enterEvent      = lambda e: self._on_collapsed_enter(e)
            self._collapsed_btn.leaveEvent      = lambda e: self._on_collapsed_leave(e)
            self._collapsed_btn.setVisible(False)   # shown only when sidebar is collapsed
            root.addWidget(self._collapsed_btn)
        else:
            self._collapsed_btn = None

        # Divider after every group
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:{C['divider']};border:none;margin:4px 8px;")
        root.addWidget(div)

        self._items_w.setVisible(start_expanded)
        self._update_header(start_expanded)

    # ── Collapsed-icon helpers (untitled groups) ──────────────

    def _refresh_collapsed_btn(self):
        if not self._collapsed_btn or not self._items:
            return
        is_active = any(k == self._active_key for _, _, k in self._items)
        col = C["accent"] if is_active else C["text_primary"]
        px = _pixmap(self._items[0][0], 26, col)
        if not px.isNull():
            self._collapsed_icon_lbl.setFixedSize(26, 26)
            self._collapsed_icon_lbl.setPixmap(px)
        if is_active:
            self._collapsed_btn.setStyleSheet(
                "background:rgba(250,45,72,0.10);border-radius:10px;"
            )
        else:
            self._collapsed_btn.setStyleSheet("background:transparent;border:none;")

    def _on_collapsed_click(self):
        if self._items:
            self._on_nav(self._items[0][2])

    def _on_collapsed_enter(self, e):
        is_active = any(k == self._active_key for _, _, k in self._items)
        col = C["accent"] if is_active else C["text_primary"]
        px = _pixmap(self._items[0][0], 26, col)
        if not px.isNull():
            self._collapsed_icon_lbl.setFixedSize(26, 26)
            self._collapsed_icon_lbl.setPixmap(px)
        self._collapsed_btn.setStyleSheet(
            f"background:{C['item_hover']};border-radius:10px;"
        )

    def _on_collapsed_leave(self, e):
        self._refresh_collapsed_btn()

    # ── Hover handlers (titled section headers) ───────────────

    def _on_hdr_enter(self, e):
        self._hdr.setStyleSheet(
            f"background:{C['item_hover']};border:none;border-radius:8px;"
        )
        if not self._sidebar_expanded and self._title:
            self._get_flyout().show_beside(self._hdr)

    def _on_hdr_leave(self, e):
        group_has_active = (not self._sidebar_expanded and
                            any(k == self._active_key for _, _, k in self._items))
        if group_has_active:
            self._hdr.setStyleSheet("background:rgba(250,45,72,0.10);border-radius:10px;")
        else:
            self._hdr.setStyleSheet("background:transparent;border:none;")
        if not self._sidebar_expanded and self._flyout:
            self._flyout.schedule_hide()

    # ── Toggle ────────────────────────────────────────────────

    def _toggle_group(self):
        if not self._sidebar_expanded:
            return
        self._group_expanded = not self._group_expanded
        self._items_w.setVisible(self._group_expanded)
        self._update_header(self._group_expanded)

    def _update_header(self, expanded: bool):
        if not self._hdr:
            return
        icon_key = _SECTION_ICON.get(self._title, "")
        group_has_active = any(k == self._active_key for _, _, k in self._items)
        if self._sidebar_expanded:
            # Full header: icon + text + chevron
            self._hdr.setFixedHeight(48)
            group_has_active = any(k == self._active_key for _, _, k in self._items)
            icon_col = C["accent"] if group_has_active else C["text_primary"]
            px = _pixmap(icon_key, 24, icon_col)
            if not px.isNull():
                self._hdr_icon.setFixedSize(24, 24)
                self._hdr_icon.setPixmap(px)
            self._hdr_icon.setVisible(True)
            self._hdr_text.setVisible(True)
            self._chevron.setVisible(True)
            self._chevron.setText("▾" if expanded else "▸")
            # Restore left layout — remove leading centering stretch if present
            first = self._hdr_layout.itemAt(0)
            if first and first.spacerItem():
                self._hdr_layout.takeAt(0)
            self._hdr_layout.setContentsMargins(12, 0, 10, 0)
            self._hdr_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            # Accent bg when active, else transparent
            if group_has_active:
                self._hdr.setStyleSheet("background:rgba(250,45,72,0.07);border-radius:10px;")
            else:
                self._hdr.setStyleSheet("background:transparent;border:none;")
        else:
            # Collapsed: large icon only — red accent if active page is inside
            self._hdr.setFixedHeight(48)
            icon_col = C["accent"] if group_has_active else C["text_primary"]
            px = _pixmap(icon_key, 26, icon_col)
            if not px.isNull():
                self._hdr_icon.setFixedSize(26, 26)
                self._hdr_icon.setPixmap(px)
            self._hdr_icon.setVisible(True)
            self._hdr_text.setVisible(False)
            self._chevron.setVisible(False)
            # Stretch centering: insert leading stretch if not already there
            first = self._hdr_layout.itemAt(0)
            if not (first and first.spacerItem()):
                self._hdr_layout.insertStretch(0, 1)
            last = self._hdr_layout.itemAt(self._hdr_layout.count() - 1)
            if not (last and last.spacerItem()):
                self._hdr_layout.addStretch(1)
            self._hdr_layout.setContentsMargins(0, 0, 0, 0)
            if group_has_active:
                self._hdr.setStyleSheet("background:rgba(250,45,72,0.10);border-radius:10px;")
            else:
                self._hdr.setStyleSheet("background:transparent;border:none;")

    # ── Active key propagation ────────────────────────────────

    def set_active_key(self, key: str):
        """Called by Sidebar on every navigation to refresh accent indicators."""
        self._active_key = key
        self._update_header(self._group_expanded)   # always refresh — both modes
        if not self._sidebar_expanded:
            if self._collapsed_btn:
                self._refresh_collapsed_btn()
        if self._flyout:
            self._flyout.set_active_key(key)

    # ── Sidebar expand / collapse ─────────────────────────────

    def set_sidebar_expanded(self, expanded: bool):
        self._sidebar_expanded = expanded
        self._update_header(self._group_expanded)
        if not expanded:
            self._items_w.setVisible(False)
            if self._collapsed_btn:
                self._collapsed_btn.setVisible(True)
                self._refresh_collapsed_btn()
        else:
            self._items_w.setVisible(self._group_expanded)
            if self._collapsed_btn:
                self._collapsed_btn.setVisible(False)
        if self._flyout:
            self._flyout.hide()

    # ── Flyout ────────────────────────────────────────────────

    def _get_flyout(self):
        if self._flyout is None:
            win = self.window()
            self._flyout = _FlyoutMenu(
                parent_window = win,
                title         = self._title,
                items         = self._items,
                on_nav        = self._on_nav,
                active_key    = self._active_key,
            )
        return self._flyout


# ─────────────────────────────────────────────────────────────
#  DIVIDER HELPER
# ─────────────────────────────────────────────────────────────

def _divider():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background:{C['divider']};border:none;max-height:1px;")
    return f


# ─────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────

class Sidebar(QFrame):

    EXPANDED_W  = SIDEBAR_EXPANDED
    COLLAPSED_W = SIDEBAR_COLLAPSED

    def __init__(self, on_navigate):
        super().__init__()
        ensure_global_input_guard()
        apply_app_icon(self)
        self.on_navigate  = on_navigate
        self._buttons     = {}          # key -> _NavButton
        self._groups      = []          # list[_NavGroup]
        self._active_key  = "home"
        self._is_expanded = True

        self.setMinimumWidth(self.EXPANDED_W)
        self.setMaximumWidth(self.EXPANDED_W)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"""
            QFrame {{
                background   : {C['sidebar_bg']};
                border       : none;
                border-right : 1px solid {C['sidebar_border']};
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 14, 8, 14)
        outer.setSpacing(0)

        # ── Brand / Logo row ──────────────────────────────────
        self._brand_row = QWidget()
        self._brand_row.setStyleSheet("background:transparent;")
        br_lay = QHBoxLayout(self._brand_row)
        br_lay.setContentsMargins(4, 0, 4, 0)
        br_lay.setSpacing(10)

        # Logo badge
        self._logo_badge = QWidget()
        self._logo_badge.setFixedSize(44, 44)
        self._logo_badge.setStyleSheet(
            "background:transparent;border:none;"
        )
        lb_lay = QHBoxLayout(self._logo_badge)
        lb_lay.setContentsMargins(0, 0, 0, 0)
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(24, 24)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px = _pixmap("logo", 24, C["accent"])
        if not px.isNull():
            logo_lbl.setPixmap(px)
        logo_lbl.setStyleSheet("background:transparent;border:none;")
        lb_lay.addWidget(logo_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self._brand_name = QLabel("Evo Aura")
        self._brand_name.setFont(QFont(
            SIDEBAR_FONT, ITEM_FONT_SIZE, QFont.Weight.DemiBold))
        self._brand_name.setStyleSheet(
            f"color:{C['text_primary']};background:transparent;border:none;"
            f"font-family:'{SIDEBAR_FONT}';font-size:{ITEM_FONT_SIZE}pt;")

        br_lay.addWidget(self._logo_badge)
        br_lay.addWidget(self._brand_name)
        br_lay.addStretch()

        outer.addWidget(self._brand_row)
        outer.addSpacing(14)
        outer.addWidget(_divider())
        outer.addSpacing(8)

        # ── Scrollable nav ────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea  {{ background:transparent; border:none; }}
            QScrollBar:vertical {{
                background : {C['sidebar_bg']}; width:4px; border-radius:2px;
            }}
            QScrollBar::handle:vertical {{
                background : {C['sidebar_border']}; border-radius:2px; min-height:20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)

        nav_w = QWidget()
        nav_w.setStyleSheet("background:transparent;")
        nav_lay = QVBoxLayout(nav_w)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(0)
        nav_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        for i, (section_title, items) in enumerate(NAV_ITEMS):
            grp = _NavGroup(
                title          = section_title,
                items          = items,
                buttons_dict   = self._buttons,
                on_nav         = self._nav,
                active_key     = "home",
                start_expanded = (i == 0),      # only Dashboard expanded
            )
            nav_lay.addWidget(grp)
            self._groups.append(grp)

        scroll.setWidget(nav_w)
        outer.addWidget(scroll, 1)

        # ── Bottom user row ───────────────────────────────────
        outer.addSpacing(8)
        outer.addWidget(_divider())
        outer.addSpacing(10)

        self._bottom_row = QWidget()
        self._bottom_row.setStyleSheet("background:transparent;")
        bot_lay = QHBoxLayout(self._bottom_row)
        bot_lay.setContentsMargins(4, 0, 4, 0)
        bot_lay.setSpacing(10)

        avatar = QWidget()
        avatar.setFixedSize(30, 30)
        avatar.setStyleSheet(
            f"background:{C['brand_bg']};border:1px solid {C['brand_border']};"
            f"border-radius:15px;"
        )
        av_lay = QHBoxLayout(avatar)
        av_lay.setContentsMargins(0, 0, 0, 0)
        av_lbl = QLabel("EA")
        av_lbl.setFont(QFont(
            SIDEBAR_FONT, META_FONT_SIZE, QFont.Weight.DemiBold))
        av_lbl.setStyleSheet(f"color:{C['accent']};background:transparent;border:none;")
        av_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av_lay.addWidget(av_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self._ver_lbl = QLabel("Evo Aura  v1.0")
        self._ver_lbl.setFont(QFont(SIDEBAR_FONT, META_FONT_SIZE))
        self._ver_lbl.setStyleSheet(
            f"color:{C['text_disabled']};background:transparent;border:none;"
            f"font-family:'{SIDEBAR_FONT}';font-size:{META_FONT_SIZE}pt;")

        bot_lay.addWidget(avatar)
        bot_lay.addWidget(self._ver_lbl)
        bot_lay.addStretch()
        outer.addWidget(self._bottom_row)

        QTimer.singleShot(0, lambda: self._apply_mode(True))

    # ── Toggle Expand / Collapse ──────────────────────────────

    def toggle(self):
        # Guard: ignore clicks while a slide is in progress
        if getattr(self, "_animating", False):
            return

        self._animating    = True
        self._is_expanded  = not self._is_expanded
        start_w = self.width()
        end_w   = self.EXPANDED_W if self._is_expanded else self.COLLAPSED_W

        # ── Width slider ──────────────────────────────────────
        anim = QVariantAnimation(self)
        anim.setStartValue(start_w)
        anim.setEndValue(end_w)
        anim.setDuration(260)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.valueChanged.connect(self._on_slide_value)
        anim.finished.connect(self._on_slide_finished)
        anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)

        # ── Text / label opacity fade ─────────────────────────
        # Collapsing → fade labels out immediately and switch icons
        # Expanding  → switch layout at midpoint, fade labels in at end
        if not self._is_expanded:
            self._fade_labels(visible=False, delay_ms=0)
            self._apply_mode(False, icons_only=True)
        else:
            QTimer.singleShot(130, lambda: self._apply_mode(True, icons_only=False))

    def _on_slide_value(self, val: int):
        self.setMinimumWidth(val)
        self.setMaximumWidth(val)

    def _on_slide_finished(self):
        # Snap to exact target width and clear guard flag
        w = self.EXPANDED_W if self._is_expanded else self.COLLAPSED_W
        self.setMinimumWidth(w)
        self.setMaximumWidth(w)
        self._animating = False
        if self._is_expanded:
            self._fade_labels(visible=True, delay_ms=0)

    def _fade_labels(self, visible: bool, delay_ms: int = 0):
        """Fade brand name and version label in / out with opacity animation."""
        targets = [self._brand_name, self._ver_lbl]
        target_opacity = 1.0 if visible else 0.0

        def _do_fade():
            for w in targets:
                if visible:
                    w.setVisible(True)
                eff = w.graphicsEffect()
                if not isinstance(eff, QGraphicsOpacityEffect):
                    eff = QGraphicsOpacityEffect(w)
                    w.setGraphicsEffect(eff)
                anim = QPropertyAnimation(eff, b"opacity", w)
                anim.setDuration(160)
                anim.setStartValue(eff.opacity())
                anim.setEndValue(target_opacity)
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                if not visible:
                    anim.finished.connect(lambda _w=w: _w.setVisible(False))
                anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _do_fade)
        else:
            _do_fade()

    def _apply_mode(self, expanded: bool, icons_only: bool = False):
        if not icons_only:
            self._brand_name.setVisible(expanded)
            self._ver_lbl.setVisible(expanded)
        for btn in self._buttons.values():
            btn.set_expanded(expanded)
        for grp in self._groups:
            grp.set_sidebar_expanded(expanded)
        # Center the logo badge when collapsed
        br_lay = self._brand_row.layout()
        if not expanded:
            br_lay.setContentsMargins(0, 0, 0, 0)
            self._logo_badge.setStyleSheet(
                "background:transparent;border:none;margin:0 auto;"
            )
        else:
            br_lay.setContentsMargins(4, 0, 4, 0)

    # ── Navigation ────────────────────────────────────────────

    def _nav(self, key: str):
        if self._active_key in self._buttons:
            self._buttons[self._active_key].set_active(False)
        self._active_key = key
        if key in self._buttons:
            self._buttons[key].set_active(True)
        for grp in self._groups:
            grp.set_active_key(key)
        self.on_navigate(key)

    def set_active(self, key: str):
        """Update highlight without firing navigation callback."""
        if self._active_key in self._buttons:
            self._buttons[self._active_key].set_active(False)
        self._active_key = key
        if key in self._buttons:
            self._buttons[key].set_active(True)
        for grp in self._groups:
            grp.set_active_key(key)

    def set_company(self, name: str):
        """Update the brand name label in the sidebar header."""
        self._brand_name.setText(name)


# ─────────────────────────────────────────────────────────────
#  MAIN WINDOW  —  wires Sidebar + all pages via QStackedWidget
# ─────────────────────────────────────────────────────────────
