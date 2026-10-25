"""Parse a downloaded provider file only after its bytes look tabular."""

from __future__ import annotations

import io

import pandas as pd

from app.discovery.eligibility import extension_of, normalize_media_type
from app.ingestion.guard import DownloadRejected

_MARKUP_PREFIXES = (b"<!doctype html", b"<html", b"<head", b"<script")
_BINARY_PREFIXES = (
    b"%PDF",
    b"PK\x03\x04",
    b"\x1f\x8b",
    b"PAR1",
    b"\x7fELF",
    b"\xd0\xcf\x11\xe0",
    b"\x89PNG",
)


def parse_table(
    content: bytes,
    *,
    filename: str | None,
    declared_format: str | None,
    content_type: str | None,
) -> pd.DataFrame:
    """Return a DataFrame or reject HTML, PDF, archives, and malformed text."""
    _reject_known_payload(content)
    media = normalize_media_type(content_type)
    if media in {
        "text/html",
        "application/xhtml+xml",
        "application/pdf",
        "application/zip",
        "application/gzip",
        "application/octet-stream",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.apache.parquet",
    }:
        raise DownloadRejected(f"Downloaded content type {media} is not tabular text.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DownloadRejected("Downloaded file is not UTF-8 text.") from error
    if "\x00" in text:
        raise DownloadRejected("Downloaded file contains binary data.")
    separator = _separator(text, filename, declared_format, media)
    frame = pd.read_csv(io.StringIO(text), sep=separator, nrows=100_001)
    if frame.shape[1] < 1 or (frame.shape[0] == 0 and frame.shape[1] == 0):
        raise DownloadRejected("Downloaded file did not parse as a table.")
    if len(frame) > 100_000 or len(frame.columns) > 500:
        raise DownloadRejected("Downloaded table exceeds the row or column limit.")
    # A single undifferentiated line is not evidence of a delimiter match.
    if separator not in text.splitlines()[0] and frame.shape[1] == 1 and " " in text.splitlines()[0]:
        raise DownloadRejected("Downloaded file does not use the expected delimiter.")
    return frame


def _reject_known_payload(content: bytes) -> None:
    sample = content.lstrip()[:64]
    lowered = sample[:32].lower()
    if any(lowered.startswith(prefix) for prefix in _MARKUP_PREFIXES):
        raise DownloadRejected("Downloaded file is HTML, not a table.")
    if any(sample.startswith(prefix) for prefix in _BINARY_PREFIXES):
        raise DownloadRejected("Downloaded file is a binary or archive payload.")


def _separator(
    text: str, filename: str | None, declared_format: str | None, media: str | None
) -> str:
    suffix = extension_of(filename)
    hint = (declared_format or "").lower()
    if hint in {"tab", "tsv"} or suffix in {"tab", "tsv"} or media == "text/tab-separated-values":
        return "\t"
    if hint == "csv" or suffix == "csv" or media in {"text/csv", "application/csv", "text/comma-separated-values"}:
        return ","
    header = text.splitlines()[0] if text else ""
    if header.count("\t") > header.count(","):
        return "\t"
    return ","
