"""Harvard Dataverse may redirect once to its exact object-store host only."""

from __future__ import annotations

import logging

import pytest

from app.ingestion.guard import (
    DownloadRejected,
    download_bytes,
    redacted_url,
    validate_provider_url,
)
from app.ingestion.parse import parse_table
from app.ingestion.retrieve import load_table


STORAGE = "https://dvn-cloud-iqss.s3.amazonaws.com/10.7910/DVN/Z2V8DD/object?X-Amz-Signature=secret"
API = "https://dataverse.harvard.edu/api/access/datafile/6988112"
TAB = b"id\tname\n1\talice\n2\tbob\n"


class Peer:
    def __init__(self, address: str = "8.8.8.8") -> None:
        self.address = address

    def get_extra_info(self, name: str):
        if name in {"peername", "server_addr"}:
            return (self.address, 443)
        return None


class Response:
    def __init__(
        self,
        *,
        body: bytes = b"",
        status_code: int = 200,
        content_type: str = "text/tab-separated-values",
        location: str | None = None,
        peer: str = "8.8.8.8",
        content_length: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        if location:
            self.headers["location"] = location
        if content_length is not None:
            self.headers["content-length"] = content_length
        self._body = body
        self.extensions = {"network_stream": Peer(peer)}

    def iter_bytes(self):
        if self._body:
            yield self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Client:
    def __init__(self, routes: list[tuple[str, Response]] | dict[str, Response]) -> None:
        if isinstance(routes, dict):
            self.routes = list(routes.items())
        else:
            self.routes = list(routes)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        for key, response in self.routes:
            if key in url or url == key:
                return response
        raise AssertionError(url)

    def close(self) -> None:
        return None


def _public(host: str) -> set[str]:
    del host
    return {"8.8.8.8"}


def test_approved_dataverse_storage_redirect_is_allowed_and_parsed() -> None:
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE, content_type="text/plain")),
            (
                "dvn-cloud-iqss.s3.amazonaws.com",
                Response(body=TAB, content_type="text/tab-separated-values"),
            ),
        ]
    )
    body, media = download_bytes(API, client=client, resolve=_public)
    frame = parse_table(body, filename="ita_senate_social.tab", declared_format="tab", content_type=media)
    assert list(frame.columns) == ["id", "name"]
    assert len(frame) == 2
    assert [url for url, _ in client.calls] == [API, STORAGE]
    assert all(
        kwargs.get("headers", {}).get("Authorization") is None
        for _, kwargs in client.calls
    )
    assert all(
        "Bearer" not in str(kwargs.get("headers", {})) for _, kwargs in client.calls
    )


def test_storage_host_is_rejected_as_an_initial_url() -> None:
    with pytest.raises(DownloadRejected, match="not an initial download host"):
        download_bytes(STORAGE, client=Client([]), resolve=_public)
    with pytest.raises(DownloadRejected, match="not an initial download host"):
        validate_provider_url(STORAGE)


@pytest.mark.parametrize(
    "location",
    [
        "https://other-bucket.s3.amazonaws.com/secret",
        "https://evil-dvn-cloud-iqss.s3.amazonaws.com/10.7910/DVN/Z2V8DD/object",
        "https://s3.amazonaws.com/dvn-cloud-iqss/object",
        "http://dvn-cloud-iqss.s3.amazonaws.com/object",
        "https://dvn-cloud-iqss.s3.amazonaws.com:8443/object",
        "https://user:pass@dvn-cloud-iqss.s3.amazonaws.com/object",
        "https://dvn-cloud-iqss.s3.amazonaws.com%2eevil.example/object",
        "https://169.254.169.254/latest/meta-data",
        "https://127.0.0.1/object",
        "https://[::1]/object",
    ],
)
def test_unapproved_redirect_targets_are_rejected(location: str) -> None:
    client = Client([(API, Response(status_code=303, location=location))])
    with pytest.raises(DownloadRejected):
        download_bytes(API, client=client, resolve=_public)
    assert [url for url, _ in client.calls] == [API]


def test_private_dns_answers_are_rejected_for_storage_hosts() -> None:
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE)),
            ("dvn-cloud-iqss.s3.amazonaws.com", Response(body=TAB)),
        ]
    )

    def private(host: str) -> set[str]:
        if host == "dataverse.harvard.edu":
            return {"8.8.8.8"}
        raise DownloadRejected("Provider address is not a public route.")

    with pytest.raises(DownloadRejected, match="public route"):
        download_bytes(API, client=client, resolve=private)


def test_metadata_service_and_private_dns_sets_are_rejected() -> None:
    for blocked in ("169.254.169.254", "10.0.0.8", "fc00::1"):
        client = Client(
            [
                (API, Response(status_code=303, location=STORAGE)),
                ("dvn-cloud-iqss.s3.amazonaws.com", Response(body=TAB, peer=blocked)),
            ]
        )

        def resolve(host: str, address: str = blocked) -> set[str]:
            if host == "dataverse.harvard.edu":
                return {"8.8.8.8"}
            return {address}

        with pytest.raises(DownloadRejected):
            download_bytes(API, client=client, resolve=resolve)


def test_peer_mismatch_after_storage_redirect_is_rejected() -> None:
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE, peer="8.8.8.8")),
            (
                "dvn-cloud-iqss.s3.amazonaws.com",
                Response(body=TAB, peer="1.1.1.1"),
            ),
        ]
    )

    def resolve(host: str) -> set[str]:
        return {"8.8.8.8"}

    with pytest.raises(DownloadRejected, match="public DNS answer"):
        download_bytes(API, client=client, resolve=resolve)


def test_later_redirect_off_approved_storage_is_rejected() -> None:
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE)),
            (
                "dvn-cloud-iqss.s3.amazonaws.com",
                Response(
                    status_code=302,
                    location="https://evil.example/steal.tab",
                ),
            ),
        ]
    )
    with pytest.raises(DownloadRejected, match="approved provider"):
        download_bytes(API, client=client, resolve=_public)


def test_too_many_redirects_are_rejected() -> None:
    hop = "https://dvn-cloud-iqss.s3.amazonaws.com/a"
    client = Client(
        [
            (API, Response(status_code=303, location=f"{hop}?n=1")),
            (f"{hop}?n=1", Response(status_code=302, location=f"{hop}?n=2")),
            (f"{hop}?n=2", Response(status_code=302, location=f"{hop}?n=3")),
            (f"{hop}?n=3", Response(status_code=302, location=f"{hop}?n=4")),
            (f"{hop}?n=4", Response(body=TAB)),
        ]
    )
    with pytest.raises(DownloadRejected, match="redirect limit"):
        download_bytes(API, client=client, resolve=_public)


def test_oversized_body_after_redirect_is_rejected_while_streaming(monkeypatch) -> None:
    from app import config

    monkeypatch.setattr(config.settings, "discovery_max_resource_bytes", 8)
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE)),
            (
                "dvn-cloud-iqss.s3.amazonaws.com",
                Response(body=b"0123456789abcdef", content_type="text/tab-separated-values"),
            ),
        ]
    )
    with pytest.raises(DownloadRejected, match="size limit"):
        download_bytes(API, client=client, resolve=_public)


def test_signed_storage_query_string_is_not_logged(caplog) -> None:
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE)),
            ("dvn-cloud-iqss.s3.amazonaws.com", Response(body=TAB)),
        ]
    )
    with caplog.at_level(logging.INFO, logger="app.ingestion.guard"):
        download_bytes(API, client=client, resolve=_public)
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "X-Amz-Signature" not in joined
    assert "secret" not in joined
    assert redacted_url(STORAGE).endswith("/10.7910/DVN/Z2V8DD/object")
    assert "X-Amz-Signature" not in redacted_url(STORAGE)


def test_html_body_after_approved_redirect_is_still_rejected() -> None:
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE)),
            (
                "dvn-cloud-iqss.s3.amazonaws.com",
                Response(
                    body=b"<!DOCTYPE html><html><body>login</body></html>",
                    content_type="text/html",
                ),
            ),
        ]
    )
    body, media = download_bytes(API, client=client, resolve=_public)
    with pytest.raises(DownloadRejected, match="HTML"):
        parse_table(
            body,
            filename="ita_senate_social.tab",
            declared_format="tab",
            content_type=media,
        )


def test_load_table_follows_approved_dataverse_redirect(monkeypatch) -> None:
    from app.api.schemas import DatasetRecord, DownloadResource
    from app.ingestion import retrieve

    resource = DownloadResource(
        url=API,
        format="tab",
        file_id="6988112",
        filename="ita_senate_social.tab",
        content_type="text/tab-separated-values",
        size_bytes=len(TAB),
        checksum="md5:abc",
        access_status="public",
        eligible=True,
    )
    record = DatasetRecord(
        id="dataverse:doi:10.7910/DVN/Z2V8DD",
        source="Harvard Dataverse",
        source_id="doi:10.7910/DVN/Z2V8DD",
        title="Political Institutions",
        landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/Z2V8DD",
        doi="doi:10.7910/DVN/Z2V8DD",
        source_version="1.0",
        download_resources=[resource],
        eligibility_status="supported_resource_verified",
    )
    monkeypatch.setattr(retrieve, "_resolve", lambda dataset_id, client: record)
    client = Client(
        [
            (API, Response(status_code=303, location=STORAGE)),
            ("dvn-cloud-iqss.s3.amazonaws.com", Response(body=TAB)),
        ]
    )
    verified_record, verified_resource, frame, inconclusive = load_table(
        "dataverse:doi:10.7910/DVN/Z2V8DD",
        "6988112",
        download_client=client,
        resolve=_public,
    )
    assert inconclusive is False
    assert verified_resource.file_id == "6988112"
    assert list(frame.columns) == ["id", "name"]
    assert verified_record.source_version == "1.0"
