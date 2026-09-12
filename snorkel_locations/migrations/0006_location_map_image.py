"""Somewhere to keep each location's map picture."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_locations", "0005_mapdata"),
    ]

    operations = [
        migrations.AddField(
            model_name="snorkellocation",
            name="map_image_key",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
