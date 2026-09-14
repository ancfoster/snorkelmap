"""A report is about a day, and there is one of them per person per day.

Two changes that belong together, because neither is much use alone.

observed_at becomes a date. It was a timestamp, but nobody reports the
minute they looked at the water, and the uniqueness rule underneath is
about days. Postgres casts timestamptz to date on its own here, so no
USING clause is needed; the time of day is dropped, which is the point.

Then the rule itself: one person may file as many reports about a
location as they like so long as each is for a different day. Written
as a unique index rather than checked in the form, because a form only
sees one request and the cases this guards against are two.

submitted_by is nullable, and Postgres treats nulls as distinct, so
reports left behind by deleted accounts do not collide with each other.
That is the behaviour wanted: they are nobody's now.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("snorkel_visibility", "0001_initial"),
    ]

    operations = [
        # The cached "most recent report" follows observed_at down to a
        # date, because it is a copy of one.
        migrations.AlterField(
            model_name="visibilitylocation",
            name="last_report_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="visibilityreport",
            name="observed_at",
            field=models.DateField(),
        ),
        migrations.AddConstraint(
            model_name="visibilityreport",
            constraint=models.UniqueConstraint(
                fields=["location", "submitted_by", "observed_at"],
                name="unique_visibility_report_per_day",
            ),
        ),
    ]
