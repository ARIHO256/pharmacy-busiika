from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


class PrivateLocalStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        super().__init__(**kwargs)

    def url(self, name):
        raise ValueError("Private documents must be downloaded through an authorized API.")


def private_storage():
    return storages["private"]
