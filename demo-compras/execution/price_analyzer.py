#!/usr/bin/env python3
"""
Price Analyzer - Deterministic price comparison logic

This script handles the deterministic parts of price analysis:
- Calculating totals
- Sorting by criteria
- Determining best options
"""

from typing import TypedDict, Optional


class Supplier(TypedDict):
    name: str
    unit_price: float
    total_price: float
    delivery_days: int
    min_order: int
    shipping_cost: float
    in_stock: bool


def calculate_total_cost(unit_price: float, quantity: int, shipping_cost: float) -> float:
    """Calculate total cost including shipping."""
    return round(unit_price * quantity + shipping_cost, 2)


def get_effective_price(supplier: dict) -> float:
    """Get comparable price, using range midpoint when available."""
    if supplier.get("price_range"):
        pr = supplier["price_range"]
        if isinstance(pr, dict) and "low" in pr and "high" in pr:
            return (pr["low"] + pr["high"]) / 2
    return supplier.get("total_price") or supplier.get("unit_price") or float('inf')


def find_best_price(suppliers: list[Supplier]) -> Optional[str]:
    """Find supplier with lowest total price (in stock only)."""
    in_stock = [s for s in suppliers if s["in_stock"]]
    if not in_stock:
        return None
    return min(in_stock, key=get_effective_price)["name"]


def find_fastest_delivery(suppliers: list[Supplier]) -> Optional[str]:
    """Find supplier with fastest delivery (in stock only)."""
    in_stock = [s for s in suppliers if s["in_stock"]]
    if not in_stock:
        return None
    return min(in_stock, key=lambda s: s["delivery_days"])["name"]


def find_best_value(suppliers: list[Supplier], urgency: str = "normal") -> Optional[str]:
    """
    Find best value considering price and delivery time.
    Score = total_price + (delivery_days * day_penalty)
    Lower is better. Urgent orders penalize slow delivery more heavily.
    """
    in_stock = [s for s in suppliers if s["in_stock"]]
    if not in_stock:
        return None

    # Urgent orders weight delivery time much more heavily
    if urgency in ("urgent", "very_urgent"):
        day_penalty = 15
        slow_threshold = 2  # penalize >2 days extra
    else:
        day_penalty = 5
        slow_threshold = None

    def value_score(s: Supplier) -> float:
        score = get_effective_price(s) + (s["delivery_days"] * day_penalty)
        if slow_threshold and s["delivery_days"] > slow_threshold:
            score += (s["delivery_days"] - slow_threshold) * 10
        return score

    return min(in_stock, key=value_score)["name"]


def analyze_suppliers(suppliers: list[Supplier], urgency: str = "normal", quantity: int = 1) -> dict:
    """
    Analyze suppliers and return recommendations.
    Accepts urgency and quantity for context-aware reasoning.
    """
    best_price = find_best_price(suppliers)
    fastest = find_fastest_delivery(suppliers)
    best_value = find_best_value(suppliers, urgency=urgency)

    in_stock = [s for s in suppliers if s["in_stock"]]

    # Generate reasoning
    reasoning_parts = []

    # Urgency context prefix
    if urgency in ("urgent", "very_urgent"):
        reasoning_parts.append("Dado la urgencia del pedido, recomendamos priorizar proveedores con stock inmediato y entrega rápida")

    if best_price and fastest and best_price == fastest:
        # Same supplier is both cheapest and fastest
        supplier = next(s for s in suppliers if s["name"] == best_price)
        reasoning_parts.append(
            f"{best_price} es la mejor opción: combina el precio más bajo "
            f"({supplier['total_price']:.2f}€) con la entrega más rápida "
            f"({supplier['delivery_days']} días)"
        )
    else:
        if best_price:
            price_supplier = next(s for s in suppliers if s["name"] == best_price)
            reasoning_parts.append(
                f"{best_price} ofrece el mejor precio total de {price_supplier['total_price']:.2f}€"
            )

        if fastest and fastest != best_price:
            fast_supplier = next(s for s in suppliers if s["name"] == fastest)
            reasoning_parts.append(
                f"{fastest} tiene la entrega más rápida en {fast_supplier['delivery_days']} días"
            )

    if best_value and best_value not in (best_price, fastest):
        reasoning_parts.append(
            f"{best_value} ofrece el mejor equilibrio precio-tiempo"
        )

    # Quantity context: total savings for large orders
    if quantity > 50 and len(in_stock) >= 2:
        prices = sorted([s["total_price"] for s in in_stock])
        savings = round(prices[-1] - prices[0], 2)
        if savings > 0:
            reasoning_parts.append(
                f"Para {quantity} unidades, la diferencia entre el proveedor más caro y el más barato es de {savings:.2f}€"
            )

    reasoning = ". ".join(reasoning_parts) + "." if reasoning_parts else "No hay proveedores disponibles con stock."

    return {
        "best_price": best_price,
        "fastest_delivery": fastest,
        "best_value": best_value,
        "reasoning": reasoning
    }


def sort_suppliers_by_price(suppliers: list[Supplier]) -> list[Supplier]:
    """Sort suppliers by total price, in-stock first."""
    return sorted(suppliers, key=lambda s: (not s["in_stock"], get_effective_price(s)))


if __name__ == "__main__":
    # Test with sample data
    test_suppliers = [
        {
            "name": "Würth España",
            "unit_price": 0.15,
            "total_price": 20.00,
            "delivery_days": 2,
            "min_order": 50,
            "shipping_cost": 5.00,
            "in_stock": True
        },
        {
            "name": "Bricomart",
            "unit_price": 0.12,
            "total_price": 17.00,
            "delivery_days": 5,
            "min_order": 100,
            "shipping_cost": 5.00,
            "in_stock": True
        },
        {
            "name": "Leroy Merlin Pro",
            "unit_price": 0.14,
            "total_price": 19.00,
            "delivery_days": 3,
            "min_order": 25,
            "shipping_cost": 5.00,
            "in_stock": True
        }
    ]

    result = analyze_suppliers(test_suppliers, urgency="normal", quantity=100)
    print("Recommendations:")
    print(f"  Best price: {result['best_price']}")
    print(f"  Fastest: {result['fastest_delivery']}")
    print(f"  Best value: {result['best_value']}")
    print(f"  Reasoning: {result['reasoning']}")
