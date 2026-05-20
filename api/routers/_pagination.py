from typing import Dict
from fastapi import Query


def pagination(
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> Dict[str, int]:
    return {"limit": limit, "offset": offset}
