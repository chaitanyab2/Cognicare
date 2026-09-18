"""
URL configuration for Cognicare project.
Phase 2: Authentication & User Foundation.
Phase 16: Progressive Web App (PWA) Foundation & Offline Fallback.
"""

import os
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, Http404
from django.shortcuts import redirect
from django.urls import path, include
from django.views.generic import TemplateView


def service_worker_view(request):
    """Serve Service Worker from root URL with Service-Worker-Allowed header."""
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'cognicare-sw.js')
    if not os.path.exists(sw_path):
        raise Http404("Service worker script not found.")
    with open(sw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def manifest_view(request):
    """Serve Web App Manifest from root URL with proper MIME type."""
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.webmanifest')
    if not os.path.exists(manifest_path):
        raise Http404("Manifest not found.")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        content = f.read()
    response = HttpResponse(content, content_type='application/manifest+json')
    response['Cache-Control'] = 'public, max-age=86400'
    return response


urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('games/', include('apps.games.urls', namespace='games')),
    path('memories/', include('apps.memories.urls', namespace='memories')),
    path('routines/', include('apps.routines.urls', namespace='routines')),
    path('sw.js', service_worker_view, name='service_worker'),
    path('manifest.webmanifest', manifest_view, name='root_manifest'),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('', lambda request: redirect('accounts:login'), name='root_redirect'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
