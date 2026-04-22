from sqlalchemy.orm import Session
from app.db import models

def create_scan(db: Session, patient_id: int, image_url: str, scan_name: str, ai_diagnosis: str, ai_confidence: float):
    db_scan = models.Scan(
        patient_id=patient_id,
        image_url=image_url,
        scan_name=scan_name,
        ai_diagnosis=ai_diagnosis,
        ai_confidence=ai_confidence,
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    return db_scan

def get_scans_by_patient(db: Session, patient_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Scan).filter(models.Scan.patient_id == patient_id).order_by(models.Scan.upload_date.desc()).offset(skip).limit(limit).all()

def get_scan_by_id_and_patient(db: Session, scan_id: int, patient_id: int):
    return db.query(models.Scan).filter(models.Scan.id == scan_id, models.Scan.patient_id == patient_id).first()

def get_pending_scans(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Scan).filter(models.Scan.status == models.ScanStatus.PENDING).order_by(models.Scan.upload_date.asc()).offset(skip).limit(limit).all()

def verify_scan(db: Session, scan_id: int, doctor_id: int, final_diagnosis: str, risk_level: str, status: str, doctor_notes: str = None):
    db_scan = db.query(models.Scan).filter(models.Scan.id == scan_id).first()
    if db_scan:
        db_scan.doctor_id = doctor_id
        db_scan.final_diagnosis = final_diagnosis
        db_scan.risk_level = risk_level
        db_scan.doctor_notes = doctor_notes
        db_scan.status = status
        db.commit()
        db.refresh(db_scan)
    return db_scan

def get_scan_by_id(db: Session, scan_id: int):
    return db.query(models.Scan).filter(models.Scan.id == scan_id).first()
