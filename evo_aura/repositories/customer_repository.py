"""Customer SQL compatibility helpers."""


def init_customer_tables(db_name):
    from pages.customers.customer_center_page import init_customer_tables as _legacy_init

    return _legacy_init(db_name)
