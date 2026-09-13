"""Fields the upload pipeline needs.

Written by hand rather than by makemigrations, so run

    python manage.py makemigrations snorkel_locations --check --dry-run

after applying it. That should report no changes; if it wants to
create something, this file and the models have drifted.
"""
import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_locations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="snorkellocation",
            name="submission_id",
            field=models.UUIDField(blank=True, db_index=True, editable=False,
                                   null=True, unique=True),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="mime_type",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="width",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="height",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="size_bytes",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="captured_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="captured_at_offset",
            field=models.CharField(blank=True, default="", max_length=6),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="captured_lat_long",
            field=django.contrib.gis.db.models.fields.PointField(
                blank=True, geography=True, null=True, srid=4326),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="sort_order",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="locationmedia",
            name="rejection_reason",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AlterField(
            model_name="locationmedia",
            name="status",
            field=models.PositiveSmallIntegerField(
                choices=[(0, "Pending upload"), (1, "Active"), (2, "Removed"),
                         (3, "Rejected"), (4, "Awaiting checks")],
                db_index=True, default=0),
        ),
        migrations.AlterModelOptions(
            name="locationmedia",
            options={"ordering": ["media_category", "sort_order", "created_at"],
                     "verbose_name_plural": "location media"},
        ),
        migrations.AddIndex(
            model_name="locationmedia",
            index=models.Index(fields=["location", "status"],
                               name="locmedia_loc_status_idx"),
        ),
    ]
