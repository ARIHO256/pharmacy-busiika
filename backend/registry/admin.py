from django.contrib import admin

from .models import CareRelationship, Organization, OrganizationLocation, PractitionerCredential, PractitionerRole

admin.site.register(Organization)
admin.site.register(OrganizationLocation)
admin.site.register(PractitionerCredential)
admin.site.register(PractitionerRole)
admin.site.register(CareRelationship)
