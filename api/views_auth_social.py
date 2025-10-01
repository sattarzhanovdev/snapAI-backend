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

class AppleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = SocialIDTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        id_token = ser.validated_data["id_token"]

        aud = "com.adconcept.snapai.ios"
        if not aud:
            msg = "Missing APPLE_CLIENT_ID in env"
            logger.error(msg)
            return Response({"detail": msg}, status=500 if settings.DEBUG else 400)

        try:
            claims = verify_apple_id_token(id_token, aud)
            iss = claims.get("iss")
            sub = claims["sub"]
            if iss != "https://appleid.apple.com":
                raise ValueError(f"Invalid iss: {iss}")
            if claims.get("aud") != aud:
                raise ValueError("aud mismatch")

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

            if settings.DEBUG:
                logger.warning("Apple ok: sub=%s aud=%s iss=%s email=%s created=%s",
                               sub, claims.get("aud"), iss, email, created)

            return Response(issue_jwt(user), status=201 if created else 200)

        except Exception as e:
            logger.exception("Apple login failed")
            detail = str(e) if settings.DEBUG else "Invalid Apple token"
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
