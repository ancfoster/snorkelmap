"""What arrives when somebody rates a location.

A plain Form rather than a ModelForm. The Review row is built by the
view, which has to decide between creating one and editing the one
that is already there, and a ModelForm bound to an instance would
duplicate that decision rather than remove it.
"""
from django import forms

from snorkel_locations import submissions

from .models import BODY_MAX, MAX_RATING, MIN_RATING


class ReviewForm(forms.Form):
    """One rating, and optionally some words to go with it."""

    rating = forms.IntegerField(
        min_value=MIN_RATING, max_value=MAX_RATING,
        error_messages={
            "required": "Choose a rating from one to five stars.",
            "invalid": "Choose a rating from one to five stars.",
            "min_value": "Choose a rating from one to five stars.",
            "max_value": "Choose a rating from one to five stars.",
        },
    )
    body = forms.CharField(required=False, strip=True)

    def clean_body(self):
        """Plain text, and no more of it than was asked for.

        Cleaned by the same function every other piece of submitted
        prose on the site goes through, rather than a second one
        written here: markup removal is the sort of thing that is
        wrong the moment it exists in two places. It is asked for one
        character more than the limit so that too long can be told
        apart from exactly long enough, and rejected rather than
        quietly trimmed, because losing the end of somebody's sentence
        without telling them is not a kindness.
        """
        text = submissions.clean_text(self.data.get("body", ""),
                                      limit=BODY_MAX + 1)
        if len(text) > BODY_MAX:
            raise forms.ValidationError(
                f"Reviews are limited to {BODY_MAX} characters.")
        return text
