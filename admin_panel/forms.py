from django import forms

from contest.models import ContestEdition
from contest.seed_data import DEV_SEED_YEAR


def official_results_csv(edition):
    lines = ["final_rank,entry_id,country_name,jury_points,televote_points,total_points"]
    if edition:
        results = {result.contest_entry_id: result for result in edition.official_results.all()}
        for entry in edition.entries.order_by("running_order"):
            result = results.get(entry.id)
            final_rank = result.final_rank if result else entry.running_order
            jury_points = result.jury_points if result else ""
            televote_points = result.televote_points if result else ""
            total_points = result.total_points if result else ""
            lines.append(
                f"{final_rank},{entry.id},{_csv_cell(entry.country_name)},"
                f"{jury_points},{televote_points},{total_points}"
            )
    return "\n".join(lines)


class EditionForm(forms.Form):
    year = forms.IntegerField(min_value=1956, initial=DEV_SEED_YEAR)


class OfficialResultsForm(forms.Form):
    results_csv = forms.CharField(
        label="Офіційний порядок CSV",
        widget=forms.Textarea(attrs={"rows": 12}),
    )

    def __init__(self, *args, edition=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["results_csv"].initial = official_results_csv(edition)


def create_edition(year):
    return ContestEdition.objects.get_or_create(year=year)[0]


def _csv_cell(value):
    text = str(value)
    if any(char in text for char in [",", '"', "\n"]):
        return '"' + text.replace('"', '""') + '"'
    return text
