import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_created_by(apps, schema_editor):
    """Give every listing the person who wrote its first revision.

    Until now `LocationRevision.created_by` carried both meanings,
    because there was only ever one revision. Now that there can be
    more than one, the question "who started this listing" belongs to
    the listing, and the answer is on its earliest revision.

    Done in one pass over the revisions with increment 0 rather than a
    query per listing.
    """
    SnorkelLocation = apps.get_model("snorkel_locations", "SnorkelLocation")
    LocationRevision = apps.get_model("snorkel_locations", "LocationRevision")

    first = LocationRevision.objects.filter(
        increment=0, created_by__isnull=False,
    ).values_list("location_id", "created_by_id")

    for location_id, user_id in first:
        SnorkelLocation.objects.filter(pk=location_id).update(
            created_by_id=user_id)


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_locations", "0007_users_snorkelled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="snorkellocation",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="locations_created",
                to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="snorkellocation",
            name="locked",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AddField(
            model_name="snorkellocation",
            name="locked_message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="locationrevision",
            name="featured_underwater_image",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="snorkel_locations.locationmedia"),
        ),
        migrations.AlterField(
            model_name="locationrevision",
            name="revision_comment",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.RunPython(backfill_created_by, migrations.RunPython.noop),
    ]
