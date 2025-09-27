# api/services/social_verify.py
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as grequests

import json, requests, jwt
from jwt import algorithms

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


# ---------- Apple ----------
def _get_apple_public_key(kid: str):
    jwks = requests.get(APPLE_JWKS_URL, timeout=10).json()["keys"]
    key = next(k for k in jwks if k["kid"] == kid)
    return algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

def verify_apple_id_token(identity_token: str, audience: str) -> dict:
    """
    Возвращает claims с полями: sub, email? (часто только в первый логин), email_verified, is_private_email.
    Бросает Exception, если токен некорректен.
    """
    header = jwt.get_unverified_header(identity_token)
    pub_key = _get_apple_public_key(header["kid"])
    claims = jwt.decode(
        identity_token,
        key=pub_key,
        algorithms=["RS256"],
        audience=audience,
        issuer=APPLE_ISS,
    )
    return claims
