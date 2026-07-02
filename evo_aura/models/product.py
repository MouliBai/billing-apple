"""Product model normalization helpers."""

from dataclasses import dataclass, asdict


@dataclass
class Product:
    item_code: str = ""
    name: str = ""
    category: str = ""
    sub_category: str = ""
    brand: str = ""
    size: str = ""
    color: str = ""
    current_stock: int = 0
    selling_price: float = 0.0
    status: str = "Active"

    def to_dict(self):
        return asdict(self)
