from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import ProfileViewSet, MealViewSet, PlanViewSet, RatingViewSet, AnalyzePhoto

router = DefaultRouter()
router.register(r"profile", ProfileViewSet, basename="profile")
router.register(r"meals", MealViewSet, basename="meals")
router.register(r"plan", PlanViewSet, basename="plan")
router.register(r"ratings", RatingViewSet, basename="ratings")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("analyze/", AnalyzePhoto.as_view(), name="analyze_stub"),
    path("", include(router.urls)),
]
