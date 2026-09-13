import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("snorkel_locations", "0006_location_map_image"),
        ("snorkel_reviews", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Contribution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=20, choices=[
                    ("location-creation", "Location created"),
                    ("location-edit", "Location edited"),
                    ("rating", "Rating left"),
                    ("review", "Review left"),
                ])),
                ("points", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contributions",
                    to="snorkel_locations.snorkellocation")),
                ("review", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contributions",
                    to="snorkel_reviews.review")),
                ("revision", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contributions",
                    to="snorkel_locations.locationrevision")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contributions",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "contribution",
                "verbose_name_plural": "contributions",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="contribution",
            index=models.Index(fields=["user", "-created_at"],
                               name="contribution_user_recent_idx"),
        ),
        migrations.AddIndex(
            model_name="contribution",
            index=models.Index(fields=["location"],
                               name="contribution_location_idx"),
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.UniqueConstraint(
                condition=models.Q(("kind", "location-creation")),
                fields=("user", "location"),
                name="unique_contribution_per_location_created"),
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.UniqueConstraint(
                condition=models.Q(("review__isnull", False)),
                fields=("user", "review", "kind"),
                name="unique_contribution_per_review"),
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.UniqueConstraint(
                condition=models.Q(("kind", "location-edit")),
                fields=("user", "revision"),
                name="unique_contribution_per_revision"),
        ),
    ]
