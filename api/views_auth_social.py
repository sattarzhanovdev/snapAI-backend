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
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class GoogleLoginView(APIView):
    """
    POST /api/auth/google/
    body: { "id_token": "<Google ID Token>" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser = SocialIDTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        id_token = ser.validated_data["id_token"]

        try:
            info = verify_google_id_token(id_token, os.getenv("GOOGLE_CLIENT_ID"))
            sub = info["sub"]
            email = (info.get("email") or "").lower().strip()
            first_name = info.get("given_name", "")
            last_name = info.get("family_name", "")

            user = None
            if email:
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={"first_name": first_name, "last_name": last_name},
                )
            else:
                # редкий случай: email не пришёл — создаём по sub с технич. email
                tech_email = f"google_{sub}@example.invalid"
                user, created = User.objects.get_or_create(email=tech_email)

            # опционально зафиксируем провайдера у пользователя (если есть такие поля)
            if hasattr(user, "provider") and hasattr(user, "provider_sub"):
                update = False
                if user.provider != "google":
                    user.provider = "google"; update = True
                if getattr(user, "provider_sub", "") != sub:
                    user.provider_sub = sub; update = True
                if update:
                    user.save(update_fields=["provider", "provider_sub"])

            return Response(issue_jwt(user), status=200)

        except Exception as e:
            logger.exception("Google login failed")
            detail = str(e) if settings.DEBUG else "Invalid Google token"
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class AppleLoginView(APIView):
    """
    POST /api/auth/apple/
    body: { "id_token": "<Apple Identity Token>" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser = SocialIDTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        identity_token = ser.validated_data["id_token"]

        try:
            claims = verify_apple_id_token(identity_token, os.getenv("APPLE_CLIENT_ID"))
            sub = claims["sub"]
            email = (claims.get("email") or "").lower().strip()

            user = None
            if email:
                user, _ = User.objects.get_or_create(email=email)
            else:
                tech_email = f"apple_{sub}@example.invalid"
                user, _ = User.objects.get_or_create(email=tech_email)

            if hasattr(user, "provider") and hasattr(user, "provider_sub"):
                update = False
                if user.provider != "apple":
                    user.provider = "apple"; update = True
                if getattr(user, "provider_sub", "") != sub:
                    user.provider_sub = sub; update = True
                if update:
                    user.save(update_fields=["provider", "provider_sub"])

            return Response(issue_jwt(user), status=200)

        except Exception as e:
            logger.exception("Apple login failed")
            detail = str(e) if settings.DEBUG else "Invalid Apple token"
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
