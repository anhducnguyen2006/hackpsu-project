"""Decide whether a repository record has a supported public tabular resource.

Eligibility is not relevance. A filename ending in ``.csv`` is not evidence that
a file was downloaded or that its bytes are tabular. ``download_verified`` is
reserved for a later bounded retrieval and is never set during discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.api.schemas import DownloadResource

ELIGIBLE_STATUSES = frozenset({"supported_resource_verified", "download_verified"})

TABULAR_CONTENT_TYPES = {
    "text/csv": "csv",
    "application/csv": "csv",
    "text/comma-separated-values": "csv",
    "text/tab-separated-values": "tsv",
    "text/tsv": "tsv",
}

UNSUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "application/gzip",
    "application/x-gzip",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.apache.parquet",
    "application/x-parquet",
    "application/octet-stream",
}

SUPPORTED_EXTENSIONS = {"csv": "csv", "tsv": "tsv", "tab": "tab"}


@dataclass(frozen=True)
class FileAssessment:
    eligible: bool
    status: str
    reason: str
    resource: DownloadResource | None = None


def normalize_media_type(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    media = value.split(";", 1)[0].strip().lower()
    return media or None


def extension_of(filename: str | None) -> str | None:
    if not isinstance(filename, str) or "." not in filename:
        return None
    suffix = filename.rsplit(".", 1)[-1].strip().lower()
    return suffix or None


def inconclusive_resource(
    *,
    url: str | None,
    filename: str | None,
    original_filename: str | None = None,
    content_type: str | None = None,
    original_format: str | None = None,
    size_bytes: int | None = None,
    checksum: str | None = None,
    file_id: str | None = None,
    access_status: str = "public",
    max_bytes: int,
) -> DownloadResource | None:
    suffix = inconclusive_tabular_name(
        filename=filename,
        original_filename=original_filename,
        content_type=content_type,
        access_status=access_status,
        size_bytes=size_bytes,
        max_bytes=max_bytes,
    )
    if suffix is None or not url:
        return None
    return DownloadResource(
        url=url,
        format=suffix,
        file_id=file_id,
        filename=filename,
        original_filename=original_filename,
        content_type=normalize_media_type(content_type),
        original_format=normalize_media_type(original_format),
        size_bytes=size_bytes,
        checksum=checksum,
        access_status="public",
        eligible=False,
    )


def inconclusive_tabular_name(
    *,
    filename: str | None,
    original_filename: str | None = None,
    content_type: str | None = None,
    access_status: str = "public",
    size_bytes: int | None = None,
    max_bytes: int,
) -> str | None:
    """Return csv/tsv/tab when a public name is plausible but the MIME type is not.

    ``text/plain`` and a missing type are inconclusive. They are not eligibility
    and they are not a download. ``application/octet-stream`` stays unsupported.
    """
    if access_status != "public":
        return None
    if size_bytes is not None and size_bytes > max_bytes:
        return None
    media = normalize_media_type(content_type)
    if media not in {None, "text/plain"}:
        return None
    suffix = extension_of(filename) or extension_of(original_filename)
    if suffix in {"csv", "tsv", "tab"}:
        return suffix
    return None


def assess_tabular_file(
    *,
    url: str | None,
    filename: str | None = None,
    original_filename: str | None = None,
    content_type: str | None = None,
    original_format: str | None = None,
    size_bytes: int | None = None,
    checksum: str | None = None,
    file_id: str | None = None,
    access_status: str = "public",
    max_bytes: int,
) -> FileAssessment:
    """Classify one provider file from metadata. This does not read the file."""
    media = normalize_media_type(content_type)
    original_media = normalize_media_type(original_format)
    suffix = extension_of(filename)
    original_suffix = extension_of(original_filename)
    label = filename or original_filename or file_id or "unnamed file"

    if access_status in {"restricted", "embargoed"}:
        return FileAssessment(False, access_status, f"{label} is {access_status}.")
    if access_status != "public":
        return FileAssessment(False, "unverified", f"{label} has no verified public access status.")

    if size_bytes is not None and size_bytes > max_bytes:
        return FileAssessment(
            False,
            "unsupported",
            f"{label} declares {size_bytes} bytes, above the {max_bytes}-byte limit.",
        )

    if media in UNSUPPORTED_CONTENT_TYPES or original_media in UNSUPPORTED_CONTENT_TYPES:
        rejected = media or original_media
        return FileAssessment(
            False,
            "unsupported",
            f"{label} has unsupported content type {rejected}.",
        )

    tabular = TABULAR_CONTENT_TYPES.get(media or "")
    if tabular is None and original_media in TABULAR_CONTENT_TYPES:
        # Dataverse may store an ingested .tab file whose original upload was CSV.
        tabular = "tab" if suffix == "tab" else TABULAR_CONTENT_TYPES[original_media]
    if tabular == "tsv" and suffix == "tab":
        tabular = "tab"

    if tabular is None:
        hinted = SUPPORTED_EXTENSIONS.get(suffix or "") or SUPPORTED_EXTENSIONS.get(original_suffix or "")
        if hinted and media is None and original_media is None:
            return FileAssessment(
                False,
                "unverified",
                f"{label} has a tabular filename but no provider content type.",
            )
        return FileAssessment(
            False,
            "unsupported",
            f"{label} is not a supported public CSV, TSV, or TAB resource.",
        )

    if not url:
        return FileAssessment(False, "unverified", f"{label} has no stable provider file URL.")

    resource = DownloadResource(
        url=url,
        format=tabular,
        file_id=file_id,
        filename=filename,
        original_filename=original_filename,
        content_type=media,
        original_format=original_media,
        size_bytes=size_bytes,
        checksum=checksum,
        access_status="public",
        eligible=True,
    )
    return FileAssessment(
        True,
        "supported_resource_verified",
        f"{label} is a public {tabular} resource in provider metadata.",
        resource,
    )


def summarize_files(
    assessments: list[FileAssessment], *, files_declared: bool
) -> tuple[str, str, list[DownloadResource]]:
    eligible = [item.resource for item in assessments if item.eligible and item.resource is not None]
    if eligible:
        names = ", ".join(resource.filename or resource.file_id or resource.format for resource in eligible)
        ignored = len(assessments) - len(eligible)
        reason = f"Provider metadata lists supported public tabular data: {names}."
        if ignored:
            reason += f" {ignored} other file(s) are not eligible analysis inputs."
        return "supported_resource_verified", reason, eligible
    if any(item.status in {"restricted", "embargoed"} for item in assessments):
        return "restricted", assessments[0].reason if len(assessments) == 1 else "Supported files are restricted or embargoed.", []
    if files_declared:
        unverified = [item for item in assessments if item.status == "unverified"]
        if unverified:
            reason = " ".join(item.reason for item in unverified)
            unsupported_count = sum(item.status == "unsupported" for item in assessments)
            if unsupported_count:
                reason += f" {unsupported_count} other file(s) have unsupported formats."
            return "unverified", reason, []
        reason = assessments[0].reason if assessments else "The record lists files, but none are supported public tabular data."
        status = assessments[0].status if assessments and assessments[0].status in {
            "restricted",
            "unsupported",
            "verification_failed",
        } else "unsupported"
        return status, reason, []
    return "unverified", "Provider metadata did not include a file list.", []


def embargo_status(date_available: str | None, today: date) -> str | None:
    if not isinstance(date_available, str) or not date_available.strip():
        return None
    try:
        available = date.fromisoformat(date_available.strip()[:10])
    except ValueError:
        return "unverified"
    if available > today:
        return "embargoed"
    return None
