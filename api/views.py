from datetime import timedelta
import base64, re, hashlib, secrets, random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import now

from rest_framework import viewsets, permissions, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile, Meal, NutritionPlan, AppRating, PendingSignup
from .serializers import (
    UserProfileSerializer, MealSerializer, NutritionPlanSerializer, AppRatingSerializer,
    StartSignupSerializer, VerifySignupSerializer, ResendOTPSerializer,
)
from .utils import plan_from_profile
from .services.openai_vision import analyze_image
from .services.emailer import send_otp_email_html
import logging
logger = logging.getLogger(__name__)

User = get_user_model()


# ================== PERMISSIONS ==================

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None) or getattr(obj, "profile", None)
        return owner == request.user


# ================== PROFILE / PLAN ==================

class ProfileViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    @action(detail=False, methods=["post"], url_path="onboarding")
    def onboarding(self, request):
        profile = self.get_object()
        ser = self.get_serializer(profile, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    @action(detail=False, methods=["post"], url_path="generate-plan")
    def generate_plan(self, request):
        profile = self.get_object()
        data = plan_from_profile(profile)
        if not data:
            return Response({"detail": "Not enough data"}, status=400)
        with transaction.atomic():
            plan, _ = NutritionPlan.objects.get_or_create(user=request.user)
            for k, v in data.items():
                setattr(plan, k, v)
            plan.save()
        return Response(NutritionPlanSerializer(plan).data)


class PlanViewSet(viewsets.GenericViewSet):
    """
    /api/plan/        GET   -> вернуть текущий план пользователя (создать пустой, если нет)
    /api/plan/        PATCH -> частично обновить поля плана пользователя
    """
    serializer_class = NutritionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        plan, _ = NutritionPlan.objects.get_or_create(user=self.request.user)
        return plan

    @action(detail=False, methods=["get"], url_path="", url_name="get")
    def get_plan(self, request):
        plan = self.get_object()
        return Response(self.get_serializer(plan).data, status=200)

    @action(detail=False, methods=["patch"], url_path="", url_name="patch")
    def patch_plan(self, request):
        plan = self.get_object()
        ser = self.get_serializer(plan, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=200)


# ================== MEALS ==================

class MealViewSet(viewsets.ModelViewSet):
    serializer_class = MealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meal.objects.filter(user=self.request.user).order_by("-taken_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="recompute")
    def recompute(self, request, pk=None):
        meal = self.get_object()
        ser = self.get_serializer(meal, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


# ================== RATINGS ==================

class RatingViewSet(viewsets.ModelViewSet):
    serializer_class = AppRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AppRating.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        stars = int(self.request.data.get("stars", 0))
        sent = stars >= 4
        serializer.save(user=self.request.user, sent_to_store=sent)


# ================== AI ANALYZE ==================

class AnalyzePhoto(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        image_file = None

        # multipart
        if "image" in request.FILES:
            image_file = request.FILES["image"]

        # base64
        elif request.data.get("image_base64"):
            img_str = request.data["image_base64"]
            match = re.match(r"data:image/(?P<ext>\w+);base64,(?P<data>.+)", img_str)
            if not match:
                return Response({"detail": "Invalid base64 format"}, status=400)

            ext = match.group("ext")
            data = match.group("data")

            try:
                img_bytes = base64.b64decode(data)
            except Exception:
                return Response({"detail": "Invalid base64 data"}, status=400)

            from django.core.files.base import ContentFile
            image_file = ContentFile(img_bytes, name=f"upload.{ext}")

        if not image_file:
            return Response({"detail": "image is required"}, status=400)

        meal = Meal.objects.create(user=request.user, title="", image=image_file, taken_at=now())
        result = analyze_image(meal.image)

        if not result:
            return Response({"detail": "AI analysis failed"}, status=502)

        meal.title = result.get("title", "")
        meal.calories = result.get("calories", 0)
        meal.protein_g = result.get("protein_g", 0)
        meal.fat_g = result.get("fat_g", 0)
        meal.carbs_g = result.get("carbs_g", 0)
        meal.ingredients = result.get("ingredients", [])
        meal.meta = result.get("meta", {})
        meal.save()

        return Response(MealSerializer(meal).data, status=201)


# ================== AUTH: REGISTRATION WITH OTP (email-only) ==================

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class StartSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = StartSignupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        password = ser.validated_data["password"]

        if User.objects.filter(email=email).exists():
            return Response({"detail": "User with this email already exists"}, status=400)

        # возьмём локаль из тела (если пришла) или из заголовка, иначе ru
        locale = (request.data.get("locale")
                  or request.headers.get("Accept-Language", "ru"))[:8] or "ru"

        ps = PendingSignup.new(
            email=email,
            password_sha256=_sha256(password),
            ttl_minutes=10,
            locale=locale,  # <-- передали
        )

        try:
            email_sent = send_otp_email_html(email=email, otp=ps._raw_otp, ttl_minutes=10)
        except Exception:
            logger.exception("OTP email send failed")
            email_sent = False

        payload = {
            "session_id": str(ps.session_id),
            "email": email,
            "email_sent": email_sent,
            "ttl_seconds": 600,
        }
        if settings.DEBUG:
            payload["debug_hint"] = "DEBUG only: OTP printed in server log"
            print(f"[DEBUG] OTP for {email}: {ps._raw_otp}")

        return Response(payload, status=200)


class VerifySignupView(APIView):
    """
    POST /api/auth/register/verify/
    body: { session_id, otp, password }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = VerifySignupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        session_id = ser.validated_data["session_id"]
        otp = str(ser.validated_data["otp"])
        password = ser.validated_data["password"]

        try:
            ps = PendingSignup.objects.get(session_id=session_id)
        except PendingSignup.DoesNotExist:
            return Response({"detail": "Invalid session"}, status=400)

        if timezone.now() > ps.expires_at:
            ps.delete()
            return Response({"detail": "OTP expired"}, status=400)

        if ps.attempts >= 5:
            ps.delete()
            return Response({"detail": "Too many attempts"}, status=429)

        if not ps.verify_and_consume(otp):
            return Response({"detail": "Invalid code"}, status=400)

        if _sha256(password) != ps.password_sha256:
            return Response({"detail": "Password mismatch with initial step"}, status=400)

        if User.objects.filter(email=ps.email).exists():
            # гонка: кто-то уже зарегался на этот email
            ps.delete()
            return Response({"detail": "User with this email already exists"}, status=400)

        with transaction.atomic():
            user = User.objects.create_user(email=ps.email, password=password)
            UserProfile.objects.get_or_create(user=user)
            ps.delete()

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {"id": user.id, "email": user.email},
        }, status=201)


class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = ResendOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sid = ser.validated_data["session_id"]

        try:
            ps = PendingSignup.objects.get(session_id=sid)
        except PendingSignup.DoesNotExist:
            return Response({"detail": "Invalid session"}, status=400)

        if timezone.now() > ps.expires_at:
            return Response({"detail": "OTP expired"}, status=400)

        if ps.resends >= 3:
            return Response({"detail": "Resend limit reached"}, status=429)

        # Сколько осталось жить коду — передадим в письмо
        ttl_seconds_left = int((ps.expires_at - timezone.now()).total_seconds())
        ttl_minutes_left = max(1, ttl_seconds_left // 60)

        # Генерируем новый код и сохраняем
        code = PendingSignup.make_otp(4)
        ps.otp_salt = secrets.token_hex(8)
        ps.otp_hash = PendingSignup.hash_otp(code, ps.otp_salt)
        ps.otp_sent_at = timezone.now()
        ps.resends += 1
        ps.save(update_fields=["otp_salt", "otp_hash", "otp_sent_at", "resends", "updated_at"])

        # ВАЖНО: без locale
        try:
            ok = send_otp_email_html(email=ps.email, otp=code, ttl_minutes=ttl_minutes_left)
            if not ok:
                # на всякий случай логируем
                logger.error("send_otp_email_html returned False for %s", ps.email)
                return Response({"detail": "Failed to send OTP"}, status=502)
        except Exception as e:
            logger.exception("Resend OTP failed")
            payload = {"detail": "Failed to send OTP"}
            if settings.DEBUG:
                payload["debug_hint"] = str(e)
            return Response(payload, status=502)

        resp = {
            "ok": True,
            "ttl_seconds_left": ttl_seconds_left,
            "resends_used": ps.resends,
            "resends_left": max(0, 3 - ps.resends),
        }
        if settings.DEBUG:
            resp["debug_hint"] = "OTP re-sent (check email/logs)"

        return Response(resp, status=200)