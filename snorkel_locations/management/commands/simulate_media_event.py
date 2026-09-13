"""Post a correctly signed media event at the local site.

Cloudflare cannot reach a development machine, so without this the
whole second half of the upload pipeline could only be exercised on a
deployed environment. With it, the webhook, the signature check and
the verification step can all be run against a real upload sitting in
the development bucket.

    python manage.py simulate_media_event media/<location>/<media>.jpg

Add --verify-only to skip the HTTP round trip and call the verification
directly, which is the quicker loop when the thing being debugged is
the checks rather than the endpoint.
"""
import hashlib
import hmac
import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from snorkel_locations.models import LocationMedia


class Command(BaseCommand):
    help = "Send a signed media event as the Cloudflare Worker would."

    def add_arguments(self, parser):
        parser.add_argument("key", help="Object key, or a media uuid")
        parser.add_argument("--url",
                            default="http://127.0.0.1:8000/api/v1/media/events")
        parser.add_argument("--verify-only", action="store_true",
                            help="Run verification directly, no HTTP")

    def handle(self, *args, **options):
        key = options["key"]
        row = (LocationMedia.objects.filter(object_key=key).first()
               or LocationMedia.objects.filter(uuid=key).first())
        if row is None:
            raise CommandError(f"No media row for {key}")

        if options["verify_only"]:
            from snorkel_locations.tasks import verify_media
            result = verify_media(row.uuid)
            row.refresh_from_db()
            self.stdout.write(
                f"{'verified' if result else 'refused'}: "
                f"{row.get_status_display()} {row.rejection_reason}")
            return

        secret = getattr(settings, "R2_MEDIA_WEBHOOK_SECRET", "")
        if not secret:
            raise CommandError("R2_MEDIA_WEBHOOK_SECRET is not set")

        body = json.dumps({"events": [
            {"key": row.object_key, "size": row.size_bytes or 0,
             "action": "PutObject"},
        ]}).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + body,
            hashlib.sha256).hexdigest()

        import requests
        response = requests.post(
            options["url"], data=body,
            headers={
                "Content-Type": "application/json",
                "X-SnorkelMap-Signature": f"t={timestamp},v1={signature}",
            }, timeout=30)
        self.stdout.write(f"{response.status_code} {response.text}")
        row.refresh_from_db()
        self.stdout.write(f"media is now {row.get_status_display()} "
                          f"{row.rejection_reason}")
