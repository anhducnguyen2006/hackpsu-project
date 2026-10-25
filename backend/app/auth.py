"""Auth0 access-token verification for protected API routes.

Tokens are verified with PyJWT against the tenant JWKS. Claim values are not
trusted until the signature, issuer, audience, and lifetime checks succeed.
This module never logs raw access tokens and never accepts an identity from a
request body or an unsigned header.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """The caller did not present a valid API access token."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AuthorizationError(Exception):
    """The token is valid but does not grant the required permission."""


class AuthConfigurationError(Exception):
    """Protected routes cannot run because Auth0 settings are incomplete."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    sub: str


class SigningKeySource(Protocol):
    def get_key(self, token: str) -> object: ...

    def refresh(self) -> None: ...


class JwksSigningKeys:
    """Bounded JWKS cache. A miss refreshes the set once so rotated keys work."""

    def __init__(self, url: str, lifespan_seconds: int) -> None:
        self.url = url
        self._lifespan_seconds = lifespan_seconds
        self._client = self._build()

    def _build(self) -> PyJWKClient:
        return PyJWKClient(
            self.url,
            cache_jwk_set=True,
            lifespan=self._lifespan_seconds,
            timeout=5,
            max_cached_keys=16,
        )

    def get_key(self, token: str) -> object:
        try:
            return self._client.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientError as error:
            raise LookupError("signing key") from error

    def refresh(self) -> None:
        self._client = self._build()


_signing_keys: SigningKeySource | None = None
_jwks: JwksSigningKeys | None = None


def install_signing_keys(source: SigningKeySource | None) -> None:
    """Replace JWKS lookup. Tests install a local key; production leaves this unset."""
    global _signing_keys
    _signing_keys = source


def auth_configured() -> bool:
    return bool(settings.auth0_domain.strip() and settings.auth0_audience.strip())


def expected_issuer() -> str:
    issuer = settings.auth0_issuer.strip()
    if issuer:
        return issuer if issuer.endswith("/") else f"{issuer}/"
    domain = (
        settings.auth0_domain.strip()
        .removeprefix("https://")
        .removeprefix("http://")
        .strip("/")
    )
    return f"https://{domain}/"


def jwks_url() -> str:
    return f"{expected_issuer()}.well-known/jwks.json"


def _key_source() -> SigningKeySource:
    global _jwks
    if _signing_keys is not None:
        return _signing_keys
    url = jwks_url()
    lifespan = max(60, int(settings.auth0_jwks_cache_seconds))
    if _jwks is None or _jwks.url != url:
        _jwks = JwksSigningKeys(url, lifespan)
    return _jwks


def _signing_key(token: str) -> object:
    source = _key_source()
    try:
        return source.get_key(token)
    except LookupError:
        source.refresh()
        try:
            return source.get_key(token)
        except LookupError as error:
            raise AuthenticationError("key") from error


def _reject_unexpected_algorithm(token: str) -> None:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise AuthenticationError("malformed") from error
    algorithm = header.get("alg")
    if algorithm != "RS256":
        raise AuthenticationError("algorithm")


def authenticate_token(token: str) -> AuthenticatedPrincipal:
    """Validate one access token and return its verified subject.

    The header algorithm is only used to reject unexpected algorithms. The
    signature is always checked as RS256 with a key from the trusted JWKS.
    """
    if not auth_configured():
        raise AuthConfigurationError()
    if not token or token.count(".") != 2:
        raise AuthenticationError("malformed")
    _reject_unexpected_algorithm(token)
    try:
        payload = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=settings.auth0_audience.strip(),
            issuer=expected_issuer(),
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
            },
            leeway=0,
        )
    except jwt.ExpiredSignatureError as error:
        raise AuthenticationError("expired") from error
    except jwt.ImmatureSignatureError as error:
        raise AuthenticationError("immature") from error
    except jwt.InvalidIssuerError as error:
        raise AuthenticationError("issuer") from error
    except jwt.InvalidAudienceError as error:
        raise AuthenticationError("audience") from error
    except jwt.InvalidSignatureError as error:
        raise AuthenticationError("signature") from error
    except jwt.InvalidAlgorithmError as error:
        raise AuthenticationError("algorithm") from error
    except jwt.PyJWTError as error:
        raise AuthenticationError("malformed") from error

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationError("subject")
    _require_scope(payload)
    return AuthenticatedPrincipal(sub=subject.strip())


def _require_scope(payload: dict) -> None:
    required = settings.auth0_required_scope.strip()
    if not required:
        return
    granted = set(str(payload.get("scope") or "").split())
    if required not in granted:
        raise AuthorizationError()


def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedPrincipal:
    """FastAPI dependency. Missing configuration fails closed with 503."""
    if not auth_configured():
        logger.warning("authentication rejected reason=not_configured")
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        logger.info("authentication rejected reason=missing")
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return authenticate_token(credentials.credentials)
    except AuthConfigurationError:
        logger.warning("authentication rejected reason=not_configured")
        raise HTTPException(status_code=503, detail="Authentication is not configured.") from None
    except AuthorizationError:
        logger.info("authentication rejected reason=forbidden")
        raise HTTPException(status_code=403, detail="You do not have permission for this action.") from None
    except AuthenticationError as error:
        logger.info("authentication rejected reason=%s", error.reason)
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
