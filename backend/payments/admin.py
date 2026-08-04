from django.contrib import admin

from .models import Invoice, JournalEntry, LedgerAccount, Payout, Posting, Subscription

admin.site.register(Invoice)
admin.site.register(Subscription)
admin.site.register(Payout)
admin.site.register(LedgerAccount)
admin.site.register(JournalEntry)
admin.site.register(Posting)
