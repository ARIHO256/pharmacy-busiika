from django.contrib import admin
from .models import (
    GeneratedClinicalDocument, OperationalAction, ReleaseAcceptance, ResultReview,
    WorkflowActionEvent, WorkflowCase, WorkflowComment,
)

admin.site.register(WorkflowCase)
admin.site.register(WorkflowActionEvent)
admin.site.register(WorkflowComment)
admin.site.register(GeneratedClinicalDocument)
admin.site.register(ResultReview)

admin.site.register(OperationalAction)
admin.site.register(ReleaseAcceptance)
