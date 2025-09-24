from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile, Meal, NutritionPlan, AppRating
from django.contrib.auth.validators import UnicodeUsernameValidator

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "user", "gender", "date_of_birth", "units",
            "height_cm", "weight_kg", "activity", "goal",
            "desired_weight_kg", "allergies", "has_premium", "trial_ends_at",
            "created_at", "updated_at",
        ]

class NutritionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionPlan
        fields = ["calories", "protein_g", "fat_g", "carbs_g", "generated_at"]

class MealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meal
        read_only_fields = ["user", "taken_at"]
        fields = [
            "id", "title", "image", "calories", "protein_g", "fat_g", "carbs_g",
            "servings", "ingredients", "meta", "taken_at",
        ]

class AppRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppRating
        fields = ["id", "stars", "comment", "sent_to_store", "created_at"]
        
# ─────────────────────────────────────────────────────────
# 1) Старт регистрации (отправка OTP на email)
# body: { email, username?, password?, locale? }
# ─────────────────────────────────────────────────────────
class StartSignupSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    username = serializers.CharField(min_length=3, max_length=30, validators=[UnicodeUsernameValidator()])
    password = serializers.CharField(min_length=6, max_length=128, write_only=True)

class VerifySignupSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    otp        = serializers.RegexField(r"^\d{6}$", min_length=6, max_length=6)
    username   = serializers.CharField(min_length=3, max_length=30, validators=[UnicodeUsernameValidator()])
    password   = serializers.CharField(min_length=6, max_length=128, write_only=True)
# ─────────────────────────────────────────────────────────
# 3) Повторная отправка кода
# body: { session_id }
# ─────────────────────────────────────────────────────────
class ResendOTPSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()