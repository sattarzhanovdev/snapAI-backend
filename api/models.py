from django.db import models
from django.contrib.auth.models import User

class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"

class UnitsSystem(models.TextChoices):
    METRIC = "metric", "Metric"  # kg, cm
    IMPERIAL = "imperial", "Imperial"  # lbs, ft/in

class ActivityLevel(models.TextChoices):
    SEDENTARY = "sedentary", "Sedentary"
    NORMAL = "normal", "Normal"
    ACTIVE = "active", "Active"

class GoalType(models.TextChoices):
    LOSE = "lose", "Lose weight"
    MAINTAIN = "maintain", "Maintain"
    GAIN = "gain", "Gain weight"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    gender = models.CharField(max_length=16, choices=Gender.choices, default=Gender.OTHER)
    date_of_birth = models.DateField(null=True, blank=True)

    # единицы/значения роста/веса при онбординге
    units = models.CharField(max_length=16, choices=UnitsSystem.choices, default=UnitsSystem.METRIC)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)

    activity = models.CharField(max_length=16, choices=ActivityLevel.choices, default=ActivityLevel.NORMAL)
    goal = models.CharField(max_length=16, choices=GoalType.choices, default=GoalType.MAINTAIN)
    desired_weight_kg = models.FloatField(null=True, blank=True)

    allergies = models.TextField(blank=True, default="")

    has_premium = models.BooleanField(default=False)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"

class NutritionPlan(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="plan")
    calories = models.IntegerField(default=0)
    protein_g = models.IntegerField(default=0)
    fat_g = models.IntegerField(default=0)
    carbs_g = models.IntegerField(default=0)
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Plan({self.user.username})"

class Meal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meals")
    taken_at = models.DateTimeField(auto_now_add=True)

    title = models.CharField(max_length=160, blank=True)
    image = models.ImageField(upload_to="uploads/meals/", blank=True, null=True)

    calories = models.IntegerField(default=0)
    protein_g = models.IntegerField(default=0)
    fat_g = models.IntegerField(default=0)
    carbs_g = models.IntegerField(default=0)
    servings = models.FloatField(default=1.0)

    # список ингредиентов и произвольные данные анализа (метки, health score)
    ingredients = models.JSONField(default=list, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Meal({self.user.username}, {self.title or 'untitled'})"

class AppRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    stars = models.IntegerField()  # 1..5
    comment = models.TextField(blank=True, default="")
    sent_to_store = models.BooleanField(default=False)  # если 4–5, фронт может попытаться отправить в стор
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rating({self.stars})"
    
    
import uuid
from django.db import models
from django.utils import timezone

class PendingSignup(models.Model):
    """
    Временная сессия регистрации по email-OTP.
    Совместимо с StartSignupView / VerifySignupView / ResendOTPView.
    """
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    email = models.EmailField()
    username = models.CharField(max_length=150, blank=True, default="")
    # Пароль храним как sha256 строки пароля (временное хранение до verify)
    password_sha256 = models.CharField(max_length=128, blank=True, default="")

    locale = models.CharField(max_length=10, blank=True, default="")

    # OTP хранится в виде hash(salt+code)
    otp_hash = models.CharField(max_length=128)
    otp_salt = models.CharField(max_length=32)
    otp_sent_at = models.DateTimeField(default=timezone.now)

    # TTL сессии/кода; выставляется во view при создании
    expires_at = models.DateTimeField()

    # Защита от брута/спама
    attempts = models.IntegerField(default=0)   # попытки ввода кода
    resends = models.IntegerField(default=0)    # количество переотправок

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["session_id"]),
            models.Index(fields=["expires_at"]),
        ]
        verbose_name = "Pending signup session"
        verbose_name_plural = "Pending signup sessions"

    def __str__(self):
        return f"PendingSignup<{self.email}> {self.session_id}"