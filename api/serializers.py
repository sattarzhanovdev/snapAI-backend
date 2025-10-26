from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import UserProfile, Meal, NutritionPlan, AppRating, PendingSignup, Report

User = get_user_model()


# ===== User / Profile / Plan / Meal / Rating =====

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id", "user", "gender", "date_of_birth", "units",
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


# ===== OTP Signup flow (email-only) =====

OTP_LENGTH = 4

class StartSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, max_length=128, write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("User with this email already exists")
        validate_password(attrs["password"])
        return attrs


class VerifySignupSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    otp = serializers.RegexField(fr"^\d{{{OTP_LENGTH}}}$")
    password = serializers.CharField(min_length=6)
    
class ResendOTPSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()


class SocialIDTokenSerializer(serializers.Serializer):
    id_token = serializers.CharField()
    

class IOSReceiptInSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=128)
    original_transaction_id = serializers.CharField(max_length=128)
    transaction_id = serializers.CharField(max_length=128, required=False, allow_blank=True)
    bundle_id = serializers.CharField(max_length=256, required=False, allow_blank=True)
    app_account_token = serializers.CharField(max_length=64, required=False, allow_blank=True)
    raw_payload = serializers.JSONField(required=False)
    
    
class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("id", "user", "name", "comment", "photo", "created_at")
        read_only_fields = ("id", "user", "created_at")