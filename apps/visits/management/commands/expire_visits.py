from django.core.management.base import BaseCommand

from apps.visits.services import expire_stale_requests


class Command(BaseCommand):
    help = "Mark stale PENDING/APPROVED visits past their window as EXPIRED. Run via cron."

    def handle(self, *args, **options):
        count = expire_stale_requests()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} visit request(s)."))
