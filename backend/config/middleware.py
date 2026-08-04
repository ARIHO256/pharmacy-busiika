import re
import uuid

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


class RequestIDMiddleware:
    """Attach a safe correlation ID to every request and response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.META.get("HTTP_X_REQUEST_ID", "").strip()
        request_id = supplied if _REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid.uuid4())
        request.request_id = request_id
        request.META["HTTP_X_REQUEST_ID"] = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
