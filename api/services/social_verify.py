# api/services/social_verify.py
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as grequests

import json, requests, jwt
from jwt import algorithms
from functools import lru_cache

APPLE_ISS = "https://appleid.apple.com"
APPLE_JWKS_URL = f"{APPLE_ISS}/auth/keys"


# ---------- Google ----------
def verify_google_id_token(id_token: str, audience: str) -> dict:
    """
    Возвращает dict с полями Google: sub, email, email_verified, given_name, family_name, picture, ...
    Бросает Exception, если токен некорректен.
    """
    info = google_id_token.verify_oauth2_token(
        id_token, grequests.Request(), audience
    )
    iss = info.get("iss")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        raise ValueError("Invalid issuer")
    return info


@lru_cache(maxsize=1)
def _get_apple_jwks():
    resp = requests.get(APPLE_JWKS_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return {k["kid"]: k for k in data.get("keys", [])}

def _get_apple_public_key(kid: str):
    jwks = _get_apple_jwks()
    key = jwks.get(kid)
    if not key:
        # refresh once in case of rotation
        _get_apple_jwks.cache_clear()
        jwks = _get_apple_jwks()
        key = jwks.get(kid)
    if not key:
        raise ValueError(f"Apple JWKS key not found for kid={kid}")
    return algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

def verify_apple_id_token(identity_token: str, audience: str, *, verify_aud_in_decode=True) -> dict:
    """
    Returns claims if valid; raises ValueError with a clear message otherwise.
    """
    try:
        header = jwt.get_unverified_header(identity_token)
    except Exception as e:
        raise ValueError(f"Invalid JWT header: {e}")

    kid = header.get("kid")
    if not kid:
        raise ValueError("Missing kid in Apple token header")

    pub_key = _get_apple_public_key(kid)

    # Allow slight clock skew (e.g., 5 minutes)
    options = {
        "require": ["iss", "sub", "aud", "exp", "iat"],
        "verify_aud": verify_aud_in_decode,  # we can also turn this off and check manually
    }

    try:
        claims = jwt.decode(
            identity_token,
            key=pub_key,
            algorithms=["RS256"],
            audience=[audience] if verify_aud_in_decode else None,
            issuer=APPLE_ISS,
            options=options,
            leeway=300,  # 5 minutes
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Apple token expired")
    except jwt.InvalidIssuerError:
        raise ValueError("Invalid iss (issuer) for Apple token")
    except jwt.InvalidAudienceError as e:
        raise ValueError(f"aud mismatch: {e}")
    except jwt.InvalidSignatureError:
        raise ValueError("Invalid Apple token signature")
    except Exception as e:
        raise ValueError(f"Apple token decode error: {e}")

    return claims