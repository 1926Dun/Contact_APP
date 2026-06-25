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
    certainty: int = Field(ge=0, le=100, description="0-100 in 10-point increments")
    rationale: str
    points_to_prove: list[PointToProveMapping]
    nsir_alternative: str | None = None
    guidance_applied: list[str] = Field(default_factory=list)


class Assessment(BaseModel):
    metadata: LogMetadata
    summary: str
    people: list[Person]
    vulnerabilities: list[Vulnerability]
    candidates: list[CandidateCrime] = Field(
        description="Candidate crimes ordered by certainty, highest first"
    )
