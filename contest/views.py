from django.shortcuts import render

from .services import get_current_edition


def finalist_list(request):
    edition = get_current_edition()
    entries = []
    if edition:
        results = {
            result.contest_entry_id: result
            for result in edition.official_results.select_related("contest_entry").order_by("final_rank")
        }
        entries = list(edition.entries.all())
        for entry in entries:
            entry.official_result = results.get(entry.id)
        if results:
            entries.sort(key=lambda entry: entry.official_result.final_rank if entry.official_result else entry.running_order)
    return render(request, "contest/finalist_list.html", {"edition": edition, "entries": entries})
