from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contest.models import ContestEdition
from contest.seed_data import DEV_SEED_YEAR
from contest.services import seed_finalists


class Command(BaseCommand):
    help = "Seed the current contest edition and finalists."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Replace existing finalists from seed data. Allowed only while the edition is in setup state.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        edition, edition_created = ContestEdition.objects.get_or_create(year=DEV_SEED_YEAR)

        if not edition.can_edit_finalists:
            raise CommandError("Cannot seed finalists after setup state.")

        if options["reset"]:
            edition.entries.all().delete()

        before_ids = set(edition.entries.values_list("running_order", flat=True))
        count = seed_finalists(edition=edition)
        after_ids = set(edition.entries.values_list("running_order", flat=True))
        created_count = len(after_ids - before_ids)
        updated_count = count - created_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded edition {edition.year}: edition_created={edition_created}, "
                f"entries_created={created_count}, entries_updated={updated_count}."
            )
        )
