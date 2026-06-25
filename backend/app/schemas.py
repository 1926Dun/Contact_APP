"""Pydantic schemas for assessment and report output."""

from pydantic import BaseModel, Field


class LogMetadata(BaseModel):
    reference_number: str | None = None
    date: str | None = None
    times: list[str] = Field(default_factory=list)
    location: str | None = None


class Person(BaseModel):
    name: str
    role: str = Field(description="victim, suspect, or witness")
    basis: str


class Vulnerability(BaseModel):
    indicator: str
    person: str
    detail: str


class PointToProveMapping(BaseModel):
    point: str
    status: str = Field(description="met, not_met, or unclear")
    supporting_text: str


class CandidateCrime(BaseModel):
    offence_title: str
    legislation: str
    classification_code: str | None = None
    notifiable: bool | None = None
    is_principal_crime: bool = Field(
        description="True if this offence appears in the Principal Crime look-up table (HOCR page 14)"
    )
    principal_crime_max_sentence: str | None = Field(
        default=None,
        description="Maximum sentence from the Principal Crime table, e.g. '10 yrs', 'Life'"
    )
    certainty: int = Field(ge=0, le=100, description="0-100 in 10-point increments")
    rationale: str
    points_to_prove: list[PointToProveMapping]
    nsir_alternative: str | None = None
    guidance_applied: list[str] = Field(default_factory=list)


class CountingRulesAnalysis(BaseModel):
    one_crime_per_victim: str = Field(
        description="Apply HOCR One Crime per Victim rule: identify each victim and the offender(s), state how many crimes would be counted and why"
    )
    finished_incident_rule: str = Field(
        description="Apply HOCR Finished Incident Rule: state whether the log reports a finished sequence of acts, and what that means for the count"
    )
    principal_crime: str = Field(
        description="Apply HOCR Principal Crime Rule: identify the most serious offence from the candidates and state why it is the principal crime for recording purposes"
    )


class Assessment(BaseModel):
    metadata: LogMetadata
    summary: str
    people: list[Person]
    vulnerabilities: list[Vulnerability]
    candidates: list[CandidateCrime] = Field(
        description="Candidate crimes ordered by certainty, highest first"
    )
    counting_rules: CountingRulesAnalysis


class DocumentVersion(BaseModel):
    key: str
    label: str
    filename: str
    file_hash: str


class Report(BaseModel):
    log_id: int
    metadata: LogMetadata
    summary: str
    people: list[Person]
    crimes_selected: list[CandidateCrime]
    crimes_not_selected: list[CandidateCrime]
    document_versions: list[DocumentVersion]
    created_at: str


class ReportRequest(BaseModel):
    log_id: int
    selected_indices: list[int] = Field(
        description="Zero-based indices of candidates the user selected"
    )
