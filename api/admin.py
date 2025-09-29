from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, UserProfile, NutritionPlan, Meal, AppRating, PendingSignup, PaymentReceiptIOS, Entitlement, Report


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ("id", "email", "is_active", "is_staff", "is_superuser", "date_joined", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser")
    ordering = ("-date_joined",)
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "is_staff", "is_superuser", "is_active"),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "gender", "units", "activity", "goal", "has_premium")
    search_fields = ("user__email",)


@admin.register(NutritionPlan)
class NutritionPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "calories", "protein_g", "fat_g", "carbs_g", "generated_at")
    search_fields = ("user__email",)


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "calories", "taken_at")
    search_fields = ("user__email", "title")


@admin.register(AppRating)
class AppRatingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "stars", "sent_to_store", "created_at")
    list_filter = ("sent_to_store", "stars")
    search_fields = ("user__email", "comment")


@admin.register(PendingSignup)
class PendingSignupAdmin(admin.ModelAdmin):
    list_display = ("session_id", "email", "otp_sent_at", "expires_at", "resends", "attempts", "created_at")
    search_fields = ("email",)
    readonly_fields = ("session_id", "otp_hash", "otp_salt", "created_at", "updated_at")



@admin.register(PaymentReceiptIOS)
class PaymentReceiptIOSAdmin(admin.ModelAdmin):
    list_display = ("user", "product_id", "original_transaction_id", "status", "expires_at", "created_at")
    search_fields = ("user__email", "original_transaction_id", "transaction_id", "product_id")
    list_filter = ("status",)

@admin.register(Entitlement)
class EntitlementAdmin(admin.ModelAdmin):
    list_display = ("user", "product_id", "is_active", "expires_at", "updated_at")
    search_fields = ("user__email", "product_id", "original_transaction_id")
    list_filter = ("is_active",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone_number", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "phone_number", "comment", "user__email")
    readonly_fields = ("created_at",)
