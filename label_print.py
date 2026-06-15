# "label_print.py"
"""
label_print.py  —  Evo Aura  •  Label Designer & Printer
==========================================================
PyQt6  |  Apple / EvoAura design system

Standalone Label Print module extracted from product_page.py
Provides a 2-column label designer with:
  • Paper & Layout config (width, columns, height, gap, margins, DPI)
  • Fields-to-print toggles (name, barcode, MRP, price, HSN, GST, etc.)
  • Live label preview canvas with pseudo-barcode rendering
  • QZ Tray printer connection panel
  • Preset layouts + print button

USAGE
-----
from label_print import LabelPrintWidget

# Standalone — pass a dict of product data
data = {
    "name": "Cotton Shirt", "alias": "Slim Fit", "sku": "SKU001",
    "barcode": "8901234567890", "code": "P00001", "hsn": "6205",
    "brand": "Raymond", "mrp": 1299.0, "sell": 999.0, "gst": "12%",
}
w = LabelPrintWidget(product_data=data)

# OR — bind live to a ProductFormWidget instance (reads fields dynamically)
w = LabelPrintWidget(form=product_form_widget)
"""

import sys
import hashlib

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QGridLayout, QComboBox,
    QDoubleSpinBox, QSpinBox, QApplication, QMessageBox,
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QPalette,
)
from PyQt6.QtCore import Qt, QRectF, QSizeF


# ─────────────────────────────────────────────────────────────
#  DESIGN TOKENS  —  Apple / EvoAura  (same theme)
# ─────────────────────────────────────────────────────────────
C = dict(
    bg_white      = "#FFFFFF",
    bg_light      = "#F5F5F7",
    bg_panel      = "#F2F2F7",
    bg_card       = "#FAFAFA",

    accent        = "#FA2D48",
    accent_dark   = "#C81F36",

    success       = "#27ae60",
    warning       = "#e67e22",

    text          = "#000000",
    text2         = "#6E6E73",
    text3         = "#A1A1A6",

    border        = "#D2D2D7",
    hover_bg      = "#E5E5EA",

    section_hdr   = "#1D1D1F",
    section_icon  = "#FA2D48",

    blue          = "#1A73E8",
    blue_tint     = "#EEF5FF",
    blue_dark     = "#1558B0",
)

FORM_FIELD_HEIGHT = 38

SEC_HDR_SS = f"color:{C['section_hdr']};background:transparent;font-size:13px;font-weight:700;border:none;"
LABEL_SS   = f"color:{C['text2']};background:transparent;font-weight:500;font-size:12px;border:none;"
HINT_SS    = f"color:{C['text3']};background:transparent;font-size:11px;margin-top:1px;border:none;"

_NO_ARROW = (
    "QDoubleSpinBox,QSpinBox{"
    "border:1.5px solid #d2d2d7;border-radius:8px;"
    "padding:6px 10px;font-size:13px;background:#ffffff;"
    "color:#000000;min-height:38px;max-height:38px;height:38px;}"
    "QDoubleSpinBox:hover,QSpinBox:hover{border:1.5px solid #1a73e8;}"
    "QDoubleSpinBox:focus,QSpinBox:focus{border:2px solid #FA2D48;background:#FFF8F9;}"
    "QDoubleSpinBox::up-button,QDoubleSpinBox::down-button,"
    "QSpinBox::up-button,QSpinBox::down-button{"
    "width:0;height:0;border:none;background:transparent;image:none;}"
    "QDoubleSpinBox::up-arrow,QDoubleSpinBox::down-arrow,"
    "QSpinBox::up-arrow,QSpinBox::down-arrow{width:0;height:0;image:none;}"
)

FIELD_SS = f"""
    QLabel {{ border:none; background:transparent; }}
    QLineEdit {{
        border:1.5px solid {C['border']}; border-radius:8px;
        padding:6px 10px; font-size:13px; background:#FFFFFF;
        color:#000000; min-height:34px;
    }}
    QLineEdit:hover  {{ border:1.5px solid {C['blue']}; }}
    QLineEdit:focus  {{ border:2px solid {C['accent']}; background:#FFF8F9; }}
    QComboBox {{
        border:1.5px solid {C['border']}; border-radius:8px;
        padding:6px 10px; font-size:13px; background:#FFFFFF;
        color:#000000; min-height:34px;
    }}
    QComboBox:hover {{ border:1.5px solid {C['blue']}; }}
    QComboBox:focus {{ border:2px solid {C['accent']}; background:#FFF8F9; }}
    QComboBox::drop-down {{ border:none; width:24px; }}
    QComboBox::down-arrow {{
        image:none;
        border-left:5px solid transparent;
        border-right:5px solid transparent;
        border-top:6px solid {C['text3']};
        margin-right:6px;
    }}
    QComboBox QAbstractItemView {{
        background:#FFFFFF; color:#000000;
        selection-background-color:{C['blue']};
        selection-color:#FFFFFF;
        border:1px solid {C['border']};
        border-radius:8px; padding:4px; outline:none;
    }}
    QComboBox QAbstractItemView::item {{
        color:#000000; background:#FFFFFF;
        min-height:32px; padding:4px 10px; border:none;
    }}
    QComboBox QAbstractItemView::item:hover    {{ background:{C['accent']}; color:#FFFFFF; }}
    QComboBox QAbstractItemView::item:selected {{ background:{C['blue']}; color:#FFFFFF; }}
"""


# ─────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────
def _F(sz=13, bold=False) -> QFont:
    f = QFont("SF Pro Text", sz)
    if bold:
        f.setWeight(QFont.Weight.Bold)
    return f


def make_section(title: str, icon: str = "") -> tuple:
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background:{C['bg_white']};
            border:1px solid {C['border']};
            border-radius:12px;
        }}
    """)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(20, 14, 20, 18)
    outer.setSpacing(10)

    hdr = QHBoxLayout(); hdr.setSpacing(6)
    if icon:
        ico = QLabel(icon)
        ico.setStyleSheet(f"font-size:15px;color:{C['section_icon']};background:transparent;border:none;")
        hdr.addWidget(ico)
    lbl = QLabel(title)
    lbl.setFont(_F(13, bold=True))
    lbl.setStyleSheet(SEC_HDR_SS)
    hdr.addWidget(lbl); hdr.addStretch()
    outer.addLayout(hdr)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"background:{C['border']};border:none;max-height:1px;")
    outer.addWidget(sep)

    grid = QGridLayout()
    grid.setSpacing(8)
    grid.setColumnMinimumWidth(0, 140)
    grid.setColumnMinimumWidth(1, 170)
    grid.setColumnMinimumWidth(2, 140)
    grid.setColumnMinimumWidth(3, 170)
    outer.addLayout(grid)
    return frame, grid


def _normalize_field_widget(widget):
    if isinstance(widget, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
        widget.setFixedHeight(FORM_FIELD_HEIGHT)


def add_field(grid, row, col, label, widget, hint="", span=1):
    _normalize_field_widget(widget)
    lbl = QLabel(label)
    lbl.setFont(_F(12))
    lbl.setStyleSheet(LABEL_SS)
    grid.addWidget(lbl, row, col)
    col_span = 1 + (span - 1) * 2
    if hint:
        container = QWidget(); container.setStyleSheet("background:transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0); vbox.setSpacing(2)
        vbox.addWidget(widget)
        h_lbl = QLabel(hint); h_lbl.setStyleSheet(HINT_SS)
        h_lbl.setWordWrap(True)
        vbox.addWidget(h_lbl)
        grid.addWidget(container, row, col + 1, 1, col_span)
    else:
        grid.addWidget(widget, row, col + 1, 1, col_span)


# ─────────────────────────────────────────────────────────────
#  TOGGLE SWITCH  (same as product_page.py)
# ─────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtCore import QTimer, QSize


class ToggleSwitch(QCheckBox):
    """iOS/Material-style toggle switch matching the EvoAura theme."""
    _TRACK_W  = 40
    _TRACK_H  = 20
    _KNOB_D   = 18
    _PADDING  = 1

    _OFF_TRACK  = QColor("#9A9999")
    _ON_TRACK   = QColor("#f28090")
    _OFF_KNOB   = QColor("#FFFFFF")
    _ON_KNOB    = QColor("#FA2D48")
    _LABEL_COL  = QColor("#111111")

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._anim_val = 0.0
        self._timer = None
        self._direction = 0

        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QCheckBox{spacing:10px;font-size:13px;color:#111111;"
            "background:transparent;border:none;}"
            "QCheckBox::indicator{width:0px;height:0px;}"
        )
        self.stateChanged.connect(self._on_state)

    def setChecked(self, checked):
        super().setChecked(checked)
        self._anim_val = 1.0 if checked else 0.0
        self.update()

    def _on_state(self, state):
        target = 1.0 if self.isChecked() else 0.0
        self._direction = 1 if target > self._anim_val else -1
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setInterval(12)
            self._timer.timeout.connect(self._step)
        self._timer.start()

    def _step(self):
        step = 0.08
        if self._direction > 0:
            self._anim_val = min(1.0, self._anim_val + step)
        else:
            self._anim_val = max(0.0, self._anim_val - step)
        self.update()
        target = 1.0 if self.isChecked() else 0.0
        if abs(self._anim_val - target) < 0.01:
            self._anim_val = target
            self._timer.stop()

    def sizeHint(self):
        fm = self.fontMetrics()
        txt_w = fm.horizontalAdvance(self.text()) if self.text() else 0
        spacing = 10 if self.text() else 0
        return QSize(
            self._TRACK_W + spacing + txt_w + 4,
            max(self._TRACK_H + 4, fm.height() + 4)
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        tw, th, kd, pad = self._TRACK_W, self._TRACK_H, self._KNOB_D, self._PADDING
        t = self._anim_val
        cy = self.height() / 2

        track_r = QRectF(0, cy - th / 2, tw, th)
        track_col = QColor(
            int(self._OFF_TRACK.red()   + t * (self._ON_TRACK.red()   - self._OFF_TRACK.red())),
            int(self._OFF_TRACK.green() + t * (self._ON_TRACK.green() - self._OFF_TRACK.green())),
            int(self._OFF_TRACK.blue()  + t * (self._ON_TRACK.blue()  - self._OFF_TRACK.blue())),
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_col)
        p.drawRoundedRect(track_r, th / 2, th / 2)

        travel = tw - kd - pad * 2
        knob_x = pad + t * travel
        knob_y = cy - kd / 2
        knob_r = QRectF(knob_x, knob_y, kd, kd)

        knob_col = QColor(
            int(self._OFF_KNOB.red()   + t * (self._ON_KNOB.red()   - self._OFF_KNOB.red())),
            int(self._OFF_KNOB.green() + t * (self._ON_KNOB.green() - self._OFF_KNOB.green())),
            int(self._OFF_KNOB.blue()  + t * (self._ON_KNOB.blue()  - self._OFF_KNOB.blue())),
        )
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawEllipse(knob_r.adjusted(1, 2, 1, 2))
        p.setBrush(knob_col)
        p.drawEllipse(knob_r)

        if self.text():
            p.setPen(QPen(self._LABEL_COL))
            fnt = QFont(); fnt.setPointSize(10)
            p.setFont(fnt)
            text_x = tw + 10
            p.drawText(
                QRectF(text_x, 0, self.width() - text_x, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self.text()
            )
        p.end()


# ─────────────────────────────────────────────────────────────
#  LABEL CANVAS  —  live preview with pseudo-barcode
# ─────────────────────────────────────────────────────────────
class LabelCanvas(QWidget):
    def __init__(self, designer, parent=None):
        super().__init__(parent)
        self._d = designer
        self.setMinimumHeight(260)
        self.setStyleSheet(
            "background:#e8e8ed;border:1.5px solid #c7c7cc;border-radius:8px;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        d = self._d
        paper_mm  = d._lbl_paper_mm()
        cols      = d.f_lbl_columns.value()
        gap_mm    = d.f_lbl_gap.value()
        height_mm = d.f_lbl_height.value()
        mar_l     = d.f_lbl_mar_l.value()
        mar_r     = d.f_lbl_mar_r.value()
        lbl_w_mm  = d._calc_label_width()
        ld        = d._get_label_data()

        avail_w = self.width() - 32
        avail_h = self.height() - 32
        scale   = min(avail_w / max(paper_mm, 1),
                      avail_h / max(height_mm + 6, 1))
        scale   = min(scale, 6.0)

        total_w_px = paper_mm * scale
        ox = (self.width()  - total_w_px) / 2
        oy = (self.height() - height_mm * scale) / 2

        # Paper shadow
        p.fillRect(int(ox + 3), int(oy + 3),
                   int(total_w_px), int(height_mm * scale),
                   QColor(0, 0, 0, 30))
        # Paper
        p.fillRect(int(ox), int(oy),
                   int(total_w_px), int(height_mm * scale),
                   QColor("#ffffff"))
        p.setPen(QPen(QColor("#999999"), 1))
        p.drawRect(int(ox), int(oy),
                   int(total_w_px), int(height_mm * scale))

        for col in range(cols):
            x_start_mm = mar_l + col * (lbl_w_mm + gap_mm)
            lx = ox + x_start_mm * scale
            ly = oy
            lw = lbl_w_mm * scale
            lh = height_mm * scale

            if cols > 1 and col < cols - 1:
                cut_x = int(lx + lw + gap_mm * scale / 2)
                pen_dash = QPen(QColor("#aaaaaa"), 1, Qt.PenStyle.DashLine)
                p.setPen(pen_dash)
                p.drawLine(cut_x, int(oy), cut_x, int(oy + lh))

            # Build field list with real data
            fields = []
            if d.f_lbl_show_name.isChecked():
                fields.append(("name",    ld["name"],                   True,  "normal"))
            if d.f_lbl_show_alias.isChecked() and ld["alias"]:
                fields.append(("alias",   ld["alias"],                  False, "normal"))
            if d.f_lbl_show_barcode.isChecked():
                fields.append(("barcode", ld["barcode"],                False, "barcode"))
            if d.f_lbl_show_mrp.isChecked():
                fields.append(("mrp",     f"MRP ₹{ld['mrp']:.2f}",      True,  "price"))
            if d.f_lbl_show_price.isChecked():
                fields.append(("price",   f"Price ₹{ld['sell']:.2f}",   False, "price2"))
            if d.f_lbl_show_mrp_lbl.isChecked():
                fields.append(("mrplbl",  "Maximum Retail Price",       False, "small"))
            if d.f_lbl_show_hsn.isChecked() and ld["hsn"]:
                fields.append(("hsn",     f"HSN: {ld['hsn']}",          False, "small"))
            if d.f_lbl_show_gst.isChecked():
                fields.append(("gst",     f"GST: {ld['gst']}",          False, "small"))
            if d.f_lbl_show_brand.isChecked() and ld["brand"]:
                fields.append(("brand",   ld["brand"],                  False, "small"))
            if d.f_lbl_show_itemcode.isChecked() and ld["code"]:
                fields.append(("code",    f"Code: {ld['code']}",        False, "small"))

            if not fields:
                fields.append(("empty", "No fields selected", False, "normal"))

            bc_fields  = [f for f in fields if f[3] == "barcode"]
            txt_fields = [f for f in fields if f[3] != "barcode"]

            pad = 3 * scale / 3
            inner_x = lx + pad
            inner_w = lw - pad * 2

            if bc_fields:
                bc_h   = lh * 0.45
                txt_h  = lh * 0.55
                txt_y0 = ly + bc_h
                bc_y0  = ly

                bc_val = bc_fields[0][1]
                bar_margin = 4
                bx0 = int(inner_x + bar_margin)
                bx1 = int(inner_x + inner_w - bar_margin)
                bar_area_w = bx1 - bx0
                bar_top    = int(bc_y0 + 3)
                bar_bot    = int(bc_y0 + bc_h * 0.72)
                bar_h_px   = bar_bot - bar_top

                if bar_area_w > 4 and bar_h_px > 2:
                    seed = int(hashlib.md5(bc_val.encode()).hexdigest()[:8], 16)
                    bx = bx0
                    unit = max(1, bar_area_w // 60)
                    phase = seed
                    p.setPen(Qt.PenStyle.NoPen)
                    while bx < bx1 - unit:
                        phase = (phase * 1103515245 + 12345) & 0x7fffffff
                        is_bar = (phase >> 15) % 3 != 0
                        bw = unit * (1 + (phase >> 20) % 2)
                        bw = min(bw, bx1 - bx)
                        if is_bar:
                            p.fillRect(bx, bar_top, bw, bar_h_px, QColor("#1a1a1a"))
                        bx += bw + 1

                    p.fillRect(bx0,          bar_top, unit, bar_h_px, QColor("#000000"))
                    p.fillRect(bx0 + unit + 1, bar_top, unit, bar_h_px, QColor("#000000"))
                    p.fillRect(bx1 - unit * 2, bar_top, unit, bar_h_px, QColor("#000000"))
                    p.fillRect(bx1 - unit,   bar_top, unit, bar_h_px, QColor("#000000"))

                fnt_bc = QFont("Courier New")
                fnt_bc.setPixelSize(max(int(bc_h * 0.20), 6))
                p.setFont(fnt_bc)
                p.setPen(QPen(QColor("#1a1a1a"), 1))
                p.drawText(
                    QRectF(inner_x, bc_y0 + bc_h * 0.72, inner_w, bc_h * 0.28),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                    bc_val
                )
            else:
                txt_y0 = ly
                txt_h  = lh

            if txt_fields:
                rh = txt_h / len(txt_fields)
                for ti, (ftype, txt, bold, style) in enumerate(txt_fields):
                    ty = txt_y0 + ti * rh
                    fnt = QFont()
                    fnt.setBold(bold)
                    if style == "price":
                        fnt.setPixelSize(max(int(rh * 0.62), 8))
                        p.setPen(QPen(QColor("#c0392b"), 1))
                        fnt.setBold(True)
                    elif style == "price2":
                        fnt.setPixelSize(max(int(rh * 0.55), 8))
                        p.setPen(QPen(QColor("#1a6fa8"), 1))
                        fnt.setBold(True)
                    elif style == "name":
                        fnt.setPixelSize(max(int(rh * 0.54), 8))
                        p.setPen(QPen(QColor("#111111"), 1))
                    elif style == "small":
                        fnt.setPixelSize(max(int(rh * 0.42), 6))
                        p.setPen(QPen(QColor("#555555"), 1))
                    else:
                        fnt.setPixelSize(max(int(rh * 0.48), 7))
                        p.setPen(QPen(QColor("#222222"), 1))
                    p.setFont(fnt)
                    p.drawText(
                        QRectF(inner_x, ty, inner_w, rh),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        txt
                    )
        p.end()


# ─────────────────────────────────────────────────────────────
#  LABEL PRINT WIDGET  —  full designer + preview + print
# ─────────────────────────────────────────────────────────────
class LabelPrintWidget(QWidget):
    """
    Standalone Label Designer / Printer.

    Parameters
    ----------
    product_data : dict | None
        Static product data used for the preview. Keys:
        name, alias, sku, barcode, code, hsn, brand, mrp, sell, gst
    form : object | None
        Optional ProductFormWidget-like object. If provided, label data is
        read *live* from its fields (f_name, f_mrp, f_gst_rate, …).
    """

    def __init__(self, product_data=None, form=None, parent=None):
        super().__init__(parent)
        self._static_data = product_data or {}
        self._form        = form

        self.setStyleSheet(f"background:{C['bg_light']};" + FIELD_SS)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self._build()

    # ── label geometry helpers ───────────────────────────
    def _mm_to_px(self, mm, dpi=96):
        return mm * dpi / 25.4

    def _lbl_paper_mm(self):
        txt = self.f_lbl_paper.currentText()
        return {"1 inch (25.4 mm)": 25.4, "2 inch (50.8 mm)": 50.8,
                "3 inch (76.2 mm)": 76.2, "4 inch (101.6 mm)": 101.6}.get(txt, 76.2)

    def _calc_label_width(self):
        paper_mm  = self._lbl_paper_mm()
        cols      = self.f_lbl_columns.value()
        gap_mm    = self.f_lbl_gap.value()
        mar_l     = self.f_lbl_mar_l.value()
        mar_r     = self.f_lbl_mar_r.value()
        total_gap = gap_mm * (cols - 1)
        usable    = paper_mm - mar_l - mar_r - total_gap
        return round(usable / cols, 2) if cols > 0 else usable

    def _get_label_data(self):
        """Read live from form if bound, else use static data."""
        if self._form is not None:
            f = self._form
            return {
                "name":    f.f_name.text().strip()     or "Product Name",
                "alias":   f.f_alias.text().strip()    or "",
                "sku":     f.f_sku.text().strip()      or "",
                "barcode": (f.f_barcode.text().strip()
                            or f.f_sku.text().strip() or "000000000000"),
                "code":    f.f_item_code.text().strip() or "",
                "hsn":     f.f_hsn.text().strip()      or "",
                "brand":   f.f_brand.text().strip()    or "",
                "mrp":     f.f_mrp.value(),
                "sell":    f.f_selling_price.value(),
                "gst":     f.f_gst_rate.currentText(),
            }
        d = self._static_data
        return {
            "name":    d.get("name")    or "Product Name",
            "alias":   d.get("alias")   or "",
            "sku":     d.get("sku")     or "",
            "barcode": d.get("barcode") or d.get("sku") or "000000000000",
            "code":    d.get("code")    or "",
            "hsn":     d.get("hsn")     or "",
            "brand":   d.get("brand")   or "",
            "mrp":     float(d.get("mrp", 0) or 0),
            "sell":    float(d.get("sell", 0) or 0),
            "gst":     d.get("gst")     or "0%",
        }

    def _refresh_label_preview(self):
        self._lbl_canvas.update()
        lw = self._calc_label_width()
        lh = self.f_lbl_height.value()
        cols = self.f_lbl_columns.value()
        paper_mm = self._lbl_paper_mm()
        self._lbl_info.setText(
            f"Label: {lw:.1f} x {lh:.1f} mm  │  "
            f"{cols} col  │  Paper: {paper_mm:.1f} mm wide"
        )

    # ── build UI ──────────────────────────────────────────
    def _build(self):
        master = QHBoxLayout()
        master.setContentsMargins(0, 0, 0, 0)
        master.setSpacing(14)

        left_w  = QWidget(); left_w.setStyleSheet("background:transparent;")
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0); left_lay.setSpacing(12)

        right_w  = QWidget(); right_w.setStyleSheet("background:transparent;")
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(0, 0, 0, 0); right_lay.setSpacing(8)

        master.addWidget(left_w, 1)
        master.addWidget(right_w, 1)

        # ── Section 1: Paper & Layout ─────────────────────
        sec, g = make_section("Paper & Layout", "📰")
        g.setHorizontalSpacing(12); g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)

        self.f_lbl_paper = QComboBox()
        self.f_lbl_paper.addItems([
            "1 inch (25.4 mm)", "2 inch (50.8 mm)",
            "3 inch (76.2 mm)", "4 inch (101.6 mm)"
        ])
        self.f_lbl_paper.setCurrentText("3 inch (76.2 mm)")

        self.f_lbl_columns = QSpinBox()
        self.f_lbl_columns.setFixedHeight(38)
        self.f_lbl_columns.setStyleSheet(_NO_ARROW)
        self.f_lbl_columns.setRange(1, 3); self.f_lbl_columns.setValue(2)

        self.f_lbl_height = QDoubleSpinBox()
        self.f_lbl_height.setFixedHeight(38)
        self.f_lbl_height.setStyleSheet(_NO_ARROW)
        self.f_lbl_height.setRange(5, 200); self.f_lbl_height.setValue(25)
        self.f_lbl_height.setSuffix(" mm")

        self.f_lbl_gap = QDoubleSpinBox()
        self.f_lbl_gap.setFixedHeight(38)
        self.f_lbl_gap.setStyleSheet(_NO_ARROW)
        self.f_lbl_gap.setRange(0, 10); self.f_lbl_gap.setValue(3)
        self.f_lbl_gap.setSuffix(" mm")

        self.f_lbl_mar_l = QDoubleSpinBox()
        self.f_lbl_mar_l.setFixedHeight(38)
        self.f_lbl_mar_l.setStyleSheet(_NO_ARROW)
        self.f_lbl_mar_l.setRange(0, 10); self.f_lbl_mar_l.setValue(1)
        self.f_lbl_mar_l.setSuffix(" mm")

        self.f_lbl_mar_r = QDoubleSpinBox()
        self.f_lbl_mar_r.setFixedHeight(38)
        self.f_lbl_mar_r.setStyleSheet(_NO_ARROW)
        self.f_lbl_mar_r.setRange(0, 10); self.f_lbl_mar_r.setValue(1)
        self.f_lbl_mar_r.setSuffix(" mm")

        self.f_lbl_dpi = QComboBox()
        self.f_lbl_dpi.addItems(["203 DPI", "300 DPI", "600 DPI"])

        r = 0
        add_field(g, r, 0, "Paper Width",  self.f_lbl_paper)
        add_field(g, r, 2, "Columns",      self.f_lbl_columns)
        r += 1
        add_field(g, r, 0, "Label Height", self.f_lbl_height)
        add_field(g, r, 2, "Gap between labels", self.f_lbl_gap)
        r += 1
        add_field(g, r, 0, "Margin Left",  self.f_lbl_mar_l)
        add_field(g, r, 2, "Margin Right", self.f_lbl_mar_r)
        r += 1
        add_field(g, r, 0, "Printer DPI",  self.f_lbl_dpi)
        left_lay.addWidget(sec)

        # ── Section 2: Fields to Print ────────────────────
        sec2, g2 = make_section("Fields to Print", "📋")
        g2.setHorizontalSpacing(16); g2.setVerticalSpacing(8)

        self.f_lbl_show_name     = ToggleSwitch("Product Name");  self.f_lbl_show_name.setChecked(True)
        self.f_lbl_show_barcode  = ToggleSwitch("Barcode");       self.f_lbl_show_barcode.setChecked(True)
        self.f_lbl_show_mrp      = ToggleSwitch("MRP");           self.f_lbl_show_mrp.setChecked(True)
        self.f_lbl_show_price    = ToggleSwitch("Selling Price"); self.f_lbl_show_price.setChecked(False)
        self.f_lbl_show_mrp_lbl  = ToggleSwitch("MRP Label text")
        self.f_lbl_show_hsn      = ToggleSwitch("HSN Code")
        self.f_lbl_show_alias    = ToggleSwitch("Alias Name")
        self.f_lbl_show_itemcode = ToggleSwitch("Item Code")
        self.f_lbl_show_gst      = ToggleSwitch("GST%")
        self.f_lbl_show_brand    = ToggleSwitch("Brand")

        chks = [
            self.f_lbl_show_name,    self.f_lbl_show_barcode,
            self.f_lbl_show_mrp,     self.f_lbl_show_price,
            self.f_lbl_show_mrp_lbl, self.f_lbl_show_hsn,
            self.f_lbl_show_alias,   self.f_lbl_show_itemcode,
            self.f_lbl_show_gst,     self.f_lbl_show_brand,
        ]
        for i, chk in enumerate(chks):
            g2.addWidget(chk, i // 2, i % 2)
        left_lay.addWidget(sec2)

        # ── Static editable fields (only when NOT bound to form) ──
        if self._form is None:
            sec3, g3 = make_section("Product Data", "🏷️")
            g3.setHorizontalSpacing(12); g3.setVerticalSpacing(10)
            g3.setColumnStretch(1, 1); g3.setColumnStretch(3, 1)

            d = self._static_data
            self.f_name        = QLineEdit(d.get("name", ""))
            self.f_alias       = QLineEdit(d.get("alias", ""))
            self.f_sku         = QLineEdit(d.get("sku", ""))
            self.f_barcode     = QLineEdit(d.get("barcode", ""))
            self.f_item_code   = QLineEdit(d.get("code", ""))
            self.f_hsn         = QLineEdit(d.get("hsn", ""))
            self.f_brand       = QLineEdit(d.get("brand", ""))

            self.f_mrp = QDoubleSpinBox()
            self.f_mrp.setRange(0, 9999999); self.f_mrp.setDecimals(2)
            self.f_mrp.setPrefix("₹ "); self.f_mrp.setFixedHeight(38)
            self.f_mrp.setStyleSheet(_NO_ARROW)
            self.f_mrp.setValue(float(d.get("mrp", 0) or 0))

            self.f_selling_price = QDoubleSpinBox()
            self.f_selling_price.setRange(0, 9999999); self.f_selling_price.setDecimals(2)
            self.f_selling_price.setPrefix("₹ "); self.f_selling_price.setFixedHeight(38)
            self.f_selling_price.setStyleSheet(_NO_ARROW)
            self.f_selling_price.setValue(float(d.get("sell", 0) or 0))

            self.f_gst_rate = QComboBox()
            self.f_gst_rate.addItems(["0%", "5%", "12%", "18%", "28%"])
            if d.get("gst") in ("0%", "5%", "12%", "18%", "28%"):
                self.f_gst_rate.setCurrentText(d["gst"])

            rr = 0
            add_field(g3, rr, 0, "Product Name", self.f_name)
            add_field(g3, rr, 2, "Alias", self.f_alias); rr += 1
            add_field(g3, rr, 0, "SKU", self.f_sku)
            add_field(g3, rr, 2, "Barcode", self.f_barcode); rr += 1
            add_field(g3, rr, 0, "Item Code", self.f_item_code)
            add_field(g3, rr, 2, "HSN Code", self.f_hsn); rr += 1
            add_field(g3, rr, 0, "Brand", self.f_brand)
            add_field(g3, rr, 2, "GST Rate", self.f_gst_rate); rr += 1
            add_field(g3, rr, 0, "MRP", self.f_mrp)
            add_field(g3, rr, 2, "Selling Price", self.f_selling_price)
            left_lay.addWidget(sec3)

            for fw in (self.f_name, self.f_alias, self.f_sku, self.f_barcode,
                       self.f_item_code, self.f_hsn, self.f_brand):
                fw.textChanged.connect(self._refresh_label_preview)
            self.f_mrp.valueChanged.connect(self._refresh_label_preview)
            self.f_selling_price.valueChanged.connect(self._refresh_label_preview)
            self.f_gst_rate.currentTextChanged.connect(self._refresh_label_preview)

        left_lay.addStretch()

        # ════════════════════════════════════════════════════
        # RIGHT PANEL — QZ Tray + Preview + Print
        # ════════════════════════════════════════════════════
        qz_frame = QFrame()
        qz_frame.setStyleSheet(
            "QFrame{background:#f5f5f7;border:1px solid #d2d2d7;border-radius:10px;}")
        qz_lay = QVBoxLayout(qz_frame)
        qz_lay.setContentsMargins(14, 10, 14, 10); qz_lay.setSpacing(8)

        qz_title_row = QHBoxLayout()
        qz_icon = QLabel("🖨️  QZ Tray")
        qz_icon.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['section_hdr']};"
            f"background:transparent;border:none;")
        self._qz_status = QLabel("●  Not connected")
        self._qz_status.setStyleSheet(
            "font-size:11px;font-weight:600;color:#8e8e93;background:transparent;border:none;")
        qz_title_row.addWidget(qz_icon); qz_title_row.addStretch()
        qz_title_row.addWidget(self._qz_status)
        qz_lay.addLayout(qz_title_row)

        qz_row2 = QHBoxLayout(); qz_row2.setSpacing(8)
        self.f_lbl_printer = QComboBox()
        self.f_lbl_printer.addItems(["-- Select Printer --"])
        self.f_lbl_printer.setFixedHeight(32)
        self.f_lbl_printer.setStyleSheet(
            f"background:#ffffff;border:1px solid {C['border']};border-radius:6px;"
            f"font-size:12px;padding:0 8px;")

        _btn_refresh = QPushButton("↻  Refresh")
        _btn_refresh.setFixedSize(88, 32)
        _btn_refresh.setStyleSheet(
            f"background:#ffffff;color:{C['text']};border:1px solid {C['border']};"
            f"border-radius:6px;font-size:12px;font-weight:600;")

        _btn_connect = QPushButton("Connect")
        _btn_connect.setFixedSize(80, 32)
        _btn_connect.setStyleSheet(
            f"background:{C['blue']};color:white;border:none;"
            f"border-radius:6px;font-size:12px;font-weight:600;")

        qz_row2.addWidget(self.f_lbl_printer, 1)
        qz_row2.addWidget(_btn_refresh)
        qz_row2.addWidget(_btn_connect)
        qz_lay.addLayout(qz_row2)

        _qz_hint = QLabel(
            "QZ Tray enables direct printing to thermal / barcode printers. "
            "Download at qz.io and keep it running.")
        _qz_hint.setWordWrap(True)
        _qz_hint.setStyleSheet(
            f"font-size:10px;color:{C['text3']};background:transparent;border:none;")
        qz_lay.addWidget(_qz_hint)
        right_lay.addWidget(qz_frame)

        def refresh_printers():
            try:
                from PyQt6.QtPrintSupport import QPrinterInfo
                printers = [p.printerName() for p in QPrinterInfo.availablePrinters()]
            except Exception:
                printers = []
            self.f_lbl_printer.clear()
            if printers:
                self.f_lbl_printer.addItems(printers)
                self._qz_status.setText("●  Printers found")
                self._qz_status.setStyleSheet(
                    "font-size:11px;font-weight:600;color:#30a14e;background:transparent;border:none;")
            else:
                self.f_lbl_printer.addItems(["-- No printers found --"])
                self._qz_status.setText("●  No printers")
                self._qz_status.setStyleSheet(
                    "font-size:11px;font-weight:600;color:#e3b341;background:transparent;border:none;")

        def connect_printer():
            refresh_printers()
            pname = self.f_lbl_printer.currentText()
            if pname and "No printer" not in pname and "Select" not in pname:
                self._qz_status.setText(f"●  {pname}")
                self._qz_status.setStyleSheet(
                    "font-size:11px;font-weight:600;color:#30a14e;background:transparent;border:none;")

        _btn_refresh.clicked.connect(refresh_printers)
        _btn_connect.clicked.connect(connect_printer)

        # ── Preview title + info ───────────────────────────
        _prev_title = QLabel("🏷️  Label Preview")
        _prev_title.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{C['section_hdr']};"
            f"background:transparent;border:none;")
        right_lay.addWidget(_prev_title)

        self._lbl_info = QLabel("")
        self._lbl_info.setStyleSheet(
            f"font-size:11px;color:{C['text3']};background:transparent;border:none;")
        right_lay.addWidget(self._lbl_info)

        # ── Canvas ────────────────────────────────────────
        self._lbl_canvas = LabelCanvas(self, right_w)
        right_lay.addWidget(self._lbl_canvas, 1)

        # ── Preset row ────────────────────────────────────
        preset_row = QHBoxLayout(); preset_row.setSpacing(8)
        _preset_lbl = QLabel("Preset:")
        _preset_lbl.setStyleSheet(
            f"font-size:12px;color:{C['text2']};background:transparent;border:none;")
        self._lbl_preset = QComboBox()
        self._lbl_preset.addItems([
            "3in 2-col 36x25 mm", "4in 2-col 50x25 mm",
            "4in 3-col 34x25 mm", "2in 1-col 50x25 mm",
            "4in 1-col 100x25 mm",
        ])
        self._lbl_preset.setFixedHeight(30)
        _apply_preset = QPushButton("Apply")
        _apply_preset.setFixedSize(60, 30)
        _apply_preset.setStyleSheet(
            f"background:{C['accent']};color:white;border:none;border-radius:6px;"
            f"font-size:12px;font-weight:600;")
        preset_row.addWidget(_preset_lbl)
        preset_row.addWidget(self._lbl_preset, 1)
        preset_row.addWidget(_apply_preset)
        right_lay.addLayout(preset_row)

        def apply_preset():
            presets = {
                "3in 2-col 36x25 mm":  ("3 inch (76.2 mm)",  2, 25.0, 3.0),
                "4in 2-col 50x25 mm":  ("4 inch (101.6 mm)", 2, 25.0, 3.0),
                "4in 3-col 34x25 mm":  ("4 inch (101.6 mm)", 3, 25.0, 2.0),
                "2in 1-col 50x25 mm":  ("2 inch (50.8 mm)",  1, 25.0, 0.0),
                "4in 1-col 100x25 mm": ("4 inch (101.6 mm)", 1, 25.0, 0.0),
            }
            sel = self._lbl_preset.currentText()
            if sel in presets:
                paper, cols, h, gap = presets[sel]
                self.f_lbl_paper.setCurrentText(paper)
                self.f_lbl_columns.setValue(cols)
                self.f_lbl_height.setValue(h)
                self.f_lbl_gap.setValue(gap)
            self._refresh_label_preview()

        _apply_preset.clicked.connect(apply_preset)

        # ── Print button ──────────────────────────────────
        _btn_print = QPushButton("🖨️  Print Label")
        _btn_print.setFixedHeight(40)
        _btn_print.setStyleSheet(f"""
            QPushButton {{
                background: {C['accent']};
                color: white; border: none; border-radius: 10px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover  {{ background: {C['accent_dark']}; }}
            QPushButton:pressed {{ opacity: 0.85; }}
        """)
        right_lay.addWidget(_btn_print)
        _btn_print.clicked.connect(self._do_print)

        # ── Wire signals ──────────────────────────────────
        for w in (self.f_lbl_paper, self.f_lbl_columns, self.f_lbl_height,
                  self.f_lbl_gap, self.f_lbl_mar_l, self.f_lbl_mar_r):
            if isinstance(w, QComboBox):
                w.currentTextChanged.connect(self._refresh_label_preview)
            else:
                w.valueChanged.connect(self._refresh_label_preview)
        for chk in chks:
            chk.stateChanged.connect(self._refresh_label_preview)

        # If bound to a form, refresh whenever its fields change
        if self._form is not None:
            f = self._form
            for fw in (f.f_name, f.f_sku, f.f_barcode,
                       f.f_item_code, f.f_hsn, f.f_brand, f.f_alias):
                fw.textChanged.connect(self._refresh_label_preview)
            f.f_mrp.valueChanged.connect(self._refresh_label_preview)
            f.f_selling_price.valueChanged.connect(self._refresh_label_preview)
            f.f_gst_rate.currentTextChanged.connect(self._refresh_label_preview)

        self.layout().addLayout(master)
        self._refresh_label_preview()

    # ── Print ─────────────────────────────────────────────
    def _do_print(self):
        pname = self.f_lbl_printer.currentText()
        if not pname or "No printer" in pname or "Select" in pname:
            QMessageBox.warning(self, "No Printer",
                "Please connect a printer first using the QZ Tray panel above.")
            return
        try:
            from PyQt6.QtPrintSupport import QPrinter
            from PyQt6.QtGui import QFont as PFont, QColor as QC2
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPrinterName(pname)
            lw_mm = self._calc_label_width()
            lh_mm = self.f_lbl_height.value()
            printer.setPageSize(QPrinter.PageSize.Custom)
            printer.setPageSizeMM(QSizeF(lw_mm, lh_mm))
            printer.setFullPage(True)
            p2 = QPainter()
            p2.begin(printer)
            scale = printer.resolution() / 25.4
            ld = self._get_label_data()
            fnt = PFont(); fnt.setBold(True)
            fnt.setPixelSize(max(int(lh_mm * scale * 0.3), 10))
            p2.setFont(fnt)
            p2.drawText(5, int(lh_mm * scale * 0.4), ld["name"])
            fnt2 = PFont(); fnt2.setBold(True)
            fnt2.setPixelSize(max(int(lh_mm * scale * 0.28), 8))
            p2.setFont(fnt2)
            p2.setPen(QC2("#c0392b"))
            p2.drawText(5, int(lh_mm * scale * 0.75), f"MRP ₹{ld['mrp']:.2f}")
            p2.end()
            QMessageBox.information(self, "Print", "Label sent to printer.")
        except Exception as ex:
            QMessageBox.information(self, "Print", str(ex))


# ─────────────────────────────────────────────────────────────
#  STANDALONE TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    sample = {
        "name":    "Premium Cotton Formal Shirt",
        "alias":   "Slim Fit White",
        "sku":     "SKU-SHIRT-001",
        "barcode": "8901234567890",
        "code":    "P00001",
        "hsn":     "6205",
        "brand":   "Raymond",
        "mrp":     1299.0,
        "sell":    999.0,
        "gst":     "12%",
    }

    win = LabelPrintWidget(product_data=sample)
    win.setWindowTitle("Evo Aura — Label Print")
    win.resize(1100, 720)
    win.show()
    sys.exit(app.exec())