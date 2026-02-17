from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class UserRole(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"

class ScanStatus(str, enum.Enum):
    PENDING = "Pending Review"
    VERIFIED = "Verified"

class RiskLevel(str, enum.Enum):
    NORMAL = "Normal"
    MODERATE = "Moderate"
    HIGH = "High Risk"
    UNKNOWN = "Unknown" # default for new scans

class AuthProvider(str, enum.Enum):
    LOCAL = "local"  # Email/Password
    GOOGLE = "google"  # Google OAuth

# User (patient) ────────< Scan
#    my_scans            patient
#
# User (doctor) ────────< Scan
#    reviewed_scans      doctor

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    # Password is optional because Google users don't need it
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    # track how they registered
    provider = Column(Enum(AuthProvider), default=AuthProvider.LOCAL)
    avatar_url = Column(String(500), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.PATIENT)
    created_at = Column(DateTime, default=datetime.now())

    # Relationships
    my_scans = relationship("Scan", foreign_keys="[Scan.patient_id]", back_populates="patient")
    reviewed_scans = relationship("Scan", foreign_keys="[Scan.doctor_id]", back_populates="doctor")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    image_url = Column(String(500), nullable=False)
    scan_name = Column(String(200), default="Untitled Scan")  # "Regular Checkup - Right Eye"
    upload_date = Column(DateTime, default=datetime.now())

    ai_diagnosis = Column(String(100), nullable=True)  # "Diabetic Retinopathy"
    ai_confidence = Column(Float, nullable=True)

    final_diagnosis = Column(String(100), nullable=True)  # Doctor's final decision
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.UNKNOWN)
    status = Column(Enum(ScanStatus), default=ScanStatus.PENDING)
    doctor_notes = Column(Text, nullable=True)  # Notes from the doc

    patient = relationship("User", foreign_keys=[patient_id], back_populates="my_scans")
    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="reviewed_scans")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(500), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now())
    revoked = Column(Boolean, default=False)

    # Relationship
    user = relationship("User", backref="tokens")