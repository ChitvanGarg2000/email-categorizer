from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from ..application_extractor import APPLICATION_STAGES
from ..database import get_db
from ..models import User, Application
from ..schemas import ApplicationOut, ApplicationUpdate
from .emails import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/", response_model=list[ApplicationOut])
def list_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.last_updated.desc())
        .all()
    )
    return [ApplicationOut.model_validate(r) for r in rows]


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int,
    body: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if body.stage is not None:
        if body.stage not in APPLICATION_STAGES:
            raise HTTPException(status_code=400, detail="Invalid stage")
        app.stage = body.stage
    if body.company is not None:
        app.company = body.company or None
    if body.role is not None:
        app.role = body.role or None

    db.commit()
    db.refresh(app)
    return ApplicationOut.model_validate(app)
