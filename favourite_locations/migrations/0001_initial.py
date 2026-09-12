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
            name="Favourite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="favourited_by",
                    to="snorkel_locations.snorkellocation")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="favourites",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "favourite",
                "verbose_name_plural": "favourites",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="favourite",
            index=models.Index(fields=["user", "-created_at"],
                               name="favourite_user_recent_idx"),
        ),
        migrations.AddConstraint(
            model_name="favourite",
            constraint=models.UniqueConstraint(
                fields=("user", "location"),
                name="unique_favourite_per_user_location"),
        ),
    ]
