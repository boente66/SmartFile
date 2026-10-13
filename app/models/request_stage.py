"""Mapeamento puro entre estado operacional e etapa visual."""

def request_stage(status):
    return {"OPEN":0,"IN_PROGRESS":1,"OVERDUE":1,"ATTENDED":2,"DELIVERING":3,"DELIVERED":3,"COMPLETED":4,"CANCELLED":4}.get(status,0)
