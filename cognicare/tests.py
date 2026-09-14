"""
Basic foundation tests for Cognicare project.
Phase 1: Environment & Project Foundation.
"""

from django.conf import settings
from django.db import connection
from django.test import TestCase, Client


class FoundationTestCase(TestCase):
    """Verifies core Django foundation configuration."""

    def test_database_connection(self):
        """Verifies that SQLite database is connected and operable."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            self.assertEqual(row[0], 1)

    def test_settings_foundation(self):
        """Verifies critical settings are properly configured."""
        self.assertEqual(settings.TIME_ZONE, 'Asia/Kolkata')
        self.assertTrue(settings.USE_I18N)
        self.assertTrue(settings.USE_TZ)
        self.assertEqual(settings.STATIC_URL, '/static/')
        self.assertEqual(settings.MEDIA_URL, '/media/')
        self.assertIn(settings.BASE_DIR / 'templates', settings.TEMPLATES[0]['DIRS'])

    def test_admin_redirect_and_session(self):
        """Verifies middleware chain, session engine, and URL resolution."""
        client = Client()
        response = client.get('/admin/')
        # Unauthenticated request to /admin/ should redirect to /admin/login/
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/admin/login/' in response.headers.get('Location', ''))
