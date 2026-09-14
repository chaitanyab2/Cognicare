"""
URL configuration for Cognicare project.
Phase 2: Authentication & User Foundation.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('games/', include('apps.games.urls', namespace='games')),
    path('memories/', include('apps.memories.urls', namespace='memories')),
    path('', lambda request: redirect('accounts:login'), name='root_redirect'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
