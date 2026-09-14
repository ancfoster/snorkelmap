"""Turn user_type into a real integer column.

It was a CharField whose choices were integers and whose default was
the string "standard", which is not one of those choices. So the stored
values are "1" through "8" for anybody whose type was ever set, and
"standard" for everybody else.

Done in four steps rather than one AlterField, because Postgres will
not cast a varchar column to an integer on its own and Django does not
write the USING clause that would let it. A new column, filled from the
old one, then the old one dropped and the new one renamed into its
place: no cast, and nothing lost.
"""
from django.db import migrations, models

STANDARD = 4
LOWEST, HIGHEST = 1, 8


def to_numbers(apps, schema_editor):
    """Copy the old strings across as numbers.

    One UPDATE per type rather than a pass over every row. Anything
    that is not one of the eight — "standard", an empty string,
    whatever else has found its way in — is left at the default the
    new column was added with, which is Standard User. That is what
    those accounts already were.
    """
    User = apps.get_model("snorkelusers", "User")
    for number in range(LOWEST, HIGHEST + 1):
        User.objects.filter(user_type=str(number)).update(
            user_type_number=number)


def to_strings(apps, schema_editor):
    """And back again, if this is ever unwound."""
    User = apps.get_model("snorkelusers", "User")
    for number in range(LOWEST, HIGHEST + 1):
        User.objects.filter(user_type_number=number).update(
            user_type=str(number))


class Migration(migrations.Migration):

    dependencies = [
        ("snorkelusers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="user_type_number",
            field=models.PositiveSmallIntegerField(
                default=STANDARD,
                choices=[(1, "Snorkel Admin"), (2, "Moderator Level 1"),
                         (3, "Moderator Level 2"), (4, "Standard User"),
                         (5, "Standard User with restrictions"),
                         (6, "Read-only User"), (7, "Suspended User"),
                         (8, "Deleted User")]),
        ),
        migrations.RunPython(to_numbers, to_strings),
        migrations.RemoveField(model_name="user", name="user_type"),
        migrations.RenameField(
            model_name="user",
            old_name="user_type_number",
            new_name="user_type",
        ),
        # While we are here: an IntegerField whose default was the
        # string "1".
        migrations.AlterField(
            model_name="user",
            name="notification_level",
            field=models.IntegerField(default=1),
        ),
    ]
