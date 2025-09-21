from rest_framework.views import APIView
from rest_framework import viewsets, permissions, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.timezone import now

from .models import UserProfile, Meal, NutritionPlan, AppRating
from .serializers import (
    UserProfileSerializer, MealSerializer,
    NutritionPlanSerializer, AppRatingSerializer,
)
from .utils import plan_from_profile
from .services.openai_vision import analyze_image

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None) or getattr(obj, "profile", None)
        return owner == request.user

class ProfileViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    @action(detail=False, methods=["post"], url_path="onboarding")
    def onboarding(self, request):
        """Сохраняем пошаговый онбординг профиля"""
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

class MealViewSet(viewsets.ModelViewSet):
    serializer_class = MealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meal.objects.filter(user=self.request.user).order_by("-taken_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="recompute")
    def recompute(self, request, pk=None):
        """Пересчёт БЖУ/ккал при смене servings или ручном редакте — фронт присылает новые значения"""
        meal = self.get_object()
        ser = self.get_serializer(meal, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NutritionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NutritionPlan.objects.filter(user=self.request.user)

class RatingViewSet(viewsets.ModelViewSet):
    serializer_class = AppRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AppRating.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        stars = int(self.request.data.get("stars", 0))
        sent = stars >= 4
        serializer.save(user=self.request.user, sent_to_store=sent)

# Технический endpoint: заглушка анализа фото (в реале — вызов GPT‑Vision)

class AnalyzePhoto(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file = request.FILES.get("image")
        if not file:
            return Response({"detail": "image is required"}, status=400)

        meal = Meal.objects.create(
            user=request.user,
            title="",
            image=file,
            taken_at=now()
        )

        image_url = request.build_absolute_uri(meal.image.url)
        result = analyze_image(file)  # не URL, а сам файл

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