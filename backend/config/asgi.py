"""ASGI entrypoint for HTTP and authenticated WebSocket traffic."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from enterprise.routing import websocket_urlpatterns
from enterprise.ws_auth import QueryStringJWTAuthMiddleware

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": QueryStringJWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
})
