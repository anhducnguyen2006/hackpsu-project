"""Local RSA fixtures for Auth0 access-token tests. No network and no live JWKS."""

from __future__ import annotations

import base64
import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://test.example.auth0.com/"
AUDIENCE = "https://dataopedia.test/api"
KID = "test-key-1"

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key = private_key.public_key()
other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class TestKeyStore:
    def __init__(self) -> None:
        self.keys = {KID: public_key}
        self.refresh_count = 0
        self.fail_until_refresh = False

    def get_key(self, token: str) -> object:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if self.fail_until_refresh and self.refresh_count == 0:
            raise LookupError(kid or "missing")
        if kid not in self.keys:
            raise LookupError(kid or "missing")
        return self.keys[kid]

    def refresh(self) -> None:
        self.refresh_count += 1


def token(
    sub: str = "auth0|user-a",
    *,
    aud: str = AUDIENCE,
    iss: str = ISSUER,
    exp: int | None = None,
    nbf: int | None = None,
    iat: int | None = None,
    kid: str = KID,
    algorithm: str = "RS256",
    private: object = private_key,
    scope: str | None = None,
    include_sub: bool = True,
) -> str:
    now = int(time.time())
    payload: dict[str, object] = {
        "iss": iss,
        "aud": aud,
        "iat": now - 10 if iat is None else iat,
        "exp": now + 600 if exp is None else exp,
    }
    if include_sub:
        payload["sub"] = sub
    if nbf is not None:
        payload["nbf"] = nbf
    if scope is not None:
        payload["scope"] = scope
    return jwt.encode(payload, private, algorithm=algorithm, headers={"kid": kid})


def bearer(sub: str = "auth0|user-a", **kwargs: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(sub, **kwargs)}"}


def unsigned_token() -> str:
    header = _b64({"alg": "none", "typ": "JWT"})
    payload = _b64(
        {
            "sub": "auth0|user-a",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": int(time.time()) - 10,
            "exp": int(time.time()) + 600,
        }
    )
    return f"{header}.{payload}."


def _b64(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
