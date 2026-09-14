"""
Canonical option lists for the location creation flow.

One source of truth: the create template renders every chip from these
structures, and the publish endpoint validates submitted ids against them.
The front end never invents an id, so nothing can drift between the markup,
the JavaScript and the database.

Each group carries:
  key           state key the JS groups selections under
  label         heading shown above the chips
  chips         ordered [(id, label), ...]
  none_option   True adds a "None" chip that clears and dims the rest
  single_select True allows only one selection in the group
  example       key of the example block in the examples partial, if any
  comments      True renders an optional comment box under the group
"""


# State keys are prefixed by step (envReef, mlFish, hazWater, facSafety).
# The submitted JSON nests them under that step with the prefix dropped,
# so envReef lands at environment_types.reef. Derived rather than typed out
# twice, so the two can never disagree.
_STATE_PREFIXES = ("env", "ml", "haz", "fac")


def _payload_key(key):
    for prefix in _STATE_PREFIXES:
        rest = key[len(prefix):]
        if key.startswith(prefix) and rest and rest[0].isupper():
            return rest[0].lower() + rest[1:]
    return key


def _group(key, label, chips, *, none_option=False, single_select=False,
           example=None, comments=False, none_text=""):
    return {
        "key": key,
        "payload_key": _payload_key(key),
        "label": label,
        "chips": [{"id": i, "label": l} for i, l in chips],
        "none_option": none_option,
        "single_select": single_select,
        "example": example,
        "comments": comments,
        # What a listing says when somebody answered "None" for this
        # group. Written per group rather than assembled from the label,
        # because "no Washing and Changing" does not read as English and
        # "no washing or changing facilities" does. Only groups that
        # offer a None option need one.
        "none_text": none_text,
    }


# ── Step 2: basic details ────────────────────────────────────────────

ACCESS_TYPES = [
    ("shore", "From the shore"),
    ("boat", "Boat"),
]

# Water type is exclusive across groups: choosing from one dims the other,
# and clicking a dimmed chip switches groups rather than being blocked.
WATER_TYPE_GROUPS = [
    {
        "id": "salt",
        "label": "Salt Water",
        "chips": [
            {"id": "ocean-sea", "label": "Ocean / Sea"},
            {"id": "sea-cave", "label": "Sea Cave"},
            {"id": "estuary", "label": "Estuary"},
            {"id": "coastal-lagoon", "label": "Coastal Lagoon"},
        ],
    },
    {
        "id": "fresh",
        "label": "Fresh Water",
        "chips": [
            {"id": "lake", "label": "Lake"},
            {"id": "river", "label": "River"},
            {"id": "pond", "label": "Pond"},
            {"id": "freshwater-lagoon", "label": "Freshwater Lagoon"},
            {"id": "cave", "label": "Cave"},
        ],
    },
]

DIFFICULTY_LABELS = ["Easy", "Moderate", "Difficult", "Extreme"]


# ── Step 4: underwater environment ─────────────────────────────────

ENVIRONMENT_GROUPS = [
    _group(
        "envReef", "Reef",
        [
            ("reef", "Reef"),
        ],
        example="envReef",
    ),
    _group(
        "envRocky", "Rocky",
        [
            ("rocky-shore", "Rocky Shore"),
            ("boulders", "Boulders"),
            ("drop-off", "Drop Off"),
            ("pinnacles", "Pinnacles"),
        ],
        example="envRocky",
    ),
    _group(
        "envSeabed", "Seabed & Substrate",
        [
            ("sandy-bottom", "Sandy Bottom"),
            ("volcanic-sand", "Volcanic Sand"),
            ("shell-bed", "Shell Bed"),
            ("pebble-shingle", "Pebble / Shingle"),
            ("gravel-bed", "Gravel Bed"),
            ("rocky-bottom", "Rocky Bottom"),
            ("rubble", "Rubble"),
            ("mud", "Mud"),
        ],
        example="envSeabed",
    ),
    _group(
        "envVegetated", "Vegetated",
        [
            ("kelp-forest", "Kelp Forest"),
            ("seagrass-meadow", "Seagrass Meadow"),
            ("mangroves", "Mangroves"),
            ("posidonia", "Posidonia Meadow"),
        ],
        example="envVegetated",
    ),
    _group(
        "envStructures", "Structures",
        [
            ("wreck", "Wreck"),
            ("plane", "Plane"),
            ("artificial-reef", "Artificial Reef Structure"),
            ("pier-jetty", "Pier / Jetty Piling"),
            ("harbour-wall", "Sea / Harbour Wall"),
            ("tetrapods", "Tetrapods"),
        ],
        example="envStructures",
    ),
    _group(
        "envGeological", "Geological",
        [
            ("sea-cave", "Sea Cave"),
            ("sea-arch", "Sea Arch / Swim-through"),
            ("lava-volcanic", "Lava / Volcanic Formation"),
            ("flooded-limestone", "Flooded Limestone / Karst"),
        ],
        example="envGeological",
    ),
]


# ── Step 5: marine life ─────────────────────────────────

MARINE_LIFE_GROUPS = [
    _group(
        "mlFish", "Fish",
        [
            ("sharks", "Sharks"),
            ("rays", "Rays"),
            ("colourful-reef", "Colourful Reef Fish"),
            ("schooling-fish", "Schooling Fish"),
            ("flatfish", "Flatfish"),
            ("eels", "Eels"),
            ("large-pelagic", "Large pelagic fish (tuna, marlin, sunfish)"),
            ("big-coastal", "Big coastal fish (wolffish, bass, grouper)"),
            ("medium-fish", "Medium fish (mullet, parrotfish, bream, mackerel)"),
            ("small-juvenile", "Small & juvenile fish"),
            ("seahorses", "Seahorses"),
        ],
        example="mlFish",
    ),
    _group(
        "mlMammals", "Marine Mammals",
        [
            ("seals", "Seals"),
            ("sea-lions", "Sea Lions"),
            ("dolphins-porpoises", "Dolphins & Porpoises"),
            ("whales", "Whales"),
            ("manatees-dugongs", "Manatees & Dugongs"),
        ],
        example="mlMammals",
    ),
    _group(
        "mlCrustaceans", "Crustaceans",
        [
            ("crabs", "Crabs"),
            ("lobsters", "Lobsters"),
            ("shrimp", "Shrimp"),
            ("crayfish", "Crayfish"),
        ],
        example="mlCrustaceans",
    ),
    _group(
        "mlMolluscs", "Molluscs",
        [
            ("mussels", "Mussels"),
            ("scallops", "Scallops"),
            ("clams", "Clams"),
            ("snails", "Snails"),
            ("limpets", "Limpets"),
            ("nudibranchs", "Nudibranchs / Sea Slugs"),
        ],
        example="mlMolluscs",
    ),
    _group(
        "mlEchinoderm", "Echinoderm",
        [
            ("starfish", "Starfish & Brittle Stars"),
            ("urchins", "Urchins"),
            ("sea-cucumbers", "Sea Cucumbers"),
            ("feather-stars", "Feather Stars"),
        ],
        example="mlEchinoderm",
    ),
    _group(
        "mlCnidarians", "Cnidarians",
        [
            ("hard-corals", "Hard Corals"),
            ("soft-corals", "Soft Corals"),
            ("sea-anemones", "Sea Anemones"),
            ("jellyfish", "Jellyfish"),
            ("hydroids", "Hydroids"),
        ],
        example="mlCnidarians",
    ),
    _group(
        "mlReptiles", "Reptiles",
        [
            ("sea-snakes", "Sea Snakes"),
            ("turtles", "Turtles"),
            ("marine-iguanas", "Marine Iguanas"),
        ],
        example="mlReptiles",
    ),
    _group(
        "mlCephalopods", "Cephalopods",
        [
            ("octopus", "Octopus"),
            ("squid", "Squid"),
            ("cuttlefish", "Cuttlefish"),
        ],
        example="mlCephalopods",
    ),
    _group(
        "mlSessile", "Sessile Life",
        [
            ("sea-sponges", "Sea Sponges"),
            ("worms", "Tube Worms & Feather Dusters"),
            ("tunicates", "Tunicates"),
        ],
        example="mlSessile",
    ),
    _group(
        "mlBirds", "Birds",
        [
            ("diving-seabirds", "Diving Seabirds"),
        ],
        example="mlBirds",
    ),
]


# ── Step 6: hazards ─────────────────────────────────
# Every hazard group takes an optional comment box.

HAZARD_GROUPS = [
    _group(
        "hazCurrents", "Currents and Water Movement",
        [
            ("rip-currents", "Rip currents"),
            ("tidal-currents", "Tidal currents"),
            ("surge-swell", "Surge and swell"),
            ("whirlpools", "Whirlpools & eddies"),
            ("large-tidal", "Large tidal range"),
        ],
        example="hazCurrents",
        comments=True,
    ),
    _group(
        "hazEntryExit", "Entry and Exit",
        [
            ("difficult-entry", "Difficult entry"),
            ("difficult-exit", "Difficult exit"),
            ("shore-break", "Shore break"),
            ("long-swim", "Long swim from shore"),
            ("entry-exit-diff", "Entry and exit points are different"),
        ],
        comments=True,
    ),
    _group(
        "hazWater", "Water Hazards",
        [
            ("submerged", "Submerged hazards"),
            ("entanglement", "Entanglement risk"),
            ("poor-vis", "Poor visibility common"),
            ("fishing-gear", "Fishing gear"),
            ("shore-fishing", "Shore Fishing (angling)"),
        ],
        comments=True,
    ),
    _group(
        "hazTraffic", "Marine Traffic",
        [
            ("boat-traffic", "Boat traffic"),
            ("anchorage", "Anchorage"),
            ("wind-kite", "Wind / kite surfers"),
            ("paddle-boarders", "Paddle boarders"),
            ("commercial-fish", "Commercial fishing boats"),
            ("slipway", "Slipway (launching + recovery of boats)"),
            ("rec-fishing", "Recreational fishing boats"),
            ("jet-skis", "Jet skis / Personal Watercraft"),
        ],
        comments=True,
    ),
    _group(
        "hazPollution", "Pollution",
        [
            ("intake-outfall", "Intake & Outfall Pipes"),
            ("pollution-obs", "Pollution observed"),
            ("sewage", "Sewage"),
            ("garbage", "Garbage / litter"),
        ],
        comments=True,
    ),
    _group(
        "hazMarineLife", "Marine Life Hazards",
        [
            ("jellyfish", "Jellyfish"),
            ("large-sharks", "Large sharks"),
            ("stinging-animals", "Stinging Animals"),
            ("stinging-coral", "Stinging Coral"),
            ("biting-fish", "Biting Fish (e.g. trigger fish)"),
            ("territorial-mammals", "Territorial mammals"),
            ("sea-snakes-haz", "Sea snakes"),
            ("spiny-creatures", "Spiny creatures (sea urchins, scorpionfish)"),
        ],
        example="hazMarineLife",
        comments=True,
    ),
]


# ── Step 7: facilities ─────────────────────────────────
# Every facility group takes an optional comment box.

FACILITY_GROUPS = [
    _group(
        "facWashing", "Washing and Changing",
        [
            ("toilets", "Toilets"),
            ("showers", "Showers"),
            ("changing", "Changing facilities"),
            ("lockers", "Lockers"),
        ],
        none_option=True, example="facWashing",
        none_text=(
            "Users have indicated there are no washing or changing facilities at this location."),
        comments=True,
    ),
    _group(
        "facFood", "Food & Drink",
        [
            ("cafe", "Cafe"),
            ("pub-bar", "Pub / Bar"),
            ("supermarket", "Supermarket"),
            ("shop-kiosk", "Shop / kiosk"),
        ],
        none_option=True, example="facFood",
        none_text=(
            "Users have indicated there are no food or drink facilities at this location."),
        comments=True,
    ),
    _group(
        "facSignal", "Mobile / Cell Signal",
        [
            ("has-signal", "Usable Cell / Mobile Signal"),
            ("intermittent-signal", "Intermittent cell / mobile signal"),
            ("no-signal", "No cell / mobile signal"),
        ],
        single_select=True,
        comments=True,
    ),
    _group(
        "facSafety", "Safety and Emergency",
        [
            ("lifeguard", "Lifeguard"),
            ("first-aid", "First aid point"),
            ("emergency-phone", "Emergency phone / call point"),
        ],
        none_option=True, example="facSafety",
        none_text=(
            "Users have indicated there are no safety or emergency facilities at this location."),
        comments=True,
    ),
]

# Facility groups rendered either side of the "Getting There" block on step 7
FACILITIES_BEFORE_GETTING_THERE = ["facWashing", "facFood"]
FACILITIES_AFTER_GETTING_THERE = ["facSignal", "facSafety"]


# ── Step 7: getting there ────────────────────────────────────────────

PARKING_AVAILABILITY = [
    ("yes", "Yes"),
    ("none", "None"),
]

# Only shown once parking availability is answered "yes"
PARKING_TYPES = [
    ("on-road", "On-road parking"),
    ("off-road", "Off-road parking"),
    ("car-park", "Car Park / Parking Lot"),
]

TRANSPORT_TYPES = [
    ("bus", "Bus"),
    ("train", "Train"),
    ("other", "Other"),
]


# ── Step 3: media ────────────────────────────────────────────────────
# Above water is the only photo required to publish.

MEDIA_SECTIONS = [
    {
        "key": "aboveWater",
        "slug": "above-water",
        "label": "Above Water Surroundings",
        "required": True,
        "helper": ("The shoreline, the entry point, the view from the car park. "
                   "Anything that helps someone know they are in the right place."),
    },
    {
        "key": "underwater",
        "slug": "underwater",
        "label": "Underwater Pictures",
        "required": False,
        "helper": ("Not required to publish, but they give people a far better "
                   "sense of what they will see."),
    },
]


# ── Step 8: annotation map markers ───────────────────────────────────
# icon files live at static/images/sm-map-icons/<id>.png, with a
# matching <id>-comment.png used once a marker carries a note.

MARKER_LIBRARY = [
    {
        "category": "Entry & Exit",
        "markers": [
            ("entry", "Entry Point"),
            ("exit", "Exit Point"),
        ],
    },
    {
        "category": "Facilities",
        "markers": [
            ("swim-ladder", "Swim Ladder"),
            ("parking", "Parking"),
            ("showers", "Showers"),
            ("toilets", "Toilets"),
            ("first-aid", "First Aid"),
            ("changing-facility", "Changing Facility"),
        ],
    },
    {
        "category": "Underwater Features",
        "markers": [
            ("wreck", "Wreck"),
            ("plane-wreck", "Plane Wreck"),
        ],
    },
    {
        "category": "Hazards",
        "markers": [
            ("hazard", "Hazard"),
            ("lobster-crab-pots", "Lobster & Crab Pots"),
            ("slipway", "Slipway"),
            ("underwater-hazard", "Underwater Hazard"),
            ("outflow", "Outflow"),
            ("rip-current", "Rip Current"),
            ("personal-watercraft", "Personal Watercraft"),
            ("angling", "Angling"),
            ("windsurfers", "Windsurfers"),
            ("stinging-jellies", "Stinging Jellies"),
            ("large-sharks", "Large Sharks"),
            ("slippery", "Slippery Surface"),
            ("crocodiles", "Crocodiles"),
            ("no-snorkelling", "No Snorkelling"),
            ("strong-currents", "Strong Currents"),
        ],
    },
]


# ── Visibility report ────────────────────────────────────────────────

VISIBILITY_MAX_AGE_DAYS = 180

VISIBILITY_CATEGORY_LABELS = ["Very Poor", "Poor", "Average", "Very Good", "Excellent"]
VISIBILITY_SCALE_LABELS = ["0m", "2m", "5m", "8m", "12m+"]


# ── Step chrome ──────────────────────────────────────────────────────
# The numbered steps the user walks. The intro, resume, publish and
# thank-you screens sit outside this count.

STEP_TOTAL = 8

STEPS = [
    {"number": 1, "slug": "where", "title": "Where is it"},
    {"number": 2, "slug": "details", "title": "Basic Details"},
    {"number": 3, "slug": "media", "title": "Upload media"},
    {"number": 4, "slug": "environment", "title": "Underwater Environment"},
    {"number": 5, "slug": "marine-life", "title": "Types of marine life"},
    {"number": 6, "slug": "hazards", "title": "Hazards"},
    {"number": 7, "slug": "facilities", "title": "Facilities"},
    {"number": 8, "slug": "location-map", "title": "Location Map"},
]


def flat_water_types():
    """Water types come grouped for the form; flat for looking one up.

    Here rather than beside whichever page needed it first, because
    both the listing and the history read stored ids back into labels
    and neither should be carrying its own copy of the mapping.
    """
    return [(chip["id"], chip["label"])
            for group in WATER_TYPE_GROUPS
            for chip in group["chips"]]


def all_groups():
    """Every chip group, for validating a submitted payload in one pass."""
    return (ENVIRONMENT_GROUPS + MARINE_LIFE_GROUPS
            + HAZARD_GROUPS + FACILITY_GROUPS)


def valid_ids(group_key):
    """Allowed chip ids for one group key, including its None option."""
    for group in all_groups():
        if group["key"] == group_key:
            ids = {chip["id"] for chip in group["chips"]}
            if group["none_option"]:
                ids.add("none")
            return ids
    return set()


# ── Reading a stored submission back ─────────────────────────────────
#
# The create form writes its selections under the payload key of each
# group, so a listing page needs the same mapping in reverse to turn
# stored ids back into the words a person chose.

PAYLOAD_SECTIONS = {
    "environmentTypes": {g["payload_key"]: g for g in ENVIRONMENT_GROUPS},
    "marineLife": {g["payload_key"]: g for g in MARINE_LIFE_GROUPS},
    "hazards": {g["payload_key"]: g for g in HAZARD_GROUPS},
    "facilities": {g["payload_key"]: g for g in FACILITY_GROUPS},
}


def label_for(group_key, chip_id):
    """The label of one chip, or the raw id if it is no longer offered."""
    if chip_id == "none":
        return "None"
    for group in all_groups():
        if group["key"] != group_key:
            continue
        for chip in group["chips"]:
            if chip["id"] == chip_id:
                return chip["label"]
    return chip_id


def labels_for(options, ids):
    """Labels for ids taken from a flat (id, label) list."""
    lookup = dict(options)
    return [lookup.get(i, i) for i in ids or []]


def describe_group_map(section, stored):
    """Turn one stored section into something a template can loop over.

    Returns a list of {"label", "selected", "comments", "absent"}, in
    the order
    the groups are defined rather than the order the JSON happens to be
    in, and skipping groups the person left empty. Groups that no
    longer exist are dropped, so a listing created before a chip was
    renamed still renders rather than breaking.
    """
    index = PAYLOAD_SECTIONS.get(section, {})
    described = []

    for payload_key, group in index.items():
        value = (stored or {}).get(payload_key)
        if value is None:
            continue

        if isinstance(value, dict):
            selected = value.get("selected") or []
            comments = value.get("comments") or ""
        else:
            selected = value or []
            comments = ""

        if not selected and not comments:
            continue

        # "None" is an answer, not an absence of one, and a different
        # kind of answer from the rest: it says the reader should not
        # expect to find any of this here. Pulled out of the list so
        # the page can say so in words rather than showing a chip
        # reading "None", which tells nobody anything.
        absent = "none" in selected
        selected = [i for i in selected if i != "none"]

        described.append({
            "label": group["label"],
            "selected": [label_for(group["key"], i) for i in selected],
            "comments": comments,
            "absent": absent,
            "absent_text": group["none_text"] if absent else "",
        })

    return described


# ── Page context ─────────────────────────────────────────────────────

def create_page_context():
    """Everything the create template needs.

    Lives here rather than in views.py so it can be imported and tested
    without pulling in the GIS models, and so the template and any future
    server-side validation read from exactly the same structures.
    """
    from django.conf import settings
    from django.templatetags.static import static

    from .media import accept_attribute, hint_text, media_rules

    facility_index = {group["key"]: group for group in FACILITY_GROUPS}

    return {
        "mapbox_token": settings.MAPBOX_TOKEN,
        # Trailing slash matters: the JS appends "<marker-id>.png"
        "marker_icon_base": static("images/sm-map-icons/"),
        "step_total": STEP_TOTAL,
        "steps": STEPS,

        "access_types": ACCESS_TYPES,
        "water_type_groups": WATER_TYPE_GROUPS,
        "difficulty_labels": DIFFICULTY_LABELS,

        "media_sections": MEDIA_SECTIONS,
        # Photo rules live in media.py so that the browser gate and the
        # server side checks read the same numbers.
        "media_rules": media_rules(),
        "media_accept": accept_attribute(),
        "media_hint": hint_text(),

        "environment_groups": ENVIRONMENT_GROUPS,
        "marine_life_groups": MARINE_LIFE_GROUPS,
        "hazard_groups": HAZARD_GROUPS,

        "facility_groups_before": [facility_index[k] for k in FACILITIES_BEFORE_GETTING_THERE],
        "facility_groups_after": [facility_index[k] for k in FACILITIES_AFTER_GETTING_THERE],
        "parking_availability": PARKING_AVAILABILITY,
        "parking_types": PARKING_TYPES,
        "transport_types": TRANSPORT_TYPES,

        "marker_library": MARKER_LIBRARY,

        "visibility_max_age_days": VISIBILITY_MAX_AGE_DAYS,
        "visibility_category_labels": VISIBILITY_CATEGORY_LABELS,
        "visibility_scale_labels": VISIBILITY_SCALE_LABELS,
    }
