from django.shortcuts import render

from .services import get_current_edition


def finalist_list(request):
    edition = get_current_edition()
    entries = []
    if edition:
        entries = edition.entries.all()
    return render(request, "contest/finalist_list.html", {"edition": edition, "entries": entries})

