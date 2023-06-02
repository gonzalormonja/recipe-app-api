"""
Test for the ingredient APIs.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient, Recipe

from recipe.serializers import IngredientSerializer


INGREDIENTS_URL = reverse("recipe:ingredient-list")


def detail_url(ingredient_id):
    """Create and return a ingredient detail url."""
    return reverse("recipe:ingredient-detail", args=[ingredient_id])


def create_ingredient(user, name="ingredientName"):
    """Create and return a ingredient"""
    return Ingredient.objects.create(user=user, name=name)


def create_user(email="user@example.com", password="password123"):
    """Create and return a user."""
    return get_user_model().objects.create_user(email, password)


def create_recipe(user, **params):
    """Create and return a sample recipe."""
    defaults = {
        "title": "Sample recipe title",
        "time_minutes": 22,
        "price": Decimal("5.25"),
        "description": "Sample description",
        "link": "http://example.com/recipe.pdf",
    }

    defaults.update(params)

    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


class PublicIngredientAPITest(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required for retrieving ingredients."""
        res = self.client.get(INGREDIENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientAPITest(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_ingredients(self):
        """Test retrieving a list of ingredients."""

        create_ingredient(self.user)
        create_ingredient(self.user, name="otherName")

        res = self.client.get(INGREDIENTS_URL)

        ingredients = Ingredient.objects.all().order_by("-name")
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(serializer.data, res.data)

    def test_ingredients_limited_to_user(self):
        """Test list of ingredients is limited to authenticated user."""
        create_ingredient(self.user)
        user2 = create_user(email="other@example.com")
        create_ingredient(user2, name="other name")

        res = self.client.get(INGREDIENTS_URL)

        ingredients = Ingredient.objects.filter(user=self.user).order_by("-name")
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(serializer.data, res.data)

    def test_update_ingredient(self):
        """Test updating a Ingredient"""
        ingredient = create_ingredient(user=self.user)

        payload = {"name": "otherName"}
        url = detail_url(ingredient_id=ingredient.id)
        res = self.client.patch(url, payload)

        ingredient.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for index, value in payload.items():
            self.assertEqual(getattr(ingredient, index), value)

    def test_delete_ingredient(self):
        """Test deleting a Ingredient"""
        ingredient = create_ingredient(user=self.user)

        url = detail_url(ingredient_id=ingredient.id)
        res = self.client.delete(url)

        ingredient_exists = Ingredient.objects.filter(id=ingredient.id).exists()

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ingredient_exists)

    def test_filter_ingredients_assigned_to_recipes(self):
        """Test listing ingredients by those assigned to recipes."""
        in1 = create_ingredient(user=self.user, name="ig1")
        in2 = create_ingredient(user=self.user, name="ig2")
        r1 = create_recipe(user=self.user, title="r1")
        r1.ingredients.add(in1)

        res = self.client.get(INGREDIENTS_URL, {"assigned_only": 1})

        s1 = IngredientSerializer(in1)
        s2 = IngredientSerializer(in2)
        self.assertIn(s1.data, res.data)
        self.assertNotIn(s2.data, res.data)

    def test_filter_ingredients_unique(self):
        """Test filtered ingredients returns a unique list."""
        in1 = create_ingredient(user=self.user, name="ig1")
        create_ingredient(user=self.user, name="ig2")
        r1 = create_recipe(user=self.user, title="r1")
        r2 = create_recipe(user=self.user, title="r2")
        r1.ingredients.add(in1)
        r2.ingredients.add(in1)

        res = self.client.get(INGREDIENTS_URL, {"assigned_only": 1})

        self.assertEqual(len(res.data), 1)
