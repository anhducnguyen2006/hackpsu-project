"""HTTPS retrieval limited to provider APIs and one Dataverse storage hop.

The initial URL must be a canonical Harvard Dataverse or Zenodo API path that
this process rebuilt from verified metadata. Clients never nominate a download
URL.

Harvard Dataverse may return a 303 Location to its published object store.
That storage hostname is not an initial API host. It is accepted only as a
server-supplied redirect after a successful Dataverse file-access hop, and only
when it exactly matches the configured storage host. Wildcard S3 trust is
rejected. Every hop still requires HTTPS, port 443, no userinfo, a public DNS
answer, and a connected peer in that answer set.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from collections.abc import Callable
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DownloadRejected(RuntimeError):
    """The URL or response is not a safe provider file download."""


_API_APPROVED = {
    "dataverse.harvard.edu": ("/api/access/datafile/",),
    "zenodo.org": ("/api/records/",),
}
_MAX_REDIRECTS = 3
_DATAVERSE_API_HOST = "dataverse.harvard.edu"


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


def redacted_url(url: str) -> str:
    """Strip query and fragment so signed storage URLs are never logged."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    netloc = host
    if parsed.port not in {None, 443}:
        netloc = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def validate_provider_url(url: str) -> None:
    """Accept only an initial approved repository API path."""
    _classify_url(url, allow_storage=False)


def _storage_hosts() -> frozenset[str]:
    return frozenset(
        host.strip().lower().rstrip(".")
        for host in settings.dataverse_storage_hosts.split(",")
        if host.strip()
    )


def _classify_url(url: str, *, allow_storage: bool) -> str:
    """Return ``api`` or ``storage`` after rejecting unsafe authorities."""
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise DownloadRejected("Only HTTPS provider URLs without credentials are allowed.")
    if parsed.username is not None or parsed.password is not None:
        raise DownloadRejected("Only HTTPS provider URLs without credentials are allowed.")
    netloc = parsed.netloc or ""
    if "@" in netloc:
        raise DownloadRejected("Only HTTPS provider URLs without credentials are allowed.")
    if parsed.port not in {None, 443}:
        raise DownloadRejected("Provider downloads must use port 443.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or "%" in host or host.startswith(".") or host.endswith("."):
        raise DownloadRejected("Download URL host is missing or malformed.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise DownloadRejected("Download URL must use an approved hostname, not a raw IP.")

    prefixes = _API_APPROVED.get(host)
    if prefixes is not None:
        if not any(parsed.path.startswith(prefix) for prefix in prefixes):
            raise DownloadRejected("Download URL is not on an approved provider API path.")
        if parsed.path.startswith("/api/access/datafile/"):
            file_id = parsed.path.removeprefix("/api/access/datafile/").split("/", 1)[0]
            if not file_id.isdigit():
                raise DownloadRejected("Dataverse file path is not a numeric file id.")
        return "api"

    if allow_storage and host in _storage_hosts():
        if not parsed.path or parsed.path == "/":
            raise DownloadRejected("Storage redirect path is missing.")
        return "storage"

    if host in _storage_hosts():
        raise DownloadRejected(
            "Dataverse object storage is not an initial download host."
        )
    raise DownloadRejected("Download URL is not on an approved provider API path.")


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
    allow_storage = False
    try:
        for _hop in range(_MAX_REDIRECTS + 1):
            kind = _classify_url(current, allow_storage=allow_storage)
            host = (urlsplit(current).hostname or "").lower().rstrip(".")
            allowed = resolve(host)
            response = http.get(
                current,
                headers={
                    "Accept": "text/csv, text/tab-separated-values, text/plain, */*;q=0.1"
                },
            )
            peer = _peer_address(response)
            if peer is None or peer not in allowed:
                raise DownloadRejected(
                    "Download connection did not match the public DNS answer."
                )
            _assert_global(peer)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise DownloadRejected("Provider redirect had no location.")
                # Storage trust is granted only by a Dataverse API hop Location.
                allow_storage = kind == "api" and host == _DATAVERSE_API_HOST
                if kind == "storage":
                    # A further hop must stay on the same exact storage host.
                    allow_storage = True
                current = urljoin(current, location)
                logger.info(
                    "provider_download event=redirect kind=%s next=%s",
                    kind,
                    redacted_url(current),
                )
                continue
            if response.status_code == 429:
                raise DownloadRejected("Provider rate limit reached (HTTP 429).")
            if response.status_code != 200:
                raise DownloadRejected(f"Provider returned HTTP {response.status_code}.")
            declared = response.headers.get("content-length")
            if (
                isinstance(declared, str)
                and declared.isdigit()
                and int(declared) > settings.discovery_max_resource_bytes
            ):
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
