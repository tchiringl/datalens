from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from services.assessment_service import generate_assessment_report, list_assessment_reports

router = APIRouter()


class AssessmentRequest(BaseModel):
    source_id: str = Field(..., description="OpenMetadata service/source id")
    table_limit: int = Field(3, ge=1, le=10)
    row_limit: int = Field(20000, ge=100, le=200000)


@router.get("/reports", summary="List generated data assessment reports")
async def get_reports(source_id: Optional[str] = Query(default=None)) -> List[Dict[str, Any]]:
    return list_assessment_reports(source_id=source_id)


@router.post(
    "/reports/generate",
    summary="Generate ydata-profiling assessment report for a source",
)
async def generate_report(payload: AssessmentRequest) -> Dict[str, Any]:
    try:
        return await generate_assessment_report(
            source_id=payload.source_id,
            table_limit=payload.table_limit,
            row_limit=payload.row_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
