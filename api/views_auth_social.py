# api/views_auth_social.py
import os, logging
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import SocialIDTokenSerializer
from .services.social_verify import verify_google_id_token, verify_apple_id_token
import base64, hashlib
from jwt import ExpiredSignatureError, InvalidIssuerError, InvalidAudienceError, InvalidSignatureError

logger = logging.getLogger(__name__)
User = get_user_model()

def issue_jwt(user) -> dict:
    r = RefreshToken.for_user(user)
    return {"access": str(r.access_token), "refresh": str(r)}

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = SocialIDTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        id_token = ser.validated_data["id_token"]

        aud = os.getenv("GOOGLE_CLIENT_ID")
        if not aud:
            msg = "Missing GOOGLE_CLIENT_ID in env"
            logger.error(msg)
            return Response({"detail": msg}, status=500 if settings.DEBUG else 400)

        try:
            info = verify_google_id_token(id_token, aud)
            iss = info.get("iss")
            sub = info["sub"]
            if iss not in ("https://accounts.google.com", "accounts.google.com"):
                raise ValueError(f"Invalid iss: {iss}")
            if info.get("aud") != aud:
                raise ValueError("aud mismatch")

            email = (info.get("email") or "").lower().strip()
            first_name = info.get("given_name", "")
            last_name = info.get("family_name", "")

            created = False
            if email:
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={"first_name": first_name, "last_name": last_name},
                )
            else:
                # без email — технич. адрес
                user, created = User.objects.get_or_create(email=f"google_{sub}@example.invalid")

            if hasattr(user, "provider") and hasattr(user, "provider_sub"):
                to_update = []
                if getattr(user, "provider", "") != "google":
                    user.provider = "google"; to_update.append("provider")
                if getattr(user, "provider_sub", "") != sub:
                    user.provider_sub = sub; to_update.append("provider_sub")
                if to_update:
                    user.save(update_fields=to_update)

            if settings.DEBUG:
                logger.warning("Google ok: sub=%s aud=%s iss=%s email=%s created=%s",
                               sub, info.get("aud"), iss, email, created)

            return Response(issue_jwt(user), status=201 if created else 200)

        except Exception as e:
            logger.exception("Google login failed")
            detail = str(e) if settings.DEBUG else "Invalid Google token"
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _sha256_b64url(s: str) -> str:
    d = hashlib.sha256(s.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode("ascii")

class AppleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = SocialIDTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        id_token = ser.validated_data["id_token"]

        raw_nonce = (request.data.get("nonce") or "").strip()
        aud = "com.adconcept.snapai.ios"

        try:
            # 1) Проверим подпись+issuer внутри verify_apple_id_token,
            #    НО audience вручную, чтобы отдать понятную ошибку
            claims = verify_apple_id_token(id_token, aud, verify_aud_in_decode=False)

            # 2) iss
            iss = claims.get("iss")
            if iss != "https://appleid.apple.com":
                return Response({"detail": f"Invalid issuer: {iss}"}, status=400)

            # 3) aud (str или list)
            token_aud = claims.get("aud")
            aud_ok = (token_aud == aud) if isinstance(token_aud, str) else (
                isinstance(token_aud, (list, tuple, set)) and aud in token_aud
            )
            if not aud_ok:
                return Response({"detail": f"aud mismatch: token aud={token_aud}, expected={aud}"}, status=400)

            # 4) nonce — примем и hex, и base64url
            if raw_nonce:
                token_nonce = (claims.get("nonce") or "").strip()
                exp_hex = _sha256_hex(raw_nonce)
                exp_b64 = _sha256_b64url(raw_nonce)
                if token_nonce not in (exp_hex, exp_b64):
                    return Response({
                        "detail": "nonce mismatch",
                        "token_nonce": token_nonce,
                        "expected_hex": exp_hex,
                        "expected_b64url": exp_b64,
                    }, status=400)

            # 5) user
            sub = claims.get("sub")
            if not sub:
                return Response({"detail": "Missing sub in Apple token"}, status=400)

            email = (claims.get("email") or "").lower().strip()
            created = False
            if email:
                user, created = User.objects.get_or_create(email=email)
            else:
                user, created = User.objects.get_or_create(email=f"apple_{sub}@example.invalid")

            if hasattr(user, "provider") and hasattr(user, "provider_sub"):
                to_update = []
                if getattr(user, "provider", "") != "apple":
                    user.provider = "apple"; to_update.append("provider")
                if getattr(user, "provider_sub", "") != sub:
                    user.provider_sub = sub; to_update.append("provider_sub")
                if to_update:
                    user.save(update_fields=to_update)

            return Response(issue_jwt(user), status=201 if created else 200)

        except ExpiredSignatureError:
            return Response({"detail": "Apple token expired"}, status=400)
        except InvalidIssuerError:
            return Response({"detail": "Invalid Apple token issuer"}, status=400)
        except InvalidAudienceError as e:
            return Response({"detail": f"aud mismatch: {e}"}, status=400)
        except InvalidSignatureError:
            return Response({"detail": "Invalid Apple token signature"}, status=400)
        except Exception as e:
            logger.exception("Apple login failed")
            # На время отладки покажем точную причину:
            return Response({"detail": f"{type(e).__name__}: {e}"}, status=400)