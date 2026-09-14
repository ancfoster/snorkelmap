"""What arrives when somebody files a visibility report.

A plain Form rather than a ModelForm, for the same reason the review
form is one: the row it becomes belongs to a VisibilityLocation the
view has to find or make first, and a ModelForm bound to an instance
would duplicate that decision rather than remove it.

Three things are checked here that the database cannot check: that the
figure is on the scale, that the date is a real day in the recent past
rather than one somebody typed, and that the comment is prose. The
fourth rule, one report per person per day, is the database's, because
a form only ever sees one request.
"""
from datetime import date, timedelta
from decimal import Decimal

from django import forms

from snorkel_locations import submissions

from .display import MAX_AGE_DAYS, SCALE_POINTS

COMMENT_MAX = 500

# The slider's range and its step. Anything between, and nothing
# outside: a figure of 3.7 did not come from the slider, and one of 40
# is not a report about the sea.
VISIBILITY_MIN = Decimal("0")
VISIBILITY_MAX = Decimal(str(SCALE_POINTS[-1]))
VISIBILITY_STEP = Decimal("0.5")


class VisibilityReportForm(forms.Form):
    """One figure, the day it was seen, and optionally a note."""

    visibility = forms.DecimalField(
        max_digits=4, decimal_places=1,
        min_value=VISIBILITY_MIN, max_value=VISIBILITY_MAX,
        error_messages={
            "required": "Move the slider to say how far you could see.",
            "invalid": "Move the slider to say how far you could see.",
            "min_value": "Visibility cannot be less than nothing.",
            "max_value": f"The scale stops at {VISIBILITY_MAX:g} metres.",
        },
    )
    observed_at = forms.DateField(
        error_messages={
            "required": "Add the date you snorkelled here.",
            "invalid": "Add the date you snorkelled here, as a real date.",
        },
    )
    comment = forms.CharField(required=False, strip=True)

    def clean_visibility(self):
        """On the scale, and on one of its steps.

        The slider only produces halves, so a figure that is not one
        was not typed by the slider. Rounded to the nearest step rather
        than rejected: somebody arriving with 3.7 metres is not doing
        anything wrong, and the scale is not precise enough for the
        difference to mean anything.
        """
        value = self.cleaned_data["visibility"]
        steps = (value / VISIBILITY_STEP).to_integral_value()
        return (steps * VISIBILITY_STEP).quantize(Decimal("0.1"))

    def clean_observed_at(self):
        """A day that has happened, and happened recently enough.

        The same window the create form uses, read from the same
        constant, because a report is a report wherever it was filed
        from. Tomorrow is refused outright: nobody is reporting on
        water they have not been in.
        """
        when = self.cleaned_data["observed_at"]
        today = date.today()

        if when > today:
            raise forms.ValidationError("The date cannot be in the future.")
        if when < today - timedelta(days=MAX_AGE_DAYS):
            raise forms.ValidationError(
                f"Reports must be for a date within the last "
                f"{MAX_AGE_DAYS} days.")
        return when

    def clean_comment(self):
        """Plain text, and no more of it than was asked for.

        Cleaned by the same function every other piece of submitted
        prose on the site goes through, rather than a second one
        written here. Asked for one character more than the limit so
        that too long can be told apart from exactly long enough, and
        rejected rather than quietly trimmed.
        """
        text = submissions.clean_text(self.data.get("comment", ""),
                                      limit=COMMENT_MAX + 1)
        if len(text) > COMMENT_MAX:
            raise forms.ValidationError(
                f"Comments are limited to {COMMENT_MAX} characters.")
        return text
