from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import ProfileViewSet, MealViewSet, PlanViewSet, RatingViewSet, AnalyzePhoto, StartSignupView, VerifySignupView, ResendOTPView

router = DefaultRouter()
router.register(r"profile", ProfileViewSet, basename="profile")
router.register(r"meals", MealViewSet, basename="meals")
router.register(r"plan", PlanViewSet, basename="plan")
router.register(r"ratings", RatingViewSet, basename="ratings")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/register/start/", StartSignupView.as_view(), name="register_start"),
    path("auth/register/verify/", VerifySignupView.as_view(), name="register_verify"),
    path("auth/register/resend/", ResendOTPView.as_view(), name="register_resend"),
    path("analyze/", AnalyzePhoto.as_view(), name="analyze_stub"),
    path("", include(router.urls)),
]
