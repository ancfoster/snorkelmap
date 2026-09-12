"""Draw the map picture for any location that has not got one.

Listings get theirs when they are created, but that request swallows
its own failures so that a slow Mapbox or an unreachable bucket can
never stop somebody publishing. This is how those get filled in, and
how the locations that existed before the field did get theirs.

    manage.py generate_map_images                  only the ones missing
    manage.py generate_map_images --force          redraw everything
    manage.py generate_map_images --limit 10       a few at a time
    manage.py generate_map_images --dry-run        say what it would do

One Mapbox request per location, so --limit is worth using the first
time if there are a lot of them.
"""
from django.core.management.base import BaseCommand

from snorkel_locations import static_map
from snorkel_locations.models import SnorkelLocation


class Command(BaseCommand):
    help = "Generate and store the Mapbox map picture for locations."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Redraw locations that already have one.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after this many. 0 means all of them.")
        parser.add_argument("--dry-run", action="store_true",
                            help="List what would be drawn and change nothing.")

    def handle(self, *args, **options):
        rows = SnorkelLocation.objects.exclude(lat_long=None)
        if not options["force"]:
            rows = rows.filter(map_image_key="")
        rows = rows.order_by("id")
        if options["limit"]:
            rows = rows[:options["limit"]]

        total = rows.count()
        if not total:
            self.stdout.write("Every location already has a map picture.")
            return

        if options["dry_run"]:
            for location in rows:
                self.stdout.write(f"would draw {location.uuid}  {location.slug}")
            self.stdout.write(f"\n{total} location(s), no changes made")
            return

        drawn = failed = 0
        for location in rows:
            key = static_map.generate_for(location, force=options["force"])
            if key:
                drawn += 1
                self.stdout.write(f"  {location.slug}  ->  {key}")
            else:
                failed += 1
                self.stderr.write(self.style.WARNING(
                    f"  {location.slug}  ->  failed, see the log"))

        self.stdout.write(self.style.SUCCESS(f"\nDrew {drawn} of {total}"))
        if failed:
            self.stderr.write(self.style.ERROR(
                f"{failed} failed. They stay empty, so running this again "
                f"retries exactly those."))
