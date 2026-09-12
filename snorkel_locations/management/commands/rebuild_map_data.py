"""Rebuild the map's data file by hand.

The file is normally rebuilt when a location is published, but that
rebuild swallows its own failures so that a bucket being unreachable
can never stop a listing going live. This is how it gets fixed
afterwards, and how the first file gets built on a fresh install.

    manage.py rebuild_map_data
    manage.py rebuild_map_data --force     upload even if unchanged
    manage.py rebuild_map_data --prune     delete superseded files
"""
from django.core.management.base import BaseCommand

from snorkel_locations import geo_storage, map_data
from snorkel_locations.models import MapData


class Command(BaseCommand):
    help = "Rebuild and upload the map data file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Upload even when the contents are unchanged.")
        parser.add_argument(
            "--prune", action="store_true",
            help="Delete every data file in the bucket but the current one.")

    def handle(self, *args, **options):
        before = MapData.load().object_key

        key = map_data.build_and_publish(force=options["force"])
        if not key:
            self.stderr.write(self.style.ERROR(
                "Upload failed. The previous file is still being served; "
                "see the log for the underlying error."))
            return

        record = MapData.load()
        if key == before and not options["force"]:
            self.stdout.write(f"Unchanged: {key} ({record.size_bytes} bytes)")
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Built {key} ({record.size_bytes} bytes)"))
            self.stdout.write(f"  {geo_storage.public_url(key)}")

        if options["prune"]:
            removed = 0
            for stale in geo_storage.list_data_files():
                if stale != key:
                    geo_storage.delete_object(stale)
                    removed += 1
            self.stdout.write(f"Pruned {removed} superseded file(s)")
