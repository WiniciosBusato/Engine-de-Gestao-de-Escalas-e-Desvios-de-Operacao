from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.reports import generate_daily_adherence_csv

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])

@router.get("/adherence/daily/csv")
def export_daily_adherence_csv(
    report_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    target_date = report_date or date.today()
    csv_file = generate_daily_adherence_csv(db=db, target_date=target_date)

    filename = f"aderencia_diaria_{target_date.strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([csv_file.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )