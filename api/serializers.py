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