"""
Serializer for recipe APIs
"""

from rest_framework import serializers

from core.models import Recipe, Tag


class TagSerializer(serializers.ModelSerializer):
    """Serializer for tags."""

    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
        ]
        read_only_fields = ["id"]


class RecipeSerializer(serializers.ModelSerializer):
    """Serializer for recipes."""

    tags = TagSerializer(many=True, required=False)

    class Meta:
        model = Recipe
        fields = ["id", "title", "time_minutes", "price", "link", "tags"]
        read_only_fields = ["id"]

    def __get_or_create_tags(self, instance, tags):
        auth_user = self.context["request"].user

        for tag in tags:
            tag_obj, created = Tag.objects.get_or_create(user=auth_user, **tag)
            instance.tags.add(tag_obj)

    def create(self, validate_data):
        """Create a recipe."""
        tags = validate_data.pop("tags", [])
        recipe = Recipe.objects.create(**validate_data)
        self.__get_or_create_tags(recipe, tags)

        return recipe

    def update(self, instance, validate_data):
        """Update a Recipe"""
        tags = validate_data.pop("tags", None)

        if tags is not None:
            instance.tags.clear()
            self.__get_or_create_tags(instance, tags)

        for attr, value in validate_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class RecipeDetailSerializer(RecipeSerializer):
    """Serializer for recipe detail view."""

    class Meta(RecipeSerializer.Meta):
        fields = RecipeSerializer.Meta.fields + ["description"]
