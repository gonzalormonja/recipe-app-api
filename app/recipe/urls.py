"""
URL mappings for recipe APIs
"""

from django.urls import path, include

from rest_framework.routers import DefaultRouter

from recipe import views

router = DefaultRouter()
router.register("recipes", views.RecipeViewSet)
router.register("tags", views.TagViewSet)

# this is for reverse("->>>>>recipe<------:create")
app_name = "recipe"

urlpatterns = [path("", include(router.urls))]
