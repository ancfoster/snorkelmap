"""Fill a development database with believable listings.

    python manage.py seed_locations                 # 25 listings, with photos
    python manage.py seed_locations --count 5
    python manage.py seed_locations --no-images     # skip the R2 uploads
    python manage.py seed_locations --geocode       # ask Mapbox, rather than
                                                    # using the built in table
    python manage.py seed_locations --delete        # remove everything it made

Everything it creates is marked, so --delete can find it again and nothing
you added by hand is ever touched.

Deliberately refuses to run against a production media bucket. Seed data
belongs in a bucket with a lifecycle rule on it, not in the one real
photographs live in.

The photographs are generated here rather than shipped: a handful of
plain coloured images with the location name drawn on them, uploaded to
R2 under the same key shape the real flow uses, so listings render
through the image service exactly as they would in production.
"""
import io
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from snorkel_locations import choices, geography, media_storage
from snorkel_locations.models import (
    Country, Locale, LocationMedia, LocationRevision, Region, SnorkelLocation,
)

SEED_MARKER = {"seed": True}

# Real coastline, with the geography already known so the seed does not
# need to call Mapbox 25 times. Coordinates are jittered slightly on each
# run so repeated seeding does not stack listings on one pin.
#
# (country code, country, region, locale, lat, lng)
PLACES = [
    ("GB", "United Kingdom", "Scotland", "St Abbs", 55.8980, -2.1380),
    ("GB", "United Kingdom", "Scotland", "Oban", 56.4120, -5.4720),
    ("GB", "United Kingdom", "England", "Falmouth", 50.1520, -5.0660),
    ("GB", "United Kingdom", "England", "Torquay", 50.4620, -3.5250),
    ("GB", "United Kingdom", "Wales", "Tenby", 51.6720, -4.7030),
    ("IE", "Ireland", "County Clare", "Doolin", 53.0150, -9.3800),
    ("ES", "Spain", "Balearic Islands", "Ibiza", 38.9090, 1.4320),
    ("ES", "Spain", "Canary Islands", "Los Cristianos", 28.0480, -16.7170),
    ("PT", "Portugal", "Madeira", "Funchal", 32.6470, -16.9080),
    ("FR", "France", "Provence-Alpes-Cote d'Azur", "Cassis", 43.2120, 5.5380),
    ("IT", "Italy", "Sardinia", "Alghero", 40.5590, 8.3150),
    ("IT", "Italy", "Sicily", "Taormina", 37.8510, 15.2940),
    ("HR", "Croatia", "Split-Dalmatia", "Hvar", 43.1720, 16.4410),
    ("GR", "Greece", "Crete", "Chania", 35.5120, 24.0180),
    ("GR", "Greece", "South Aegean", "Naxos", 37.1040, 25.3760),
    ("MT", "Malta", "", "Sliema", 35.9130, 14.5050),
    ("CY", "Cyprus", "Famagusta", "Ayia Napa", 34.9880, 34.0010),
    ("EG", "Egypt", "Red Sea", "Marsa Alam", 25.0690, 34.8900),
    ("ZA", "South Africa", "Western Cape", "Hermanus", -34.4190, 19.2340),
    ("AU", "Australia", "Queensland", "Cairns", -16.9180, 145.7780),
    ("AU", "Australia", "Western Australia", "Exmouth", -21.9300, 114.1280),
    ("NZ", "New Zealand", "Northland", "Paihia", -35.2830, 174.0910),
    ("TH", "Thailand", "Krabi", "Ao Nang", 8.0320, 98.8210),
    ("PH", "Philippines", "Palawan", "El Nido", 11.1960, 119.4160),
    ("ID", "Indonesia", "Bali", "Amed", -8.3370, 115.6630),
    ("MX", "Mexico", "Quintana Roo", "Cozumel", 20.4230, -86.9220),
    ("BZ", "Belize", "Belize District", "Caye Caulker", 17.7440, -88.0250),
    ("US", "United States", "Florida", "Key Largo", 25.0860, -80.4470),
    ("US", "United States", "Hawaii", "Kailua-Kona", 19.6400, -155.9960),
    ("JP", "Japan", "Okinawa", "Onna", 26.4970, 127.8550),
    ("IS", "Iceland", "Southern Region", "Thingvellir", 64.2550, -21.1210),
    ("NO", "Norway", "Vestland", "Bergen", 60.3970, 5.3240),
    # No country at all, so at least one listing exercises the
    # /location/ocean/<slug>/ URL shape.
    ("", "", "", "", 31.2000, -41.6000),
]

FEATURES = ["Bay", "Cove", "Point", "Reef", "Head", "Rocks", "Pool",
            "Ledge", "Gully", "Shallows", "Arch", "Channel"]
QUALIFIERS = ["Seal", "Kelp", "Anchor", "Otter", "Gannet", "Wrasse", "Basalt",
              "Coral", "Turtle", "Lantern", "Cormorant", "Starfish", "Urchin",
              "Pilchard", "Mermaid", "Puffin", "Sandeel", "Whelk"]

OPENERS = [
    "A sheltered spot that works in most conditions and stays calm when the "
    "wind is anywhere in the west.",
    "Steep sided and deep very quickly, so it suits confident snorkellers "
    "rather than a first time out.",
    "Shallow and clear over pale sand, which makes it an easy place to bring "
    "somebody who has never snorkelled before.",
    "Popular in summer and almost empty out of season, when the visibility is "
    "usually at its best.",
    "A short swim from the entry gets you over the interesting ground, so it "
    "is worth the walk down.",
]

MIDDLES = [
    "Visibility is typically five to eight metres and can be much better "
    "after a settled week.",
    "The bottom drops away gradually to about twelve metres at the outer end.",
    "Expect a light current running along the shore on the ebb, nothing that "
    "cannot be swum against.",
    "Kelp covers most of the rock from two metres down, thinning out over the "
    "sand.",
    "Water temperature runs from nine degrees in early spring to about "
    "sixteen in late summer.",
]

CLOSERS = [
    "Worth timing around high water, when the entry is far easier.",
    "Best on a calm day: any swell at all makes the exit awkward.",
    "Good for a long slow potter rather than covering distance.",
    "Bring a torch if you want to look into the overhangs on the north side.",
    "Easy to combine with the next bay along if you have the time.",
]

ENTRIES = [
    "Stone steps beside the slipway, slippery below half tide. Sitting down "
    "to put fins on is much easier than standing.",
    "Walk in over coarse sand from the middle of the beach. No scramble and "
    "nothing sharp underfoot.",
    "A short climb down over boulders at the eastern end. Take care after "
    "rain, the rock is greasy.",
    "Concrete ramp with a handrail, the only easy access along this stretch "
    "of coast.",
    "Shallow shelving shingle. Easy enough in, but the exit is tiring in any "
    "surf.",
]

MARKER_NOTES = [
    "Slippery at low water", "Handrail on the left", "Deepest point here",
    "Watch for boat traffic", "Good spot to regroup", "Shallow sand, easy exit",
    "Kelp starts about here", "", "",
]

IMAGE_PALETTE = [
    ((18, 92, 128), "above water"),
    ((32, 118, 140), "above water"),
    ((58, 96, 76), "above water"),
    ((96, 116, 140), "above water"),
    ((12, 64, 96), "underwater"),
    ((8, 84, 92), "underwater"),
    ((24, 70, 70), "underwater"),
]


class Command(BaseCommand):
    help = "Create believable dummy locations for development."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=25)
        parser.add_argument("--user", default=None,
                            help="Username to attribute them to. Defaults to "
                                 "the first superuser.")
        parser.add_argument("--no-images", action="store_true",
                            help="Skip the R2 uploads. Listings publish but "
                                 "show no photographs.")
        parser.add_argument("--geocode", action="store_true",
                            help="Resolve geography through Mapbox instead of "
                                 "the built in table. Slower, and uses quota.")
        parser.add_argument("--delete", action="store_true",
                            help="Remove everything a previous seed created.")
        parser.add_argument("--seed", type=int, default=None,
                            help="Random seed, for a repeatable set.")

    # ── Guard rails ──────────────────────────────────────────────────

    def _check_bucket(self):
        bucket = getattr(settings, "R2_MEDIA_BUCKET", "") or ""
        if not bucket.endswith(("-dev", "-local", "-test")):
            raise CommandError(
                f"R2_MEDIA_BUCKET is {bucket!r}, which does not look like a "
                f"development bucket. Refusing to put seed images in it."
            )
        return bucket

    # ── Deleting ─────────────────────────────────────────────────────

    def _delete(self, with_images):
        seeded = SnorkelLocation.objects.filter(admin_notes__seed=True)
        count = seeded.count()
        if not count:
            self.stdout.write("Nothing to delete: no seeded locations found.")
            return

        if with_images:
            self._check_bucket()
            keys = list(LocationMedia.objects
                        .filter(location__in=seeded)
                        .values_list("object_key", flat=True))
            for key in keys:
                media_storage.delete_object(key)
            self.stdout.write(f"Removed {len(keys)} objects from the bucket.")

        # current_revision is PROTECT, so it has to be let go of before
        # the revisions can be deleted with the location.
        seeded.update(current_revision=None)
        seeded.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} seeded locations."))

    # ── Content ──────────────────────────────────────────────────────

    def _name(self, locale):
        name = f"{random.choice(QUALIFIERS)} {random.choice(FEATURES)}"
        # Occasionally tie it to the place, the way real names often are.
        if locale and random.random() < 0.25:
            name = f"{locale} {random.choice(FEATURES)}"
        return name

    def _description(self):
        parts = [random.choice(OPENERS), random.choice(MIDDLES)]
        if random.random() < 0.7:
            parts.append(random.choice(CLOSERS))
        return " ".join(parts)

    def _group_map(self, section):
        """A plausible set of selections for one payload section."""
        out = {}
        for payload_key, group in choices.PAYLOAD_SECTIONS[section].items():
            if random.random() < 0.45:
                continue
            ids = [chip["id"] for chip in group["chips"]]
            if not ids:
                continue
            picked = random.sample(ids, k=min(len(ids), random.randint(1, 3)))
            if group["comments"]:
                out[payload_key] = {
                    "selected": picked,
                    "comments": (random.choice(MIDDLES)
                                 if random.random() < 0.3 else ""),
                }
            else:
                out[payload_key] = picked
        if random.random() < 0.3:
            out["comments"] = random.choice(CLOSERS)
        return out

    def _facilities(self):
        facilities = self._group_map("facilities")
        parking = [p[0] for p in choices.PARKING_TYPES]
        transport = [t[0] for t in choices.TRANSPORT_TYPES]
        facilities["gettingThere"] = {
            "comments": random.choice(CLOSERS) if random.random() < 0.4 else "",
            "parking": {
                "available": random.choice(
                    [p[0] for p in choices.PARKING_AVAILABILITY]),
                "selected": random.sample(parking, k=random.randint(0, 2)),
                "comments": "",
            },
            "transport": {
                "selected": random.sample(transport, k=random.randint(0, 2)),
                "description": "",
            },
        }
        facilities["other"] = ""
        return facilities

    def _markers(self, lat, lng):
        library = [m[0] for group in choices.MARKER_LIBRARY
                   for m in group["markers"]]
        labels = {m[0]: m[1] for group in choices.MARKER_LIBRARY
                  for m in group["markers"]}
        features = []
        for marker_id in random.sample(library, k=random.randint(2, 5)):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [
                    round(lng + random.uniform(-0.002, 0.002), 6),
                    round(lat + random.uniform(-0.002, 0.002), 6),
                ]},
                "properties": {
                    "markerId": marker_id,
                    "name": labels[marker_id],
                    "note": random.choice(MARKER_NOTES),
                },
            })
        return {"type": "FeatureCollection", "features": features}

    # ── Images ───────────────────────────────────────────────────────

    def _make_image(self, colour, caption):
        """A plain JPEG with the name on it, so listings are tellable apart."""
        from PIL import Image, ImageDraw, ImageFont

        try:
            font_big = ImageFont.load_default(size=54)
            font_small = ImageFont.load_default(size=32)
        except TypeError:
            # Pillow older than 10 cannot size the default font.
            font_big = font_small = ImageFont.load_default()

        width, height = 1600, 1200
        image = Image.new("RGB", (width, height), colour)
        draw = ImageDraw.Draw(image)
        for i in range(-height, width, 90):
            draw.line([(i, 0), (i + height, height)],
                      fill=tuple(min(255, c + 22) for c in colour), width=30)
        draw.rectangle([80, height - 260, width - 80, height - 90],
                       fill=(0, 0, 0))
        draw.text((110, height - 235), caption[:40], fill=(255, 255, 255),
                  font=font_big)
        draw.text((110, height - 160), "SnorkelMap seed data",
                  fill=(190, 190, 190), font=font_small)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82)
        return buffer.getvalue(), width, height

    def _upload(self, key, data):
        media_storage._client().put_object(
            Bucket=settings.R2_MEDIA_BUCKET,
            Key=key, Body=data, ContentType="image/jpeg",
        )

    # ── Geography ────────────────────────────────────────────────────

    def _geography(self, place, use_mapbox, lat, lng):
        if use_mapbox:
            country, region, locale, _failed = geography.resolve(lat, lng)
            return country, region, locale

        code, country_name, region_name, locale_name = place[:4]
        country = region = locale = None
        if code:
            country, _ = Country.objects.get_or_create(
                code=code, defaults={"name": country_name})
        if country and region_name:
            region, _ = Region.objects.get_or_create(
                country=country, name=region_name,
                defaults={"slug": slugify(region_name)})
        if region and locale_name:
            locale, _ = Locale.objects.get_or_create(
                region=region, name=locale_name,
                defaults={"slug": slugify(locale_name)})
        return country, region, locale

    # ── The command ──────────────────────────────────────────────────

    def handle(self, *args, **options):
        if options["seed"] is not None:
            random.seed(options["seed"])

        with_images = not options["no_images"]

        if options["delete"]:
            self._delete(with_images=True)
            return

        if with_images:
            self._check_bucket()

        User = get_user_model()
        if options["user"]:
            author = User.objects.filter(username=options["user"]).first()
            if author is None:
                raise CommandError(f"No user called {options['user']!r}.")
        else:
            author = User.objects.filter(is_superuser=True).order_by("id").first()
            if author is None:
                raise CommandError(
                    "No superuser to attribute these to. Create one, or pass "
                    "--user."
                )

        count = options["count"]
        places = random.sample(PLACES, k=min(count, len(PLACES)))
        while len(places) < count:
            places.append(random.choice(PLACES))

        created = 0
        for index, place in enumerate(places, start=1):
            lat = place[4] + random.uniform(-0.02, 0.02)
            lng = place[5] + random.uniform(-0.02, 0.02)
            locale_name = place[3]
            name = self._name(locale_name)

            country, region, locale = self._geography(
                place, options["geocode"], lat, lng)

            with transaction.atomic():
                location = SnorkelLocation.objects.create(
                    slug=geography.unique_slug(name),
                    lat_long=Point(lng, lat, srid=4326),
                    country=country, region=region, locale=locale,
                    status=SnorkelLocation.Status.DRAFT,
                    admin_notes=dict(SEED_MARKER),
                )

                revision = LocationRevision.objects.create(
                    location=location, increment=0, name=name,
                    alternate_names=([f"{locale_name} {random.choice(FEATURES)}"]
                                     if locale_name and random.random() < 0.3
                                     else []),
                    description=self._description(),
                    entry_description=random.choice(ENTRIES),
                    access_type=random.sample(
                        [a[0] for a in choices.ACCESS_TYPES],
                        k=random.randint(1, 2)),
                    water_type=[random.choice(
                        [chip["id"] for chip in
                         random.choice(choices.WATER_TYPE_GROUPS)["chips"]])],
                    difficulty=random.randint(1, 4),
                    environment_types=self._group_map("environmentTypes"),
                    marine_life=self._group_map("marineLife"),
                    hazards=self._group_map("hazards"),
                    facilities=self._facilities(),
                    marker_data=self._markers(lat, lng),
                    created_by=author,
                    revision_comment="Seeded",
                )
                location.current_revision = revision
                location.save(update_fields=["current_revision"])

            rows = []
            if with_images:
                surface_count = random.randint(1, 2)
                underwater_count = random.randint(0, 2)
                sections = ([(LocationMedia.MediaCategory.SURFACE, i)
                             for i in range(surface_count)]
                            + [(LocationMedia.MediaCategory.UNDERWATER, i)
                               for i in range(underwater_count)])

                for category, order in sections:
                    is_surface = category == LocationMedia.MediaCategory.SURFACE
                    palette = [p for p in IMAGE_PALETTE
                               if (p[1] == "above water") == is_surface]
                    colour, _kind = random.choice(palette)
                    data, width, height = self._make_image(colour, name)

                    media_uuid = media_storage.new_media_uuid()
                    key = media_storage.build_key(
                        location.uuid, media_uuid, "image/jpeg")
                    self._upload(key, data)

                    rows.append(LocationMedia.objects.create(
                        uuid=media_uuid, location=location,
                        media_type=LocationMedia.MediaType.IMAGE,
                        media_category=category,
                        uploaded_by=author,
                        description=("View across the bay" if is_surface
                                     else "Kelp and rock below the surface"),
                        object_key=key,
                        status=LocationMedia.Status.ACTIVE,
                        mime_type="image/jpeg",
                        width=width, height=height, size_bytes=len(data),
                        captured_at=timezone.now() - timedelta(
                            days=random.randint(1, 900)),
                        sort_order=order,
                        verified_at=timezone.now(),
                        orignal_media_meta={"seed": True},
                    ))

                surface = next(
                    (r for r in rows
                     if r.media_category == LocationMedia.MediaCategory.SURFACE),
                    None)
                if surface is not None:
                    revision.featured_above_water_image = surface
                    revision.save(update_fields=["featured_above_water_image"])
                    location.status = SnorkelLocation.Status.PUBLISHED
                    location.save(update_fields=["status"])
            else:
                # Without a photograph nothing would ever publish, and a
                # database full of drafts is not useful to look at.
                location.status = SnorkelLocation.Status.PUBLISHED
                location.save(update_fields=["status"])

            created += 1
            self.stdout.write(
                f"{index:>3}. {name}  {location.get_absolute_url()}"
                f"  ({len(rows)} photo{'s' if len(rows) != 1 else ''})")

        self.stdout.write(self.style.SUCCESS(
            f"\nCreated {created} locations as {author.username}."
            f"\nRemove them again with: manage.py seed_locations --delete"))
