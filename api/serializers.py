from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile, Meal, NutritionPlan, AppRating

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
    email = serializers.EmailField()
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(required=False, allow_blank=True, min_length=6)
    locale = serializers.CharField(required=False, allow_blank=True, max_length=10)

    def validate_email(self, value):
        value = value.lower().strip()
        # запрещаем, если такой email уже у User
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value

    def validate_username(self, value):
        v = value.strip()
        if v and User.objects.filter(username=v).exists():
            raise serializers.ValidationError("Username already taken")
        return v


# ─────────────────────────────────────────────────────────
# 2) Подтверждение кода
# body: { session_id, otp, username, password }
# На успех: создаётся User и возвращается JWT во view
# ─────────────────────────────────────────────────────────
class VerifySignupSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    otp = serializers.CharField(min_length=4, max_length=6)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=6)

    def validate_username(self, value):
        v = value.strip()
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError("Username already taken")
        return v


# ─────────────────────────────────────────────────────────
# 3) Повторная отправка кода
# body: { session_id }
# ─────────────────────────────────────────────────────────
class ResendOTPSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()