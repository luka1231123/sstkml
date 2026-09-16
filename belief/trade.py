"""A local purchase estimate using the quay's counted cargo and price."""


def purchase(b: dict, purse: int = 3000) -> dict:
    trade = b.get("trade", {})
    price = trade.get("grain_price", 0)
    available = sum(max(0, c.get("available", 0)) for c in trade.get("cargo", ())
                    if c.get("good") == "grain")
    copper = b.get("stores", {}).get("copper", 0)
    grain = min(available, max(0, purse) * 1000 // price) if price > 0 else 0
    paid = (grain * price + 999) // 1000
    refusal = ("The quay has no grain price." if price <= 0 else
               "No grain cargo is available at the quay." if available <= 0 else
               f"The purse needs {purse:,} copper shekels; {copper:,} counted." if copper < purse else
               "This purse cannot buy one qa of grain." if grain <= 0 else "")
    return {"grain": grain, "paid": paid, "copper": copper,
            "remaining": copper - paid, "available": available,
            "price": price, "refusal": refusal}


def lines(b: dict, purse: int = 3000) -> list[str]:
    p = purchase(b, purse)
    out = [f"Local purchase · quay count, turn {b.get('turn', '?')}.",
           f"Purse limit: {purse:,} copper shekels.",
           f"Counted price: {p['price']:,} copper shekels per 1,000 qa.",
           f"Estimated receipt: {p['grain']:,} qa from {p['available']:,} qa available.",
           f"Estimated payment: {p['paid']:,} copper shekels (rounded up).",
           f"Copper counted after payment: {p['remaining']:,} shekels.",
           "Buys cargo already here; unused copper stays in your stores."]
    if p["refusal"]:
        out.append(p["refusal"])
    return out
