from rest_framework.views import APIView
from rest_framework import viewsets, permissions, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken
import hashlib, secrets
from django.conf import settings

# ====== SNAP AI: модели / сериализаторы / утилы ======
from .models import (
    UserProfile, Meal, NutritionPlan, AppRating,
    PendingSignup,       # <- OTP черновик регистрации
)
from .serializers import (
    UserProfileSerializer, MealSerializer,
    NutritionPlanSerializer, AppRatingSerializer,
    StartSignupSerializer, VerifySignupSerializer, ResendOTPSerializer,  # <- OTP сериализаторы
)
from .utils import plan_from_profile
from .services.openai_vision import analyze_image
from .services.emailer import send_otp_email_html  # простой email-отправитель
import base64, re

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
        """Сохраняем онбординг профиля (пошагово)."""
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

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NutritionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return NutritionPlan.objects.filter(user=self.request.user)

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
        """Пересчёт БЖУ/ккал при ручном редактировании."""
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

# views.py
class AnalyzePhoto(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        image_file = None

        # вариант 1 — если multipart (FormData)
        if "image" in request.FILES:
            image_file = request.FILES["image"]

        # вариант 2 — если base64
        elif request.data.get("image_base64"):
            img_str = request.data["image_base64"]
            # убрать префикс data:image/jpeg;base64,...
            match = re.match(r"data:image/(?P<ext>\w+);base64,(?P<data>.+)", img_str)
            if not match:
                return Response({"detail": "Invalid base64 format"}, status=400)

            ext = match.group("ext")
            data = match.group("data")

            try:
                img_bytes = base64.b64decode(data)
            except Exception:
                return Response({"detail": "Invalid base64 data"}, status=400)

            # сохранить как InMemoryUploadedFile
            from django.core.files.base import ContentFile
            image_file = ContentFile(img_bytes, name=f"upload.{ext}")

        if not image_file:
            return Response({"detail": "image is required"}, status=400)

        # создаём Meal
        meal = Meal.objects.create(
            user=request.user,
            title="",
            image=image_file,
            taken_at=now()
        )

        # запускаем AI-анализ
        result = analyze_image(meal.image)

        if not result:
            return Response({"detail": "AI analysis failed"}, status=502)

        # обновляем объект
        meal.title = result.get("title", "")
        meal.calories = result.get("calories", 0)
        meal.protein_g = result.get("protein_g", 0)
        meal.fat_g = result.get("fat_g", 0)
        meal.carbs_g = result.get("carbs_g", 0)
        meal.ingredients = result.get("ingredients", [])
        meal.meta = result.get("meta", {})
        meal.save()

        return Response(MealSerializer(meal).data, status=201)

# ================== AUTH: REGISTRATION WITH OTP ==================

import hashlib, secrets, random
from django.utils import timezone
from datetime import timedelta

def _hash_otp(code: str, salt: str) -> str:
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()

class StartSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = StartSignupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email    = ser.validated_data["email"]
        username = ser.validated_data["username"].strip()
        password = ser.validated_data["password"]

        # юзер с таким email/username уже есть?
        if User.objects.filter(username=username).exists():
            return Response({"detail": "Username already taken"}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({"detail": "User with this email already exists"}, status=400)

        # OTP как строка из 6 цифр (с ведущими нулями)
        otp = f"{random.randint(0, 999999):06d}"
        salt = secrets.token_hex(8)
        otp_hash = hashlib.sha256((otp + salt).encode("utf-8")).hexdigest()
        pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        ps = PendingSignup.objects.create(
            email=email,
            password_sha256=pwd_hash,
            otp_hash=otp_hash,
            otp_salt=salt,
            attempts=0,
            expires_at=timezone.now() + timedelta(minutes=10),
            locale="ru",
        )

        # Отправка HTML-письма
        try:
            send_otp_email_html(
                to=email,
                code=otp,
                ttl_minutes=10,
                locale="ru",
            )
            email_sent = True
        except Exception:
            email_sent = False

        # В DEV режиме помогаем тестить — подсказка/лог
        payload = {
            "session_id": str(ps.session_id),
            "email": email,
            "email_sent": email_sent,
            "ttl_seconds": 600,
        }
        if settings.DEBUG:
            payload["debug_hint"] = "DEBUG only: OTP printed in server log"
            print(f"[DEBUG] OTP for {email}: {otp}")

        return Response(payload, status=200)

class VerifySignupView(APIView):
    """
    POST /api/auth/register/verify/
    body: {session_id, otp, username, password}
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = VerifySignupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        session_id = ser.validated_data["session_id"]   # UUID
        otp        = str(ser.validated_data["otp"])     # строка "012345"
        username   = ser.validated_data["username"].strip()
        password   = ser.validated_data["password"]

        try:
            ps = PendingSignup.objects.get(session_id=session_id)
        except PendingSignup.DoesNotExist:
            return Response({"detail": "Invalid session"}, status=400)

        # TTL
        if timezone.now() > ps.expires_at:
            ps.delete()
            return Response({"detail": "OTP expired"}, status=400)

        # Лимит
        if ps.attempts >= 5:
            ps.delete()
            return Response({"detail": "Too many attempts"}, status=429)

        # Проверяем код
        calc = hashlib.sha256((otp + ps.otp_salt).encode("utf-8")).hexdigest()
        if not secrets.compare_digest(calc, ps.otp_hash):
            ps.attempts += 1
            ps.save(update_fields=["attempts"])
            return Response({"detail": "Invalid code"}, status=400)

        # username/email свободны прямо сейчас?
        if User.objects.filter(username=username).exists():
            return Response({"detail": "Username already taken"}, status=400)
        if User.objects.filter(email=ps.email).exists():
            return Response({"detail": "User with this email already exists"}, status=400)

        # пароль совпадает с тем, что присылали на start?
        if ps.password_sha256 != hashlib.sha256(password.encode("utf-8")).hexdigest():
            return Response({"detail": "Password mismatch with initial step"}, status=400)

        with transaction.atomic():
            user = User.objects.create_user(username=username, email=ps.email, password=password)
            UserProfile.objects.get_or_create(user=user)
            ps.delete()

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {"id": user.id, "username": user.username, "email": user.email},
        }, status=201)


class ResendOTPView(APIView):
    """
    POST /api/auth/register/resend/
    body: {session_id}
    """
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

        code = f"{random.randint(0, 999999):06d}"
        ps.otp_salt = secrets.token_hex(8)
        ps.otp_hash = hashlib.sha256((code + ps.otp_salt).encode()).hexdigest()
        ps.otp_sent_at = timezone.now()
        ps.resends += 1
        ps.save(update_fields=["otp_salt", "otp_hash", "otp_sent_at", "resends"])

        try:
            send_otp_email_html(ps.email, code, app_name="Snap AI")
        except Exception:
            return Response({"detail": "Failed to send OTP"}, status=502)

        return Response({"ok": True})
    
    
