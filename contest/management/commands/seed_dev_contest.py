from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contest.models import ContestEdition, ContestEntry
from contest.seed_data import DEV_FINALISTS, DEV_SEED_YEAR


class Command(BaseCommand):
    help = "Seed the PRD development contest edition and finalists."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Replace existing 2026 finalists. Allowed only while the edition is in setup state.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        edition, edition_created = ContestEdition.objects.get_or_create(year=DEV_SEED_YEAR)

        if not edition.can_edit_finalists:
            raise CommandError("Cannot seed finalists after setup state.")

        if options["reset"]:
            edition.entries.all().delete()

        created_count = 0
        updated_count = 0
        for finalist in DEV_FINALISTS:
            entry, created = ContestEntry.objects.update_or_create(
                edition=edition,
                running_order=finalist["running_order"],
                defaults={
                    "country_name": finalist["country_name"],
                    "country_code": finalist["country_code"],
                    "artist_name": finalist["artist_name"],
                    "song_title": finalist["song_title"],
                    "is_ukraine": finalist.get("is_ukraine", False),
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded edition {edition.year}: edition_created={edition_created}, "
                f"entries_created={created_count}, entries_updated={updated_count}."
            )
        )

