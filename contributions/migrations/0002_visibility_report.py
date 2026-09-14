"""Visibility reports earn points too.

A fourth thing the ledger can point at, and the rule that stops any one
of them being paid for twice. Reports are paid per report rather than
per location, the same way edits are paid per revision: somebody who
snorkels the same bay every Saturday is telling us something new each
time, and the report table already limits them to one a day.

The kind column is widened because "visibility-report" is eighteen
characters and the column held twenty; that leaves no room for a longer
kind later, and widening a varchar in Postgres rewrites nothing.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contributions", "0001_initial"),
        ("snorkel_visibility", "0002_report_date_and_one_per_day"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contribution",
            name="kind",
            field=models.CharField(
                max_length=24,
                choices=[
                    ("location-creation", "Location created"),
                    ("location-edit", "Location edited"),
                    ("rating", "Rating left"),
                    ("review", "Review left"),
                    ("visibility-report", "Visibility report filed"),
                ],
            ),
        ),
        migrations.AddField(
            model_name="contribution",
            name="visibility_report",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contributions",
                to="snorkel_visibility.visibilityreport",
            ),
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.UniqueConstraint(
                fields=["user", "visibility_report"],
                condition=models.Q(kind="visibility-report"),
                name="unique_contribution_per_visibility_report",
            ),
        ),
    ]
