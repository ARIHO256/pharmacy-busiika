from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def user_from_token(raw):
    try:
        validated = JWTAuthentication().get_validated_token(raw)
        return JWTAuthentication().get_user(validated)
    except Exception:
        return AnonymousUser()


class QueryStringJWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [""])[0]
        headers = dict(scope.get("headers") or [])
        authorization = headers.get(b"authorization", b"").decode()
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
        scope["user"] = await user_from_token(token) if token else AnonymousUser()
        return await self.app(scope, receive, send)
