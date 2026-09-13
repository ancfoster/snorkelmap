from django.db import migrations, models


def backfill(apps, schema_editor):
    """Fill the cache for locations that already have people on them.

    Written as one grouped query rather than a loop over locations, so
    that a database with a lot of listings in it is not a database with
    a lot of round trips in it.
    """
    SnorkelLocation = apps.get_model("snorkel_locations", "SnorkelLocation")
    Snorkelled = apps.get_model("locations_snorkelled", "Snorkelled")

    counts = (Snorkelled.objects
              .values("location_id")
              .annotate(total=models.Count("id")))
    for row in counts:
        SnorkelLocation.objects.filter(pk=row["location_id"]).update(
            users_snorkelled=row["total"])


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_locations", "0006_location_map_image"),
        ("locations_snorkelled", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="snorkellocation",
            name="users_snorkelled",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
