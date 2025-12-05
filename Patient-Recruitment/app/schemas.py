from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal, Union

# ----- Criteria JSON -----

Criterion = Union[str, Dict[str, Any]]

class CriteriaJSON(BaseModel):
    inclusion: List[Criterion] = Field(default_factory=list)
    exclusion: List[Criterion] = Field(default_factory=list)
    notes: Optional[str] = None
    uln_tables: Optional[Dict[str, Any]] = None


# ----- Input rows (as read from Excel) -----

class PatientRow(BaseModel):
    Patient_ID: str
    Age: int
    Weight_kg: float
    T_cruzi_Diagnosis: str                 # "Confirmed" / "Not confirmed" (case-insensitive)
    Informed_Consent_Signed: str           # Yes / No
    Lives_in_Vector_Free_Area: str         # Yes / No
    Chronic_Chagas_Symptoms: str           # Yes / No
    Previous_Chagas_Treatment: str         # Yes / No
    History_of_Azole_Hypersensitivity: str # Yes / No
    Concomitant_CYP3A4_Meds: str           # Yes / No

class MappingRow(BaseModel):
    Patient_ID: str
    Site_ID: Optional[str] = None
    Assignment_Date: str                   # YYYY-MM-DD
    Assignment_Method: Optional[str] = None
    Enrollment_Status: Optional[str] = None
    Cohort: Optional[str] = None
    Priority_Flag: Optional[str] = None

class SiteHistoryRow(BaseModel):
    siteId: str
    trialId: str
    trialTitle: str
    therapeuticArea: str
    phase: str
    fiscalYear: int
    status: str                            # Closed / Terminated / Ongoing / Completed
    startupDays: int
    irbApprovalDays: int
    contractExecutionDays: int
    enrollmentTarget: int
    enrollmentActual: int
    accrualRatePerMonth: float
    screeningFailureRate: float            # 0..1 or percentage (we normalize)
    firstPatientIn: Optional[str] = None
    lastPatientOut: Optional[str] = None
    notes: Optional[str] = None


# ----- Eligibility outputs -----

EligibleType = Literal[True, False, "Inconclusive"]

class EligibilityResultRow(BaseModel):
    Patient_ID: str
    Site_ID: Optional[str] = None
    Eligible: EligibleType
    Reasons: List[str] = Field(default_factory=list)
    Missing_Data: List[str] = Field(default_factory=list)
    Confidence: Optional[float] = None


# ----- Site ranking outputs -----

class SiteRankingRow(BaseModel):
    Site_ID: Optional[str] = None
    Eligible_Patient_Pool: int
    Site_Performance_Factor: float
    Enrollment_Probability: float
    Rank: int
