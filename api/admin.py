from django.contrib import admin
from .models import UserProfile, NutritionPlan, Meal, AppRating

admin.site.register(UserProfile)
admin.site.register(NutritionPlan)
admin.site.register(Meal)
admin.site.register(AppRating)