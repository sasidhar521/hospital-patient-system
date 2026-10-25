from datetime import datetime
from database import Base
from sqlalchemy import Column, DateTime, Integer, String


class PatientRecord(Base):
  __tablename__ = "patient_records"

  id = Column(Integer, primary_key=True, index=True)
  patient_identifier = Column(
      String, index=True
  )  # Assigned ID or name instead of real ID numbers
  treatment = Column(String)
  surgery = Column(String)
  doctor = Column(String)
  prescription = Column(String)
  hospital_name = Column(String)
  created_at = Column(DateTime, default=datetime.utcnow)