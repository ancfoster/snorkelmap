"""Somewhere to record which map data file is current."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_locations", "0004_country_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="MapData",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("object_key", models.CharField(blank=True, default="",
                                                max_length=200)),
                ("size_bytes", models.PositiveIntegerField(default=0)),
                ("built_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"verbose_name_plural": "map data"},
        ),
    ]
