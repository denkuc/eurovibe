from django import forms

from contest.models import ContestEdition
from contest.seed_data import DEV_FINALISTS, DEV_SEED_YEAR


def finalist_seed_csv():
    lines = ["running_order,country_code,country_name,artist_name,song_title,is_ukraine"]
    for row in DEV_FINALISTS:
        lines.append(
            ",".join(
                [
                    str(row["running_order"]),
                    row["country_code"],
                    _csv_cell(row["country_name"]),
                    _csv_cell(row["artist_name"]),
                    _csv_cell(row["song_title"]),
                    "true" if row.get("is_ukraine") else "",
                ]
            )
        )
    return "\n".join(lines)


def official_results_csv(edition):
    lines = ["final_rank,entry_id,country_name"]
    if edition:
        for entry in edition.entries.order_by("running_order"):
            lines.append(f"{entry.running_order},{entry.id},{_csv_cell(entry.country_name)}")
    return "\n".join(lines)


class EditionForm(forms.Form):
    year = forms.IntegerField(min_value=1956, initial=DEV_SEED_YEAR)


class FinalistImportForm(forms.Form):
    finalists_csv = forms.CharField(
        label="Фіналісти CSV",
        widget=forms.Textarea(attrs={"rows": 12}),
        initial=finalist_seed_csv,
    )


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
