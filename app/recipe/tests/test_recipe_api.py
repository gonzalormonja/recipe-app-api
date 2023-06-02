"""
Tests for recipe APIs.
"""

from decimal import Decimal

import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag, Ingredient

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer

RECIPE_URL = reverse("recipe:recipe-list")


def image_upload_url(recipe_id):
    """Create and return an image upload URL."""
    return reverse("recipe:recipe-upload-image", args=[recipe_id])


def detail_url(recipe_id):
    """Create and return a recipe detail URL."""
    return reverse("recipe:recipe-detail", args=[recipe_id])


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


def create_user(email="user@example.com", password="password123"):
    """Create and return a user."""
    return get_user_model().objects.create_user(email, password)


def create_ingredient(user, name="ingredientName"):
    """Create and return a ingredient"""
    return Ingredient.objects.create(user=user, name=name)


class PublicRecipeAPITests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.get(RECIPE_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeAPITests(TestCase):
    """Test authenticated API request."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="root@example.com")
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes."""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.all().order_by("-id")
        # this is the expected response
        serializer = RecipeSerializer(recipes, many=True)

        self.assertTrue(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        """Test list of recipes is limited to authenticated user."""
        other_user = create_user()
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        """Test get recipe detail."""

        recipe = create_recipe(user=self.user)

        url = detail_url(recipe_id=recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        """Test creating a recipe."""
        payload = {
            "title": "Sample recipe",
            "time_minutes": 30,
            "price": Decimal("5.25"),
        }
        res = self.client.post(RECIPE_URL, payload)
        recipe = Recipe.objects.get(id=res.data["id"])
        for index, value in payload.items():
            self.assertEqual(getattr(recipe, index), value)

        self.assertEqual(recipe.user, self.user)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_partial_update(self):
        """Test partial update of a recipe."""
        original_link = "http://example.com/recipe.pdf"
        recipe = create_recipe(user=self.user, link=original_link)
        payload = {"title": "New recipe title"}
        url = detail_url(recipe_id=recipe.id)

        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload["title"])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        """Test full upddate of recipe."""
        recipe = create_recipe(
            user=self.user,
            title="title",
            link="https://link.com",
            description="description",
        )

        payload = {
            "title": "new title",
            "link": "https://link.com",
            "description": "description",
            "price": Decimal("5.6"),
            "time_minutes": 10,
        }

        url = detail_url(recipe.id)
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()

        for index, value in payload.items():
            self.assertEqual(getattr(recipe, index), value)

        self.assertEqual(recipe.user, self.user)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_update_user_returns_error(self):
        """Test changing the recipe user results in an error."""
        new_user = create_user()
        recipe = create_recipe(user=self.user)

        payload = {"user": new_user.id}

        url = detail_url(recipe.id)

        self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """Test deleting a recipe successful."""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_recipe_other_users_recipe_error(self):
        """Test trying to delete another users recipe gives error."""
        new_user = create_user()
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with a new tags"""

        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 30,
            "price": Decimal("4.2"),
            "tags": [
                {"name": "Thai"},
                {"name": "Dinner"},
            ],
        }

        res = self.client.post(RECIPE_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        for tag in payload["tags"]:
            exists = recipe.tags.filter(name=tag["name"], user=self.user).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_tag(self):
        """Test creating a recipe with existing tag."""
        tag_indian = Tag.objects.create(user=self.user, name="Indian")
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 30,
            "price": Decimal("4.2"),
            "tags": [
                {"name": tag_indian.name},
                {"name": "Dinner"},
            ],
        }

        res = self.client.post(RECIPE_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        for tag in payload["tags"]:
            exists = recipe.tags.filter(name=tag["name"], user=self.user).exists()
            self.assertTrue(exists)

    def test_create_tag_on_update(self):
        """Test creating tag when updating a recipe."""
        recipe = create_recipe(user=self.user)

        payload = {"tags": [{"name": "Launch"}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name="Launch")
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assigning an existing tag when updating a recipe"""
        recipe = create_recipe(user=self.user)
        tag_breakfast = Tag.objects.create(user=self.user, name="Breakfast")
        recipe.tags.add(tag_breakfast)

        tag_indian = Tag.objects.create(user=self.user, name="Indian")
        payload = {"tags": [{"name": tag_indian.name}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_indian, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_Tags(self):
        """Test clearing a recipe tags"""
        recipe = create_recipe(user=self.user)
        tag_breakfast = Tag.objects.create(user=self.user, name="Breakfast")
        tag_indian = Tag.objects.create(user=self.user, name="Indian")
        recipe.tags.add(tag_breakfast)
        recipe.tags.add(tag_indian)

        payload = {"tags": []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.all().count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        """Test creating a recipe with a new ingredients."""
        payload = {
            "title": "Sample recipe title",
            "time_minutes": 22,
            "price": Decimal("5.25"),
            "ingredients": [{"name": "ing1"}, {"name": "ing2"}],
        }
        res = self.client.post(RECIPE_URL, payload, format="json")
        recipe = Recipe.objects.get(id=res.data["id"])

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload["ingredients"]:
            exists = recipe.ingredients.filter(
                name=ingredient["name"], user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_ingredient(self):
        """Test creating a recipe with existing ingredient"""
        ingredient = create_ingredient(user=self.user)

        payload = {
            "title": "Sample recipe title",
            "time_minutes": 22,
            "price": Decimal("5.25"),
            "description": "Sample description",
            "link": "http://example.com/recipe.pdf",
            "ingredients": [{"name": ingredient.name}, {"name": "ing2"}],
        }
        res = self.client.post(RECIPE_URL, payload, format="json")

        recipe = Recipe.objects.get(id=res.data["id"])

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn(ingredient, recipe.ingredients.all())
        self.assertEqual(recipe.ingredients.count(), 2)

    def test_create_ingredient_on_update(self):
        """Test updating a recipe with a new ingredients"""
        recipe = create_recipe(user=self.user)
        old_ingredient = create_ingredient(user=self.user)
        recipe.ingredients.add()

        payload = {
            "ingredients": [{"name": "ing2"}],
        }
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        recipe.refresh_from_db()
        new_ingredient = Ingredient.objects.get(user=self.user, name="ing2")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 1)
        self.assertIn(new_ingredient, recipe.ingredients.all())
        self.assertNotIn(old_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test updating a recipe with a new ingredients"""
        recipe = create_recipe(user=self.user)
        old_ingredient = create_ingredient(user=self.user)
        recipe.ingredients.add()
        new_ingredient = create_ingredient(user=self.user, name="ing2")

        payload = {
            "ingredients": [{"name": new_ingredient.name}],
        }
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        recipe.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 1)
        self.assertIn(new_ingredient, recipe.ingredients.all())
        self.assertNotIn(old_ingredient, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(create_ingredient(user=self.user))

        payload = {"ingredients": []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        recipe.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)


class ImageUploadTests(TestCase):
    """Test for the image upload API."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(user=self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image(self):
        """Test upload an image to a recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as image_file:
            img = Image.new("RGB", (10, 10))
            img.save(image_file, format="JPEG")
            image_file.seek(0)
            payload = {"image": image_file}
            print(image_file)
            res = self.client.post(url, payload, format="multipart")

        print(res.data)
        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading invalid image."""
        url = image_upload_url(self.recipe.id)
        payload = {"image": "string"}
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
