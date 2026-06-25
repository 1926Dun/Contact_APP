"""Report generation: partition candidates into selected/not-selected, add provenance."""

from datetime import datetime, timezone

from .knowledge import get_knowledge
from .schemas import Assessment, DocumentVersion, Report


def generate_report(
    log_id: int,
    assessment: Assessment,
    selected_indices: list[int],
) -> Report:
    """Build a report from the assessment and user's crime selections."""
    candidates = assessment.candidates

    selected = [candidates[i] for i in range(len(candidates)) if i in selected_indices]
    not_selected = [
        candidates[i] for i in range(len(candidates)) if i not in selected_indices
    ]

    kb = get_knowledge()
    doc_versions = [
        DocumentVersion(
            key=d.key,
            label=d.label,
            filename=d.filename,
            file_hash=d.file_hash[:16],
        )
        for d in kb.documents.values()
    ]

    return Report(
        log_id=log_id,
        metadata=assessment.metadata,
        summary=assessment.summary,
        people=assessment.people,
        crimes_selected=selected,
        crimes_not_selected=not_selected,
        document_versions=doc_versions,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
