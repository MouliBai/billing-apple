"""Product constants kept outside the heavy product UI module."""

GST_RATES = [0, 5, 12, 18, 28]
TAX_TYPES = ["CGST+SGST", "IGST"]

SIZE_OPTIONS = [
    "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL",
    "28", "30", "32", "34", "36", "38", "40", "42", "44",
]

CATEGORY_SUBCATEGORIES = {
    "Shirts": [
        "Formal Shirt", "Casual Shirt", "Printed Shirt", "Checked Shirt",
        "Striped Shirt", "Plain Shirt", "Linen Shirt", "Denim Shirt",
        "Party Wear Shirt", "Full Sleeve Shirt", "Half Sleeve Shirt",
        "Mandarin Collar Shirt",
    ],
    "T-Shirts": [
        "Round Neck T-Shirt", "V-Neck T-Shirt", "Graphic T-Shirt",
        "Printed T-Shirt", "Solid T-Shirt", "Oversized T-Shirt",
        "Athletic T-Shirt",
    ],
    "Polo T-Shirts": ["Solid Polo", "Striped Polo", "Printed Polo", "Premium Polo", "Sports Polo"],
    "Jeans": ["Slim Fit Jeans", "Regular Fit Jeans", "Skinny Jeans", "Relaxed Fit Jeans", "Stretch Jeans", "Distressed Jeans"],
    "Trousers": ["Formal Trousers", "Casual Trousers", "Stretch Trousers", "Pleated Trousers", "Flat Front Trousers"],
    "Formal Pants": ["Office Pants", "Business Pants", "Slim Fit Formal Pants", "Regular Fit Formal Pants"],
    "Chinos": ["Slim Fit Chinos", "Regular Fit Chinos", "Stretch Chinos", "Casual Chinos"],
    "Shorts": ["Casual Shorts", "Denim Shorts", "Cotton Shorts", "Cargo Shorts", "Sports Shorts"],
    "Blazers": ["Single Breasted Blazer", "Double Breasted Blazer", "Casual Blazer", "Formal Blazer"],
    "Suits": ["2-Piece Suit", "3-Piece Suit", "Wedding Suit", "Business Suit", "Party Suit"],
    "Jackets": ["Denim Jacket", "Bomber Jacket", "Leather Jacket", "Casual Jacket", "Winter Jacket"],
    "Hoodies": ["Pullover Hoodie", "Zip Hoodie", "Graphic Hoodie", "Oversized Hoodie"],
    "Sweatshirts": ["Crew Neck Sweatshirt", "Printed Sweatshirt", "Oversized Sweatshirt", "Fleece Sweatshirt"],
    "Kurta": ["Cotton Kurta", "Linen Kurta", "Printed Kurta", "Festive Kurta", "Short Kurta"],
    "Innerwear": ["Vest", "Briefs", "Trunks", "Boxer Shorts", "Thermal Wear"],
    "Accessories": ["Belt", "Wallet", "Cap", "Socks", "Tie", "Bow Tie", "Handkerchief", "Suspenders"],
}
