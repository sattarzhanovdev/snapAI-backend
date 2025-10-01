# api/services/social_verify.py

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Any, Iterable, Union

# --- Google ---
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as grequests

# --- Apple / JWT ---
import jwt
from jwt import PyJWKClient

# --- HTTP (иногда полезно для явных ошибок сети) ---
import requests

APPLE_ISS = "https://appleid.apple.com"
APPLE_JWKS_URL = f"{APPLE_ISS}/auth/keys"


# ---------- Google ----------
def verify_google_id_token(id_token: str, audience: str) -> Dict[str, Any]:
    """
    Возвращает dict с полями Google:
    sub, email, email_verified, given_name, family_name, picture, ...
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
@lru_cache(maxsize=1)
def _get_pyjwk_client() -> PyJWKClient:
    """
    Кэшируем PyJWKClient: он сам подтянет и будет переиспользовать ключи Apple.
    cache_clear() вызовется автоматически при обновлении кода процесса,
    а при явной необходимости можно очистить кэш вручную.
    """
    return PyJWKClient(APPLE_JWKS_URL, cache_keys=True)


def _aud_match(token_aud: Union[str, Iterable[str], None], expected: str) -> bool:
    if isinstance(token_aud, str):
        return token_aud == expected
    if isinstance(token_aud, (list, tuple, set)):
        return expected in token_aud
    return False


def verify_apple_id_token(identity_token: str, audience: str, *, verify_aud_in_decode: bool = True) -> Dict[str, Any]:
    """
    Верифицирует Apple ID token и возвращает claims.
    Делает:
      - Подпись по JWK Apple (PyJWKClient)
      - Проверку iss
      - Проверку aud (в decode или вручную — см. verify_aud_in_decode)
      - Допуск по времени (leeway=300)
      - Требует поля iss, sub, aud, exp, iat
    Явно бросает понятные ошибки при сбоях.
    """
    try:
        # 1) Получаем ключ для подписи из заголовка токена (kid) через PyJWKClient
        jwk_client = _get_pyjwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(identity_token).key

        # 2) Собираем опции декодирования
        options = {
            "require": ["iss", "sub", "aud", "exp", "iat"],
            "verify_aud": verify_aud_in_decode,
        }

        # 3) Декодирование JWT
        claims = jwt.decode(
            identity_token,
            key=signing_key,
            algorithms=["RS256"],
            issuer=APPLE_ISS,
            audience=audience if verify_aud_in_decode else None,
            options=options,
            leeway=300,  # 5 минут на расхождение часов
        )

        # 4) Явная проверка iss (на всякий случай; PyJWT уже проверил)
        iss = claims.get("iss")
        if iss != APPLE_ISS:
            raise ValueError(f"Invalid iss (issuer): {iss}")

        # 5) Ручная проверка aud при необходимости
        if not verify_aud_in_decode:
            token_aud = claims.get("aud")
            if not _aud_match(token_aud, audience):
                raise ValueError(f"aud mismatch: token aud={token_aud}, expected={audience}")

        return claims

    # ---- Нормализованные ошибки ----
    except jwt.ExpiredSignatureError:
        raise ValueError("Apple token expired")
    except jwt.InvalidIssuerError:
        raise ValueError("Invalid iss (issuer) for Apple token")
    except jwt.InvalidAudienceError as e:
        # Например: "Invalid audience"
        raise ValueError(f"aud mismatch: {e}")
    except jwt.InvalidSignatureError:
        raise ValueError("Invalid Apple token signature")
    except requests.RequestException as e:
        # Проблемы сети при обращении к JWKS
        raise ValueError(f"Network error fetching Apple JWKS: {e}")
    except Exception as e:
        # Прочие ошибки декодирования / формата
        raise ValueError(f"Apple token decode error: {e}")
