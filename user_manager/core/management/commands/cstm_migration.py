from django.core.management.base import BaseCommand
from core.models import Deal

class Command(BaseCommand):
    help = "Update deal results from client results"

    def handle(self, *args, **kwargs):
        deals = Deal.objects.all()

        for deal in deals:
            deal.result = deal.client.results
            deal.save()

        self.stdout.write(self.style.SUCCESS("Deals updated successfully"))