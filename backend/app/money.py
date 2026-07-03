def format_inr(paise: int) -> str:
    """Format integer paise as Indian-grouped rupees, e.g. 24000000 -> '₹2,40,000'."""
    rupees = paise // 100
    s = str(rupees)
    if len(s) <= 3:
        grouped = s
    else:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        grouped = ",".join(parts) + "," + tail
    return f"₹{grouped}"
