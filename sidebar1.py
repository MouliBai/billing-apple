"""
sidebar.py  —  Evo Aura  •  Collapsible Sidebar
================================================
Completely standalone sidebar module.
Import in dashboard.py:
    from sidebar import Sidebar
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QSizePolicy
)
from PyQt5.QtGui   import QFont, QColor
from PyQt5.QtCore  import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint

# ─────────────────────────────────────────────────────────────
#  DESIGN TOKENS  (must match dashboard.py)
# ─────────────────────────────────────────────────────────────
C_PRIMARY  = "#1a7fe8"
C_SIDEBAR  = "#0f172a"
C_SIDEBAR_H = "#1e293b"
FONT_BODY  = "Segoe UI"

# ─────────────────────────────────────────────────────────────
#  ICON MAP  — swap any value to your own PNG/SVG path
# ─────────────────────────────────────────────────────────────
ICON_HOME         = "🏠"
ICON_SALE         = "🧾"
ICON_RETURNS      = "🔁"
ICON_BILL_VIEW    = "📋"
ICON_PRODUCTS     = "📦"
ICON_PURCHASE     = "🛒"
ICON_SUPPLIERS    = "🚚"
ICON_LOW_STOCK    = "⚠️"
ICON_CUSTOMERS    = "👥"
ICON_CREDIT       = "💳"
ICON_LOYALTY      = "⭐"
ICON_PL           = "💰"
ICON_EXPENSE      = "💸"
ICON_GST          = "🧮"
ICON_CASHFLOW     = "📈"
ICON_DAYBOOK      = "📊"
ICON_STOCK_RPT    = "📑"
ICON_TRIAL        = "📉"
ICON_EXPORT       = "📤"
ICON_COMPANY      = "🏢"
ICON_USERS        = "👤"
ICON_SECURITY     = "🔐"
ICON_AUDIT        = "🗂️"
ICON_APP          = "⚡"

NAV_ITEMS = [
    ("", [
        (ICON_HOME,      "Dashboard",       "home"),
    ]),
    ("Sales", [
        (ICON_SALE,      "New Sale",         "sale"),
        (ICON_RETURNS,   "Returns",          "returns"),
        (ICON_BILL_VIEW, "Bill View",        "bill_view"),
    ]),
    ("Inventory", [
        (ICON_PRODUCTS,  "Products",         "products"),
        (ICON_PURCHASE,  "Purchase Orders",  "purchase_orders"),
        (ICON_SUPPLIERS, "Suppliers",        "suppliers"),
        (ICON_LOW_STOCK, "Low Stock",        "low_stock"),
    ]),
    ("Customers", [
        (ICON_CUSTOMERS, "Customers",        "customers"),
        (ICON_CREDIT,    "Credit Mgmt",      "credit"),
        (ICON_LOYALTY,   "Loyalty",          "loyalty"),
    ]),
    ("Finance", [
        (ICON_PL,        "P & L Summary",    "pl_summary"),
        (ICON_EXPENSE,   "Expense Tracking", "expenses"),
        (ICON_GST,       "GST Breakdown",    "gst"),
        (ICON_CASHFLOW,  "Cash Flow",        "cashflow"),
    ]),
    ("Reports", [
        (ICON_DAYBOOK,   "Day Book",         "day_book"),
        (ICON_STOCK_RPT, "Stock Report",     "stock_report"),
        (ICON_TRIAL,     "Trial Balance",    "trial_balance"),
        (ICON_EXPORT,    "Export",           "export"),
    ]),
    ("Settings", [
        (ICON_COMPANY,   "Company",          "company_settings"),
        (ICON_USERS,     "Users & Roles",    "users"),
        (ICON_SECURITY,  "Security",         "security"),
        (ICON_AUDIT,     "Audit Log",        "audit_log"),
    ]),
]

_SECTION_ICONS = {
    "Sales":      ICON_SALE,
    "Inventory":  ICON_PRODUCTS,
    "Customers":  ICON_CUSTOMERS,
    "Finance":    ICON_PL,
    "Reports":    ICON_DAYBOOK,
    "Settings":   ICON_SECURITY,
}

# ─────────────────────────────────────────────────────────────
#  SIDEBAR DIMENSIONS  — edit here only
# ─────────────────────────────────────────────────────────────
SIDEBAR_EXPANDED  = 260
SIDEBAR_COLLAPSED = 64


# ─────────────────────────────────────────────────────────────
#  NAV BUTTON
# ─────────────────────────────────────────────────────────────

class _NavButton(QPushButton):

    _EXPANDED_STYLE = f"""
        QPushButton {{
            text-align    : left;
            padding       : 0 14px;
            border        : none;
            border-radius : 8px;
            font-size     : 13px;
            font-weight   : 400;
            color         : #94a3b8;
            background    : transparent;
        }}
        QPushButton:hover {{
            background : #1e293b;
            color      : #e2e8f0;
        }}
        QPushButton:checked {{
            background   : {C_PRIMARY}22;
            color        : {C_PRIMARY};
            font-weight  : 600;
            border-left  : 3px solid {C_PRIMARY};
            padding-left : 11px;
        }}
    """

    _COLLAPSED_STYLE = f"""
        QPushButton {{
            text-align    : center;
            padding       : 0;
            border        : none;
            border-radius : 8px;
            font-size     : 18px;
            color         : #94a3b8;
            background    : transparent;
        }}
        QPushButton:hover {{
            background : #1e293b;
            color      : #e2e8f0;
        }}
        QPushButton:checked {{
            background  : {C_PRIMARY}22;
            color       : {C_PRIMARY};
            border-left : 3px solid {C_PRIMARY};
        }}
    """

    def __init__(self, icon, label, active=False):
        super().__init__()
        self._icon  = icon
        self._label = label
        self.setCheckable(True)
        self.setChecked(active)
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(self._EXPANDED_STYLE)
        self.set_expanded(True)

    def set_expanded(self, expanded: bool):
        if expanded:
            self.setText(f"  {self._icon}   {self._label}")
            self.setFixedHeight(42)
            self.setStyleSheet(self._EXPANDED_STYLE)
            self.setToolTip("")
        else:
            self.setText(self._icon)
            self.setFixedHeight(44)
            self.setStyleSheet(self._COLLAPSED_STYLE)
            self.setToolTip(self._label)


# ─────────────────────────────────────────────────────────────
#  FLYOUT POPUP  (collapsed sidebar hover)
# ─────────────────────────────────────────────────────────────

class _FlyoutMenu(QFrame):

    def __init__(self, parent_sidebar, title, items, buttons_dict,
                 on_nav, active_key):
        super().__init__(
            parent_sidebar.window(),
            Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(120)
        self._hide_timer.timeout.connect(self.hide)

        self.setStyleSheet("""
            QFrame {
                background    : #1a2744;
                border        : 1px solid #2d3f5e;
                border-radius : 12px;
            }
        """)
        self.setFixedWidth(220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(2)

        if title:
            title_lbl = QLabel(f"  {title.upper()}")
            title_lbl.setFont(QFont(FONT_BODY, 9, QFont.Bold))
            title_lbl.setStyleSheet(
                "color:#64748b; background:transparent; "
                "padding:2px 8px 6px 8px; letter-spacing:1.2px;"
            )
            lay.addWidget(title_lbl)
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background:#2d3f5e; border:none; margin:0 4px 4px 4px;")
            lay.addWidget(sep)

        for icon, label, key in items:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(key == active_key)
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align    : left; padding: 0 12px;
                    border        : none; border-radius: 8px;
                    font-size     : 13px; font-weight: 400;
                    color         : #94a3b8; background: transparent;
                }}
                QPushButton:hover  {{ background:#243352; color:#e2e8f0; }}
                QPushButton:checked {{
                    background:#1a7fe822; color:#1a7fe8;
                    font-weight:600; border-left:3px solid #1a7fe8;
                    padding-left:9px;
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._on_item(k))
            lay.addWidget(btn)
            if key not in buttons_dict:
                buttons_dict[key] = btn

        self._on_nav = on_nav

    def _on_item(self, key):
        self.hide()
        self._on_nav(key)

    def enterEvent(self, e):
        self._hide_timer.stop()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hide_timer.start()
        super().leaveEvent(e)

    def show_beside(self, trigger_widget: QWidget):
        self._hide_timer.stop()
        gp = trigger_widget.mapToGlobal(QPoint(0, 0))
        self.move(gp.x() + trigger_widget.width() + 4, gp.y() - 10)
        self.adjustSize()
        self.raise_()
        self.show()

    def keep_open(self):   self._hide_timer.stop()
    def schedule_hide(self): self._hide_timer.start()


# ─────────────────────────────────────────────────────────────
#  NAV GROUP WIDGET
# ─────────────────────────────────────────────────────────────

class NavGroupWidget(QWidget):

    def __init__(self, title, items, buttons_dict, on_nav, active_key,
                 start_expanded=True):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self._group_collapsed  = not start_expanded
        self._sidebar_expanded = True
        self._title            = title
        self._items            = items
        self._on_nav           = on_nav
        self._buttons_dict     = buttons_dict
        self._active_key       = active_key
        self._flyout           = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Section header button ─────────────────────────────
        if title:
            self._hdr_btn = QPushButton()
            self._hdr_btn.setFixedHeight(40)
            self._hdr_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._hdr_btn.setCursor(Qt.PointingHandCursor)
            self._hdr_btn.clicked.connect(self._toggle_group)
            self._hdr_btn.installEventFilter(self)
            root.addWidget(self._hdr_btn)
        else:
            self._hdr_btn = None

        # ── Items ─────────────────────────────────────────────
        self._items_widget = QWidget()
        self._items_widget.setStyleSheet("background:transparent;")
        items_lay = QVBoxLayout(self._items_widget)
        items_lay.setContentsMargins(0, 0, 0, 4)
        items_lay.setSpacing(1)

        for icon, label, key in items:
            btn = _NavButton(icon, label, active=(key == active_key))
            btn.clicked.connect(lambda _, k=key: on_nav(k))
            items_lay.addWidget(btn)
            buttons_dict[key] = btn

        root.addWidget(self._items_widget)

        if title:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background:#1e293b; border:none; margin:4px 8px;")
            root.addWidget(sep)

        self._items_widget.setVisible(start_expanded)
        self._update_header(expanded=start_expanded)

    # ── Flyout ────────────────────────────────────────────────

    def _get_flyout(self):
        if self._flyout is None:
            sidebar = self.parent()
            while sidebar and not isinstance(sidebar, Sidebar):
                sidebar = sidebar.parent()
            self._flyout = _FlyoutMenu(
                parent_sidebar = sidebar,
                title          = self._title,
                items          = self._items,
                buttons_dict   = self._buttons_dict,
                on_nav         = self._on_nav,
                active_key     = self._active_key,
            )
        return self._flyout

    def eventFilter(self, obj, event):
        if obj is self._hdr_btn and not self._sidebar_expanded:
            from PyQt5.QtCore import QEvent
            if event.type() == QEvent.Enter:
                self._get_flyout().show_beside(self._hdr_btn)
            elif event.type() == QEvent.Leave:
                self._get_flyout().schedule_hide()
        return super().eventFilter(obj, event)

    # ── Toggle ────────────────────────────────────────────────

    def _toggle_group(self):
        if not self._sidebar_expanded:
            return
        self._group_collapsed = not self._group_collapsed
        self._items_widget.setVisible(not self._group_collapsed)
        self._update_header(expanded=not self._group_collapsed)

    def _update_header(self, expanded: bool):
        if self._hdr_btn is None:
            return
        sec_icon = _SECTION_ICONS.get(self._title, "•")
        if self._sidebar_expanded:
            chevron = "▾" if expanded else "▸"
            self._hdr_btn.setText(f"  {sec_icon}   {self._title}   {chevron}")
            self._hdr_btn.setFixedHeight(40)
            self._hdr_btn.setStyleSheet(f"""
                QPushButton {{
                    text-align   : left; padding: 0 14px;
                    border       : none; border-radius: 8px;
                    font-size    : 12px; font-weight: 700;
                    color        : #64748b; background: transparent;
                    letter-spacing: 0.5px;
                }}
                QPushButton:hover {{ background:#1e293b; color:#94a3b8; }}
            """)
        else:
            self._hdr_btn.setText(sec_icon)
            self._hdr_btn.setFixedHeight(48)
            self._hdr_btn.setStyleSheet(f"""
                QPushButton {{
                    text-align    : center; padding: 0;
                    border        : none; border-radius: 8px;
                    font-size     : 20px; color: #94a3b8;
                    background    : transparent;
                }}
                QPushButton:hover {{ background:#1e293b; color:#e2e8f0; }}
            """)

    def set_sidebar_expanded(self, sidebar_expanded: bool):
        self._sidebar_expanded = sidebar_expanded
        if self._hdr_btn:
            self._update_header(expanded=not self._group_collapsed)
        if not sidebar_expanded:
            self._items_widget.setVisible(False)
        else:
            self._items_widget.setVisible(not self._group_collapsed)
        if self._flyout:
            self._flyout.hide()


# ─────────────────────────────────────────────────────────────
#  DIVIDER HELPER
# ─────────────────────────────────────────────────────────────

def _divider():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("background:#1e293b; border:none; max-height:1px;")
    return f


# ─────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────

class Sidebar(QFrame):

    EXPANDED_W  = SIDEBAR_EXPANDED
    COLLAPSED_W = SIDEBAR_COLLAPSED

    def __init__(self, on_navigate):
        super().__init__()
        self.on_navigate  = on_navigate
        self._buttons     = {}
        self._groups      = []
        self._active_key  = "home"
        self._is_expanded = True

        # Use min/max so animation can change width freely
        self.setMinimumWidth(self.EXPANDED_W)
        self.setMaximumWidth(self.EXPANDED_W)
        self.setStyleSheet(f"background:{C_SIDEBAR}; border:none;")
        # Important: never allow sidebar to expand beyond its set width
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 16, 10, 16)
        outer.setSpacing(0)

        # ── Brand row ─────────────────────────────────────────
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(8, 0, 0, 0)
        brand_row.setSpacing(10)

        self._brand_icon = QLabel(ICON_APP)
        self._brand_icon.setFixedSize(36, 36)
        self._brand_icon.setAlignment(Qt.AlignCenter)
        self._brand_icon.setStyleSheet(
            f"color:{C_PRIMARY}; font-size:22px; background:transparent;"
        )
        self._brand_name = QLabel("Evo Aura")
        self._brand_name.setFont(QFont(FONT_BODY, 15, QFont.Bold))
        self._brand_name.setStyleSheet("color:white; background:transparent;")

        brand_row.addWidget(self._brand_icon)
        brand_row.addWidget(self._brand_name)
        brand_row.addStretch()
        outer.addLayout(brand_row)
        outer.addSpacing(6)

        brand_sep = QFrame()
        brand_sep.setFixedHeight(1)
        brand_sep.setStyleSheet("background:#1e293b; border:none; margin:6px 0;")
        outer.addWidget(brand_sep)
        outer.addSpacing(6)

        # ── Scrollable nav ─────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent; border:none;")

        nav_widget = QWidget()
        nav_widget.setStyleSheet("background:transparent;")
        nav_lay = QVBoxLayout(nav_widget)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(2)
        nav_lay.setAlignment(Qt.AlignTop)

        for i, (section_title, items) in enumerate(NAV_ITEMS):
            group = NavGroupWidget(
                title          = section_title,
                items          = items,
                buttons_dict   = self._buttons,
                on_nav         = self._nav,
                active_key     = "home",
                start_expanded = (i == 0),   # only Dashboard expanded by default
            )
            nav_lay.addWidget(group)
            self._groups.append(group)

        scroll.setWidget(nav_widget)
        outer.addWidget(scroll, 1)

        # ── Version / bottom ───────────────────────────────────
        outer.addWidget(_divider())
        outer.addSpacing(8)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(6, 0, 6, 0)
        bottom_row.setSpacing(10)

        avatar = QLabel("✦")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background    : {C_PRIMARY}33;
            border-radius : 17px;
            font-size     : 16px;
            color         : {C_PRIMARY};
        """)
        self._ver_lbl = QLabel("Evo Aura  v1.0")
        self._ver_lbl.setFont(QFont(FONT_BODY, 9))
        self._ver_lbl.setStyleSheet("color:#475569; background:transparent;")

        bottom_row.addWidget(avatar)
        bottom_row.addWidget(self._ver_lbl)
        bottom_row.addStretch()
        outer.addLayout(bottom_row)

        QTimer.singleShot(0, lambda: self._apply_button_mode(True))

    # ── Slide toggle ──────────────────────────────────────────

    def toggle(self):
        self._is_expanded = not self._is_expanded
        target = self.EXPANDED_W if self._is_expanded else self.COLLAPSED_W

        for prop in (b"minimumWidth", b"maximumWidth"):
            anim = QPropertyAnimation(self, prop, self)
            anim.setDuration(240)
            anim.setStartValue(self.width())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QPropertyAnimation.DeleteWhenStopped)

        QTimer.singleShot(40, lambda: self._apply_button_mode(self._is_expanded))

    def _apply_button_mode(self, expanded: bool):
        self._brand_name.setVisible(expanded)
        self._ver_lbl.setVisible(expanded)
        self._brand_icon.setAlignment(
            (Qt.AlignLeft | Qt.AlignVCenter) if expanded else Qt.AlignCenter
        )
        for btn in self._buttons.values():
            btn.set_expanded(expanded)
        for grp in self._groups:
            grp.set_sidebar_expanded(expanded)

    # ── Navigation ────────────────────────────────────────────

    def _nav(self, key):
        if key in self._buttons:
            self._buttons[self._active_key].setChecked(False)
            self._active_key = key
            self._buttons[key].setChecked(True)
        self.on_navigate(key)

    def set_active(self, key):
        """Update highlight WITHOUT triggering navigation (no recursion)."""
        if key in self._buttons:
            self._buttons[self._active_key].setChecked(False)
            self._active_key = key
            self._buttons[key].setChecked(True)