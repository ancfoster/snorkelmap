import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("snorkel_locations", "0005_mapdata"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="saved_by",
                    to="snorkel_locations.snorkellocation")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="saved_locations",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "saved location",
                "verbose_name_plural": "saved locations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="savedlocation",
            index=models.Index(fields=["user", "-created_at"],
                               name="saved_location_recent_idx"),
        ),
        migrations.AddConstraint(
            model_name="savedlocation",
            constraint=models.UniqueConstraint(
                fields=("user", "location"),
                name="unique_saved_location_per_user"),
        ),
    ]
