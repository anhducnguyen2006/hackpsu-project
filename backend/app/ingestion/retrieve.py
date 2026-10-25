"""Re-resolve a dataset file from provider metadata, then download that file."""

from __future__ import annotations

from datetime import date

import httpx
import pandas as pd

from app.api.schemas import (
    DatasetRecord,
    DatasetResourceRequest,
    DatasetResourcesResponse,
    DownloadResource,
)
from app.config import settings
from app.discovery.dataverse import HarvardDataverseService
from app.discovery.zenodo import ZenodoService
from app.ingestion.guard import (
    DownloadRejected,
    assert_public_host,
    canonical_dataverse_url,
    canonical_zenodo_url,
    download_bytes,
)
from app.ingestion.parse import parse_table


class SelectionError(ValueError):
    """The requested dataset or file cannot be analyzed."""


def list_resources(
    dataset_id: str, *, client: httpx.Client | None = None
) -> DatasetResourcesResponse:
    if dataset_id.startswith("uci:"):
        return DatasetResourcesResponse(
            dataset_id=dataset_id,
            provider="UCI Machine Learning Repository",
            eligibility_status="supported_resource_verified",
            note="UCI analysis uses the native repository retrieval path. No file URL is accepted.",
        )
    record = _resolve(dataset_id, client)
    return DatasetResourcesResponse(
        dataset_id=record.id,
        provider=record.source,
        source_version=record.source_version,
        doi=record.doi,
        eligibility_status=record.eligibility_status,
        resources=list(record.download_resources),
        verification_candidates=list(record.verification_candidates),
        note=(
            "Verification candidates have a tabular filename and inconclusive type metadata. "
            "They are not analyzed until a bounded download parses as a table."
            if record.verification_candidates
            else None
        ),
    )


def load_table(
    dataset_id: str,
    resource_id: str | None,
    *,
    metadata_client: httpx.Client | None = None,
    download_client: httpx.Client | None = None,
    resolve=assert_public_host,
) -> tuple[DatasetRecord, DownloadResource, pd.DataFrame, bool]:
    """Return the record, chosen file, parsed frame, and whether metadata alone was inconclusive.

    The last flag is true only for an explicit verification candidate. Normal
    eligible files are still parsed before they are marked download-verified.
    """
    record = _resolve(dataset_id, metadata_client)
    resource, inconclusive = _choose(record, resource_id)
    url = _canonical_url(record, resource)
    content, response_type = download_bytes(url, client=download_client, resolve=resolve)
    frame = parse_table(
        content,
        filename=resource.filename or resource.original_filename,
        declared_format=resource.format,
        content_type=response_type or resource.content_type,
    )
    verified = resource.model_copy(update={
        "url": url,
        "content_type": response_type or resource.content_type,
        "eligible": True,
        "access_status": "public",
    })
    return record, verified, frame, inconclusive


def _resolve(dataset_id: str, client: httpx.Client | None) -> DatasetRecord:
    DatasetResourceRequest(dataset_id=dataset_id)
    if dataset_id.startswith("dataverse:"):
        source_id = dataset_id.split(":", 1)[1]
        if not source_id.startswith("doi:"):
            raise SelectionError("Dataverse dataset id must use the persistent DOI.")
        stub = DatasetRecord(
            id=dataset_id,
            source="Harvard Dataverse",
            source_id=source_id,
            title="Pending provider metadata",
            landing_page_url=f"https://dataverse.harvard.edu/dataset.xhtml?persistentId={source_id}",
            doi=source_id,
        )
        return HarvardDataverseService(client=client).verify(stub, today=date.today())
    if dataset_id.startswith("zenodo:"):
        source_id = dataset_id.split(":", 1)[1]
        if not source_id.isdigit():
            raise SelectionError("Zenodo dataset id must be the published record number.")
        service = ZenodoService(client=client, api_url=settings.zenodo_api_url)
        return service.verify(DatasetRecord(
            id=dataset_id,
            source="Zenodo",
            source_id=source_id,
            title="Pending provider metadata",
            landing_page_url=f"https://zenodo.org/records/{source_id}",
        ))
    raise SelectionError("Dataset id must be a UCI, Dataverse, or Zenodo identifier.")


def _choose(
    record: DatasetRecord, resource_id: str | None
) -> tuple[DownloadResource, bool]:
    eligible = [item for item in record.download_resources if item.eligible]
    candidates = list(record.verification_candidates)
    if resource_id is None:
        if len(eligible) == 1:
            return eligible[0], False
        if len(eligible) > 1:
            raise SelectionError("Choose a resource_id. This dataset has more than one supported file.")
        if len(candidates) == 1:
            raise SelectionError(
                "This file has a tabular name but inconclusive type metadata. "
                "Submit its resource_id to verify the downloaded content."
            )
        raise SelectionError("No supported public tabular file is available for this dataset.")
    match = _match(eligible, resource_id)
    if match is not None:
        return match, False
    candidate = _match(candidates, resource_id)
    if candidate is not None:
        return candidate, True
    raise SelectionError("resource_id does not match a published file on this dataset.")


def _match(resources: list[DownloadResource], resource_id: str) -> DownloadResource | None:
    for resource in resources:
        if resource_id in {resource.file_id, resource.filename, resource.original_filename}:
            return resource
    return None


def _canonical_url(record: DatasetRecord, resource: DownloadResource) -> str:
    if record.source == "Harvard Dataverse":
        if not resource.file_id:
            raise SelectionError("Dataverse file is missing its published file id.")
        return canonical_dataverse_url(resource.file_id)
    if record.source == "Zenodo":
        name = resource.filename or resource.file_id
        if not name:
            raise SelectionError("Zenodo file is missing its published file key.")
        return canonical_zenodo_url(record.source_id, name)
    raise SelectionError("This repository has no external file download.")
