from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def live(request):
    """Process liveness: no dependency checks, safe for frequent probes."""

    return JsonResponse(
        {
            "status": "ok",
            "service": "healthpilot-api",
            "request_id": getattr(request, "request_id", ""),
        }
    )


@never_cache
@require_GET
def ready(request):
    """Readiness: confirms the API can reach its operational database."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse(
            {
                "status": "unavailable",
                "service": "healthpilot-api",
                "request_id": getattr(request, "request_id", ""),
            },
            status=503,
        )
    return JsonResponse(
        {
            "status": "ready",
            "service": "healthpilot-api",
            "request_id": getattr(request, "request_id", ""),
        }
    )
