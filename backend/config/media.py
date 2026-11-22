"""Development-only media serving with sensitive credential paths blocked.

Production deployments must serve ordinary public media through object storage or
an application proxy. Credential and identity documents are always retrieved
through authenticated API views and must never be exposed by a generic media
URL.
"""

from django.http import Http404
from django.views.static import serve


PRIVATE_MEDIA_PREFIXES = (
    "private-documents/",
    "doctors/licenses/",
    "doctors/certificates/",
    "organizations/licenses/",
    "staff/licenses/",
    "registry/organizations/",
    "registry/credentials/",
)


def debug_media_serve(request, path, document_root=None):
    normalized = (path or "").lstrip("/")
    if normalized.startswith(PRIVATE_MEDIA_PREFIXES):
        raise Http404("Protected healthcare document")
    return serve(request, normalized, document_root=document_root, show_indexes=False)
