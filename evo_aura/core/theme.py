"""Shared EvoAura PyQt6 theme constants.

This module is intentionally lightweight. Non-product pages import styles from
here instead of importing the very large product page just to access colors or
field styles.
"""

C = dict(
    bg_white="#FFFFFF",
    bg_light="#F5F5F7",
    bg_panel="#F2F2F7",
    bg_card="#FAFAFA",
    input_bg="#FFFFFF",
    border="#D2D2D7",
    hover_bg="#E5E5EA",
    text="#1D1D1F",
    text2="#6E6E73",
    text3="#A1A1A6",
    accent="#FA2D48",
    accent_dark="#C81F36",
    accent_tint="rgba(250,45,72,0.08)",
    accent_tint2="rgba(250,45,72,0.10)",
    accent_tint3="rgba(250,45,72,0.04)",
    accent_border="rgba(250,45,72,0.22)",
    accent_border2="rgba(250,45,72,0.25)",
    accent_border3="rgba(250,45,72,0.26)",
    success="#27AE60",
    success_dark="#1E8449",
    warning="#E67E22",
    warning_dark="#CA6F1E",
    danger="#E53935",
    blue="#1A73E8",
    blue_tint="rgba(41,128,185,0.08)",
    blue_border="rgba(41,128,185,0.22)",
    section_hdr="#1D1D1F",
)

APP_SS = f"""
QWidget     {{ background:transparent; color:{C['text']};
              font-family:'-apple-system','Segoe UI',Arial,sans-serif; font-size:13px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{
    background:{C['bg_light']}; width:5px; border-radius:2px;
}}
QScrollBar::handle:vertical {{
    background:{C['text3']}; border-radius:2px; min-height:20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
"""

FIELD_SS = f"""
    QLabel {{
        color:{C['text2']}; background:transparent; font-weight:500;
        font-size:12px; border:none;
    }}
    QLineEdit,QComboBox,QDateEdit,QDoubleSpinBox,QSpinBox,QTextEdit {{
        background:{C['input_bg']}; border:2px solid {C['border']};
        border-radius:9px; padding:8px 10px; color:{C['text']};
        font-size:13px; selection-background-color:{C['accent']};
        selection-color:white;
    }}
    QLineEdit:focus,QComboBox:focus,QDateEdit:focus,
    QDoubleSpinBox:focus,QSpinBox:focus,QTextEdit:focus {{
        border-color:{C['accent']};
    }}
    QComboBox::drop-down,QDateEdit::drop-down {{
        border:none; width:22px;
    }}
"""

LABEL_SS = (
    f"color:{C['text2']};background:transparent;font-weight:500;"
    "font-size:12px;border:none;"
)
HINT_SS = (
    f"color:{C['text3']};background:transparent;font-size:11px;"
    "margin-top:1px;border:none;"
)
SEC_HDR_SS = (
    f"color:{C['section_hdr']};background:transparent;font-size:13px;"
    "font-weight:700;border:none;"
)

TAB_SS = f"""
QTabWidget::pane {{ border:1px solid {C['border']}; border-radius:10px; }}
QTabBar::tab {{ padding:9px 14px; background:{C['bg_panel']};
    color:{C['text2']}; border:1px solid {C['border']}; }}
QTabBar::tab:selected {{ background:{C['accent']}; color:white; font-weight:700; }}
"""
