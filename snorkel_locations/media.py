"""Rules for photographs attached to a location submission.

This module is the single source of truth for what counts as an
acceptable photo. The browser receives the same values through
``media_rules()``, so the client side gate and the server side checks
cannot drift apart: change a limit here and both ends move together.

Nothing here touches the database, the network or Pillow. It is data
plus three small helpers, which keeps it cheap to import and trivial
to unit test.

Two of the ceilings are not ours. Cloudflare Image Transformations
will not fetch a remote source larger than 100 megapixels or longer
than 12,000 pixels on a side, so anything above those would upload
successfully and then never produce a thumbnail. We reject it at the
gate instead of publishing a listing with broken images.
"""

# ── Size and dimension limits ────────────────────────────────────────

# A photo smaller than this on either side looks soft on a listing
# page and worse on a phone with a dense screen. Anything from a real
# camera or phone clears it easily; what it catches is screenshots of
# screenshots and images that have been through a messaging app twice.
MIN_DIMENSION = 800

MAX_DIMENSION = 12_000          # Cloudflare remote source ceiling
MAX_MEGAPIXELS = 100            # Cloudflare remote source ceiling

# 25MB comfortably clears an iPhone HEIC (2 to 3MB), an iPhone JPEG
# (4 to 8MB) and a full frame camera JPEG (15MB or so).
MAX_FILE_BYTES = 25 * 1024 * 1024
MIN_FILE_BYTES = 1024

# Guard against someone dragging in a whole holiday folder. Raise it
# if testing suggests people genuinely want more.
MAX_FILES_PER_SECTION = 12


# ── Format signatures ────────────────────────────────────────────────
#
# Formats are identified by their leading bytes, never by the file
# extension and never by the browser supplied ``File.type``. Both of
# those are trivially wrong: a renamed .png, a HEIC that macOS
# reported as ``image/heif``, a file picked up from a share sheet with
# no type at all.
#
# A signature is a list of conditions that must ALL match. A format
# may have several alternative signatures, any ONE of which is enough.
# A condition offers a list of candidate byte strings at a fixed
# offset, given as uppercase hex.

# ISOBMFF brands that mean "this is a still image or image sequence we
# can hand to Cloudflare". iPhones write ``heic`` for a single image
# and ``msf1`` for a Live Photo still; ``mif1`` shows up on images
# written by macOS and by some Android handsets.
HEIF_BRANDS = (
    "68656963",  # heic
    "68656978",  # heix
    "6865696D",  # heim
    "68656973",  # heis
    "68657663",  # hevc
    "68657678",  # hevx
    "6865766D",  # hevm
    "68657673",  # hevs
    "6D696631",  # mif1
    "6D736631",  # msf1
)

_FTYP = "66747970"  # "ftyp", at offset 4 in every ISOBMFF file


ACCEPTED_FORMATS = [
    {
        "mime": "image/jpeg",
        "extension": "jpg",
        "label": "JPEG",
        "decodable": True,
        "signatures": [
            [{"offset": 0, "any_of": ["FFD8FF"]}],
        ],
    },
    {
        "mime": "image/png",
        "extension": "png",
        "label": "PNG",
        "decodable": True,
        "signatures": [
            [{"offset": 0, "any_of": ["89504E470D0A1A0A"]}],
        ],
    },
    {
        "mime": "image/webp",
        "extension": "webp",
        "label": "WebP",
        "decodable": True,
        "signatures": [
            [
                {"offset": 0, "any_of": ["52494646"]},   # RIFF
                {"offset": 8, "any_of": ["57454250"]},   # WEBP
            ],
        ],
    },
    {
        # "decodable": False is the important flag. Chromium and
        # Firefox have no HEIC decoder, so the browser cannot produce
        # a preview or report dimensions for these. WebKit can, and
        # since every browser on iOS is WebKit, the people who
        # actually shoot HEIC get the full experience. Everyone else
        # falls back to reading the dimensions out of the container
        # and showing a placeholder tile until the upload finishes.
        "mime": "image/heic",
        "extension": "heic",
        "label": "HEIC",
        "decodable": False,
        "signatures": [
            [
                {"offset": 4, "any_of": [_FTYP]},
                {"offset": 8, "any_of": list(HEIF_BRANDS)},
            ],
        ],
    },
]


# Formats we recognise well enough to refuse by name. A specific
# refusal ("GIFs are not supported") is worth a great deal more to
# someone than a generic one, particularly for AVIF and raw, where the
# reason is not obvious.
REJECTED_FORMATS = [
    {
        "mime": "image/gif",
        "label": "GIF",
        "signatures": [
            [{"offset": 0, "any_of": ["474946383761", "474946383961"]}],
        ],
        "message": ("{name} is a GIF. Please upload a photo saved as "
                    "JPEG, PNG, WebP or HEIC."),
    },
    {
        "mime": "image/avif",
        "label": "AVIF",
        "signatures": [
            [
                {"offset": 4, "any_of": [_FTYP]},
                {"offset": 8, "any_of": ["61766966", "61766973"]},  # avif, avis
            ],
        ],
        "message": ("{name} is an AVIF image, which our image service "
                    "cannot read as a source. Please upload the "
                    "original JPEG or HEIC instead."),
    },
    {
        # TIFF also catches camera raw: DNG, CR2, NEF and ARW are all
        # TIFF containers underneath.
        "mime": "image/tiff",
        "label": "TIFF",
        "signatures": [
            [{"offset": 0, "any_of": ["49492A00", "4D4D002A"]}],
        ],
        "message": ("{name} is a TIFF or camera raw file. Please "
                    "export it as a JPEG first."),
    },
    {
        "mime": "image/bmp",
        "label": "BMP",
        "signatures": [
            [{"offset": 0, "any_of": ["424D"]}],
        ],
        "message": ("{name} is a bitmap. Please upload a photo saved "
                    "as JPEG, PNG, WebP or HEIC."),
    },
    {
        "mime": "application/pdf",
        "label": "PDF",
        "signatures": [
            [{"offset": 0, "any_of": ["25504446"]}],
        ],
        "message": "{name} is a PDF, not a photo.",
    },
]

# SVG has no magic number. It is text, and it may open with an XML
# declaration, a doctype, a comment or the root element itself, so it
# is sniffed by looking for the root tag in the opening bytes rather
# than by a fixed offset.
SVG_MIME = "image/svg+xml"
SVG_SNIFF_BYTES = 1024
SVG_MARKERS = ["<svg", "<!doctype svg"]
SVG_MESSAGE = ("{name} is a vector graphic. Please upload a "
               "photograph.")


# ── User facing copy ─────────────────────────────────────────────────
#
# Kept here rather than in the JavaScript so the wording is reviewable
# in one place and can be reused by the server side checks and by any
# email we later send about a rejected upload. ``{...}`` placeholders
# are filled in by the caller.

MESSAGES = {
    "unsupported": ("{name} is not a format we can accept. Please "
                    "upload a JPEG, PNG, WebP or HEIC photo."),
    "unreadable": ("We could not read {name}. The file may be "
                   "damaged or incomplete."),
    "empty": "{name} appears to be empty.",
    "too_heavy": ("{name} is {size}, which is over the {limit} "
                  "limit. Please upload a smaller version."),
    "too_small": ("{name} is {width} by {height} pixels. Photos need "
                  "to be at least {min} pixels on both sides so they "
                  "stay sharp on a large screen."),
    "too_wide": ("{name} is {width} by {height} pixels. The longest "
                 "side needs to be under {max} pixels."),
    "too_many_pixels": ("{name} is {megapixels} megapixels, which is "
                        "larger than our image service can process. "
                        "The limit is {max} megapixels."),
    "too_many_files": ("You can add up to {max} photos here. {name} "
                       "and anything after it were not added."),
    "no_preview": ("Preview will appear once this photo has been "
                   "uploaded."),
}


# ── Helpers ──────────────────────────────────────────────────────────

def _condition_matches(head, condition):
    offset = condition["offset"]
    for candidate in condition["any_of"]:
        length = len(candidate) // 2
        if head[offset:offset + length].hex().upper() == candidate:
            return True
    return False


def _signature_matches(head, signatures):
    return any(
        all(_condition_matches(head, condition) for condition in signature)
        for signature in signatures
    )


def sniff(head):
    """Return the mime type of ``head``, or None if unrecognised.

    ``head`` needs to be at least the first 1024 bytes of the file.
    Recognised does not mean accepted: GIF, AVIF, TIFF, BMP, PDF and
    SVG all return their mime type so the caller can refuse them by
    name. Use ``is_accepted()`` to decide.
    """
    for fmt in ACCEPTED_FORMATS:
        if _signature_matches(head, fmt["signatures"]):
            return fmt["mime"]
    for fmt in REJECTED_FORMATS:
        if _signature_matches(head, fmt["signatures"]):
            return fmt["mime"]

    opening = head[:SVG_SNIFF_BYTES].decode("utf-8", "ignore").lower()
    if any(marker in opening for marker in SVG_MARKERS):
        return SVG_MIME
    return None


def is_accepted(mime):
    return any(fmt["mime"] == mime for fmt in ACCEPTED_FORMATS)


def extension_for(mime):
    """Storage extension for an accepted mime type.

    The extension on the object key is derived from the sniffed bytes,
    never from the name the browser supplied, so a file called
    ``holiday.jpg`` that is really a PNG is stored as ``.png``.
    """
    for fmt in ACCEPTED_FORMATS:
        if fmt["mime"] == mime:
            return fmt["extension"]
    raise ValueError(f"{mime} is not an accepted media type")


def accept_attribute():
    """Value for the file input's ``accept`` attribute.

    HEIC is listed deliberately. Leaving it off makes Safari transcode
    the photo to JPEG on the way in, which is a lossy re-encode of an
    image we would rather store untouched.
    """
    mimes = [fmt["mime"] for fmt in ACCEPTED_FORMATS]
    if "image/heic" in mimes:
        mimes.insert(mimes.index("image/heic") + 1, "image/heif")
    return ",".join(mimes)


def hint_text():
    """One line under the drop zone saying what will be accepted.

    Built from the constants so it cannot fall out of step with the
    rules it describes.
    """
    labels = [fmt["label"] for fmt in ACCEPTED_FORMATS]
    formats = ", ".join(labels[:-1]) + " or " + labels[-1]
    megabytes = MAX_FILE_BYTES // (1024 * 1024)
    return (f"{formats}. At least {MIN_DIMENSION} pixels on each side, "
            f"up to {megabytes}MB.")


def media_rules():
    """The whole rule set, shaped for ``json_script`` and the client."""
    return {
        "limits": {
            "min_dimension": MIN_DIMENSION,
            "max_dimension": MAX_DIMENSION,
            "max_megapixels": MAX_MEGAPIXELS,
            "max_bytes": MAX_FILE_BYTES,
            "min_bytes": MIN_FILE_BYTES,
            "max_files_per_section": MAX_FILES_PER_SECTION,
        },
        "accepted": ACCEPTED_FORMATS,
        "rejected": REJECTED_FORMATS,
        "svg": {
            "mime": SVG_MIME,
            "sniff_bytes": SVG_SNIFF_BYTES,
            "markers": SVG_MARKERS,
            "message": SVG_MESSAGE,
        },
        "messages": MESSAGES,
    }
