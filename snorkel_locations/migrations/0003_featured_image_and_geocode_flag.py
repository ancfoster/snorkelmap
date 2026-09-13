"""One featured image per revision, and a flag for a geocode that failed.

The revision previously carried two image fields. featured_underwater_image
is gone, and featured_surface_image is renamed to
featured_above_water_image: the picture that represents the location on
the map, in results, and at the top of its listing. Renamed rather than
dropped and recreated, so any row already pointing at a photograph keeps
doing so.

questionable_geocode marks a listing whose reverse geocode failed, as
opposed to one that genuinely has no country because it is open water.
The two produce the same empty result, and only one of them is correct.

Hand written, like 0002. Run

    python manage.py makemigrations snorkel_locations --check --dry-run

afterwards; it should report no changes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_locations", "0002_media_pipeline"),
    ]

    operations = [
        migrations.AddField(
            model_name="snorkellocation",
            name="questionable_geocode",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RemoveField(
            model_name="locationrevision",
            name="featured_underwater_image",
        ),
        migrations.RenameField(
            model_name="locationrevision",
            old_name="featured_surface_image",
            new_name="featured_above_water_image",
        ),
    ]
