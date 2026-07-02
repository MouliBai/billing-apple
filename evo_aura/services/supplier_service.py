"""Supplier business helpers."""


def stock_status(available, reorder_level):
    available = float(available or 0)
    reorder = float(reorder_level or 0)
    if available <= 0:
        return "Out of Stock"
    if reorder and available <= reorder:
        return "Low Stock"
    return "In Stock"
