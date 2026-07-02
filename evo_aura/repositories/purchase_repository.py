"""Purchase SQL compatibility helpers."""


def init_purchase_tables(db_name):
    from pages.inventory.purchase_invoices_page import init_purchase_tables as _legacy_init

    return _legacy_init(db_name)
