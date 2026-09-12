"""Give every country a slug for its URL segment.

Listings used to sit under the ISO code, /location/gb/..., and now sit
under the country's name, /location/united-kingdom/.... Same as Region
and Locale: a slug of the name, filled when the row is created.

Nothing needs doing to the listings themselves. A listing's address is
built on demand from its country, region and locale, and the detail
view finds a listing by its own slug, so links already saved under the
old code redirect to the new address rather than breaking.
"""
from django.db import migrations, models
from django.utils.text import slugify


def fill_slugs(apps, schema_editor):
    Country = apps.get_model("snorkel_locations", "Country")
    for country in Country.objects.all():
        country.slug = slugify(country.name) or slugify(country.code)
        country.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_locations", "0003_featured_image_and_geocode_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="country",
            name="slug",
            field=models.SlugField(default="", max_length=120),
            preserve_default=False,
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
    ]
