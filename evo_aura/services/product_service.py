"""Product business helpers kept outside UI classes."""


def calculate_profit(selling_price, actual_cost):
    selling = float(selling_price or 0)
    cost = float(actual_cost or 0)
    profit = selling - cost
    margin = (profit / selling * 100) if selling else 0
    markup = (profit / cost * 100) if cost else 0
    return {"profit": profit, "margin": margin, "markup": markup}
