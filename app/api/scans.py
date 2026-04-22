import io
import os
import uuid
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from app.services.inference import predict_image
from app.schemas.scan import ScanPredictionResponse, ScanResponse, ScanVerifyRequest
from app.api import deps
from app.db import database, crud, models

router = APIRouter()


@router.post("/predict")
async def predict_scan(
        file: UploadFile = File(...),
        current_user: Optional[models.User] = Depends(deps.get_optional_user),
        db: Session = Depends(database.get_db)
):
    if file.content_type not in ["image/jpeg", "image/png", "image/jpg"]:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG, and PNG images are allowed."
        )

    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="Invalid image file."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process image: {str(e)}"
        )

    prediction = predict_image(image)

    # ─── Authenticated Non-Doctor User: save scan to DB ───
    if current_user is not None and current_user.role != "doctor":

        try:
            # Reset file pointer since we consumed it when predicting
            file.file.seek(0)

            # Upload actual file stream to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file.file,
                folder="smart_retina_scans",
                resource_type="image"
            )
            image_url = upload_result.get("secure_url")
        except Exception as upload_error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload image to cloud storage: {str(upload_error)}"
            )

        scan = crud.create_scan(
            db=db,
            patient_id=current_user.id,
            image_url=image_url,
            scan_name=file.filename or "Untitled Scan",
            ai_diagnosis=prediction["predicted_class"],
            ai_confidence=prediction["confidence"]
        )
        return {"scan": scan, "prediction": prediction, "guest": False}

    # ─── Guest User: return result only, nothing saved ───
    return {
        "scan": None,
        "prediction": prediction,
        "guest": True,
        "message": "Sign up to save your scan results and view your history."
    }


@router.get("/my-scans", response_model=List[ScanResponse])
def get_my_scans(
        skip: int = 0,
        limit: int = 100,
        current_user: models.User = Depends(deps.get_current_user),
        db: Session = Depends(database.get_db)
):
    scans = crud.get_scans_by_patient(db, patient_id=current_user.id, skip=skip, limit=limit)
    return scans


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan_details(
        scan_id: int,
        current_user: models.User = Depends(deps.get_current_user),
        db: Session = Depends(database.get_db)
):
    # If the user is a DOCTOR, they can look up any scan by ID
    if current_user.role == models.UserRole.DOCTOR:
        scan = crud.get_scan_by_id(db, scan_id=scan_id)
    else:
        # Patient looking up their own scan
        scan = crud.get_scan_by_id_and_patient(db, scan_id=scan_id, patient_id=current_user.id)

    if not scan:
        raise HTTPException(
            status_code=404,
            detail="Scan not found or you don't have access to it."
        )
    return scan


# --------------------- DOCTOR ROUTES --------------------- #

@router.get("/doctor/pending", response_model=List[ScanResponse])
def get_pending_scans(
        skip: int = 0,
        limit: int = 100,
        current_doctor: models.User = Depends(deps.get_current_doctor),
        db: Session = Depends(database.get_db)
):
    return crud.get_pending_scans(db, skip=skip, limit=limit)


@router.get("/doctor/patient/{patient_id}", response_model=List[ScanResponse])
def get_patient_scans_for_doctor(
        patient_id: int,
        skip: int = 0,
        limit: int = 100,
        current_doctor: models.User = Depends(deps.get_current_doctor),
        db: Session = Depends(database.get_db)
):
    return crud.get_scans_by_patient(db, patient_id=patient_id, skip=skip, limit=limit)


@router.put("/doctor/{scan_id}/verify", response_model=ScanResponse)
def verify_scan_route(
        scan_id: int,
        request: ScanVerifyRequest,
        current_doctor: models.User = Depends(deps.get_current_doctor),
        db: Session = Depends(database.get_db)
):
    scan = crud.verify_scan(
        db,
        scan_id=scan_id,
        doctor_id=current_doctor.id,
        final_diagnosis=request.final_diagnosis,
        risk_level=request.risk_level,
        status=request.status,
        doctor_notes=request.doctor_notes
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan
