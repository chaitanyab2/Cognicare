import json
import os
from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse
from PIL import Image


class PWATests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_service_worker_endpoint(self):
        """Test that /sw.js is served with proper MIME type and Service-Worker-Allowed header."""
        response = self.client.get('/sw.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/javascript')
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertIn('cognicare-v1', response.content.decode('utf-8'))

    def test_manifest_endpoint(self):
        """Test that /manifest.webmanifest returns valid JSON with all required PWA fields."""
        response = self.client.get('/manifest.webmanifest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/manifest+json', response['Content-Type'])
        
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['name'], 'Cognicare — Dementia Care & Memory Assistant')
        self.assertEqual(data['short_name'], 'Cognicare')
        self.assertEqual(data['start_url'], '/')
        self.assertEqual(data['scope'], '/')
        self.assertEqual(data['display'], 'standalone')
        self.assertEqual(data['theme_color'], '#0f766e')
        self.assertEqual(data['background_color'], '#fbf9f5')
        self.assertTrue(len(data['icons']) >= 4)

    def test_manifest_icons_exist_and_valid(self):
        """Verify all icon paths listed in manifest actually exist and have correct sizes."""
        manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.webmanifest')
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for icon_entry in data['icons']:
            src = icon_entry['src'].lstrip('/')
            file_path = os.path.join(settings.BASE_DIR, src)
            self.assertTrue(os.path.exists(file_path), f"Missing icon file: {file_path}")
            
            if file_path.endswith('.png'):
                with Image.open(file_path) as img:
                    expected_size = icon_entry['sizes']
                    w, h = map(int, expected_size.split('x'))
                    self.assertEqual(img.size, (w, h), f"Size mismatch for {file_path}")

    def test_offline_page_endpoint(self):
        """Verify /offline/ view returns status 200 and has self-contained offline elements."""
        response = self.client.get(reverse('offline'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        self.assertIn('offline', content.lower())
        self.assertIn('reconnect-btn', content)
        self.assertIn('cognicare-theme', content)
        self.assertIn('data-theme', content)

    def test_base_html_includes_pwa_metadata(self):
        """Verify base.html renders manifest, theme-color, and PWA scripts."""
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        self.assertIn('rel="manifest"', content)
        self.assertIn('name="theme-color"', content)
        self.assertIn('apple-touch-icon', content)
        self.assertIn('cognicare-pwa.js', content)
        self.assertIn('pwa-install-banner', content)
