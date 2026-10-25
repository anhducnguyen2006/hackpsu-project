"""HTTPS retrieval limited to provider APIs.

Redirects are followed one hop at a time. Each hop is checked again for scheme,
host, path, and a public DNS answer. The connected peer address must be one of
those public answers, which closes a DNS rebinding window between the check
and the connection.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import quote, urljoin, urlsplit

import httpx

from app.config import settings

class DownloadRejected(RuntimeError):
    """The URL or response is not a safe provider file download."""


_APPROVED = {
    "dataverse.harvard.edu": ("/api/access/datafile/",),
    "zenodo.org": ("/api/records/",),
}
_MAX_REDIRECTS = 3


def canonical_dataverse_url(file_id: str) -> str:
    if not file_id.isdigit():
        raise DownloadRejected("Dataverse file id must be the published numeric id.")
    return f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"


def canonical_zenodo_url(record_id: str, filename: str) -> str:
    if not record_id.isdigit():
        raise DownloadRejected("Zenodo record id must be the published numeric id.")
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        raise DownloadRejected("Zenodo file name is not a single published file key.")
    return f"https://zenodo.org/api/records/{record_id}/files/{quote(filename, safe='')}/content"


def validate_provider_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise DownloadRejected("Only HTTPS provider URLs without credentials are allowed.")
    if parsed.port not in {None, 443}:
        raise DownloadRejected("Provider downloads must use port 443.")
    host = (parsed.hostname or "").lower().rstrip(".")
    prefixes = _APPROVED.get(host)
    if prefixes is None or not any(parsed.path.startswith(prefix) for prefix in prefixes):
        raise DownloadRejected("Download URL is not on an approved provider API path.")
    if parsed.path.startswith("/api/access/datafile/"):
        file_id = parsed.path.removeprefix("/api/access/datafile/").split("/", 1)[0]
        if not file_id.isdigit():
            raise DownloadRejected("Dataverse file path is not a numeric file id.")


def assert_public_host(host: str) -> set[str]:
    """Resolve a host and reject any address that is not globally routable."""
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise DownloadRejected("Provider host did not resolve.") from error
    addresses = {str(item[4][0]).split("%", 1)[0] for item in answers}
    if not addresses:
        raise DownloadRejected("Provider host did not resolve.")
    for address in addresses:
        _assert_global(address)
    return addresses


def _assert_global(address: str) -> None:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise DownloadRejected("Provider address is not a valid IP.") from error
    mapped = getattr(parsed, "ipv4_mapped", None)
    if mapped is not None:
        parsed = mapped
    if not parsed.is_global:
        raise DownloadRejected("Provider address is not a public route.")


def _peer_address(response: httpx.Response) -> str | None:
    stream = response.extensions.get("network_stream")
    if stream is None:
        return None
    for key in ("server_addr", "peername"):
        peer = stream.get_extra_info(key)
        if isinstance(peer, tuple) and peer:
            return str(peer[0]).split("%", 1)[0]
    return None


def download_bytes(
    url: str,
    *,
    client: httpx.Client | None = None,
    resolve: Callable[[str], set[str]] = assert_public_host,
) -> tuple[bytes, str | None]:
    """Download one approved URL, revalidating every redirect."""
    owns_client = client is None
    http = client or httpx.Client(
        timeout=settings.external_request_timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    )
    current = url
    try:
        for _hop in range(_MAX_REDIRECTS + 1):
            validate_provider_url(current)
            host = urlsplit(current).hostname or ""
            allowed = resolve(host)
            response = http.get(current, headers={"Accept": "text/csv, text/tab-separated-values, text/plain, */*;q=0.1"})
            peer = _peer_address(response)
            if peer is None or peer not in allowed:
                raise DownloadRejected("Download connection did not match the public DNS answer.")
            _assert_global(peer)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise DownloadRejected("Provider redirect had no location.")
                current = urljoin(current, location)
                continue
            if response.status_code == 429:
                raise DownloadRejected("Provider rate limit reached (HTTP 429).")
            if response.status_code != 200:
                raise DownloadRejected(f"Provider returned HTTP {response.status_code}.")
            declared = response.headers.get("content-length")
            if isinstance(declared, str) and declared.isdigit() and int(declared) > settings.discovery_max_resource_bytes:
                raise DownloadRejected("Provider file exceeds the configured size limit.")
            return _bounded_body(response), _media(response.headers.get("content-type"))
        raise DownloadRejected("Provider redirect limit was reached.")
    finally:
        if owns_client:
            http.close()


def _media(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    media = value.split(";", 1)[0].strip().lower()
    return media or None


def _bounded_body(response: httpx.Response) -> bytes:
    limit = settings.discovery_max_resource_bytes
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > limit:
            raise DownloadRejected("Provider file exceeds the configured size limit.")
        chunks.append(chunk)
    if total == 0:
        raise DownloadRejected("Provider file was empty.")
    return b"".join(chunks)
