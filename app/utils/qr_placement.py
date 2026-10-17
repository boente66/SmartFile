"""Visual PDF coordinates, including the human-readable validation label."""
def adjacent_qr(page_size, signature, size=90.0, side="below", caption=0.0):
    width, height = page_size
    x0, y0, x1, y1 = signature
    candidates = [(x0, y1 + caption + 8), (x1 + 8, min(y0, height - size - 27))]
    if side == "right":
        candidates.reverse()
    for x, y in candidates:
        x = max(0.0, min(x, width - max(size, 120)))
        y = max(0.0, y)
        if x + max(size, 120) <= width and y + size + 27 <= height:
            if x + size <= x0 or x >= x1 or y >= y1 + caption or y + size + 27 <= y0:
                return (x, y, x + size, y + size)
    raise ValueError("Não há espaço ao lado ou abaixo da assinatura. Reposicione a assinatura ou o QR manualmente.")
