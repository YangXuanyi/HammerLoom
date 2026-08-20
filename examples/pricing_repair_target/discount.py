def apply_member_discount(amount: float) -> float:
    """Apply a 10 percent member discount to qualifying orders."""
    return amount * 0.9 if amount > 100 else amount
