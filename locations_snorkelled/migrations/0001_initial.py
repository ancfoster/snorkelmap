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
            name="Snorkelled",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="snorkelled_by",
                    to="snorkel_locations.snorkellocation")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="snorkelled",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "snorkelled location",
                "verbose_name_plural": "snorkelled locations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="snorkelled",
            index=models.Index(fields=["user", "-created_at"],
                               name="snorkelled_user_recent_idx"),
        ),
        migrations.AddIndex(
            model_name="snorkelled",
            index=models.Index(fields=["location"],
                               name="snorkelled_location_idx"),
        ),
        migrations.AddConstraint(
            model_name="snorkelled",
            constraint=models.UniqueConstraint(
                fields=("user", "location"),
                name="unique_snorkelled_per_user_location"),
        ),
    ]
