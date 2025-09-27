from __future__ import annotations
import uuid
import hashlib
import secrets
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


# ========= Custom User (email-only) =========

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None  # <— убираем username
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self):
        return self.email


# ========= Enums =========

class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


class UnitsSystem(models.TextChoices):
    METRIC = "metric", "Metric"       # kg, cm
    IMPERIAL = "imperial", "Imperial" # lbs, ft/in


class ActivityLevel(models.TextChoices):
    SEDENTARY = "sedentary", "Sedentary"
    NORMAL = "normal", "Normal"
    ACTIVE = "active", "Active"


class GoalType(models.TextChoices):
    LOSE = "lose", "Lose weight"
    MAINTAIN = "maintain", "Maintain"
    GAIN = "gain", "Gain weight"


# ========= Core models =========

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    gender = models.CharField(max_length=16, choices=Gender.choices, default=Gender.OTHER)
    date_of_birth = models.DateField(null=True, blank=True)

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
        return f"Profile({self.user.email})"


class NutritionPlan(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plan")
    calories = models.IntegerField(default=0)
    protein_g = models.IntegerField(default=0)
    fat_g = models.IntegerField(default=0)
    carbs_g = models.IntegerField(default=0)
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Plan({self.user.email})"


class Meal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meals")
    taken_at = models.DateTimeField(auto_now_add=True)

    title = models.CharField(max_length=160, blank=True)
    image = models.ImageField(upload_to="uploads/meals/", blank=True, null=True)

    calories = models.IntegerField(default=0)
    protein_g = models.IntegerField(default=0)
    fat_g = models.IntegerField(default=0)
    carbs_g = models.IntegerField(default=0)
    servings = models.FloatField(default=1.0)

    ingredients = models.JSONField(default=list, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Meal({self.user.email}, {self.title or 'untitled'})"


class AppRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    stars = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, default="")
    sent_to_store = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rating({self.stars})"


# ========= Pending signup & OTP =========

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class PendingSignup(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    password_sha256 = models.CharField(max_length=64)

    otp_salt = models.CharField(max_length=32)
    otp_hash = models.CharField(max_length=64)
    otp_sent_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    attempts = models.PositiveIntegerField(default=0)
    resends = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Длина OTP по умолчанию — 4 (можно задать в .env OTP_LENGTH=4)
    OTP_LENGTH = int(os.getenv("OTP_LENGTH", 4))

    locale = models.CharField(max_length=8, default="ru")  # <-- дефолт

    def __str__(self):
        return f"{self.email} • {self.session_id}"

    # ----- helpers -----
    @staticmethod
    def make_otp(n: int | None = None) -> str:
        n = n or PendingSignup.OTP_LENGTH
        return "".join(secrets.choice("0123456789") for _ in range(n))

    @staticmethod
    def hash_otp(code: str, salt: str) -> str:
        return hashlib.sha256((code + salt).encode("utf-8")).hexdigest()

    @classmethod
    def new(cls, email: str, password_sha256: str, ttl_minutes: int = 10,
            otp_len: int | None = None, locale: str = "ru"):
        code = cls.make_otp(otp_len)
        salt = secrets.token_hex(8)
        otp_hash = cls.hash_otp(code, salt)
        obj = cls(
            email=email,
            password_sha256=password_sha256,
            otp_salt=salt,
            otp_hash=otp_hash,
            otp_sent_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
            locale=locale,  # <-- записали
        )
        obj.save()
        obj._raw_otp = code
        return obj
    
    def verify_and_consume(self, code: str) -> bool:
        """Проверяет код и инкрементит attempts. Возвращает True/False."""
        self.attempts += 1
        ok = (self.hash_otp(code, self.otp_salt) == self.otp_hash)
        self.save(update_fields=["attempts", "updated_at"])
        return ok