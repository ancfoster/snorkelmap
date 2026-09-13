import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("snorkel_locations", "0006_location_map_image"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LocationRating",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("average_rating", models.FloatField(blank=True, null=True)),
                ("number_of_reviews", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("location", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rating",
                    to="snorkel_locations.snorkellocation")),
            ],
            options={
                "verbose_name": "location rating",
                "verbose_name_plural": "location ratings",
            },
        ),
        migrations.CreateModel(
            name="Review",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("rating", models.PositiveSmallIntegerField(validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5)])),
                ("body", models.TextField(
                    blank=True, default="",
                    help_text="Optional. Plain text, up to 900 characters.",
                    validators=[django.core.validators.MaxLengthValidator(900)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="reviews",
                    to=settings.AUTH_USER_MODEL)),
                ("rating_for", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="reviews",
                    to="snorkel_reviews.locationrating")),
            ],
            options={
                "verbose_name": "review",
                "verbose_name_plural": "reviews",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(fields=["rating_for", "-created_at"],
                               name="review_recent_idx"),
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.UniqueConstraint(
                fields=("rating_for", "created_by"),
                name="unique_review_per_user_location"),
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_within_range"),
        ),
    ]
