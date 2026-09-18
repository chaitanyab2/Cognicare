"""
Unit and Integration Tests for Patient Dashboard Personalization.
Phase 13C-3B: Today's Gentle Suggestion Card & Session Launch Integration.
"""

import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone, translation

from apps.accounts.models import Role
from apps.games.models import Game, GameSession

User = get_user_model()


class PatientDashboardPersonalizationTests(TestCase):
    """
    Validates that:
    1. The patient portal renders 'Today's Gentle Suggestion' card.
    2. Suggestion details match the explainable personalization service output.
    3. The 'Play Activity' button POSTs to games:start_session with the recommended difficulty.
    4. Start session handles invalid, clamped, and missing difficulty gracefully.
    5. Tenant isolation ensures patient data never leaks across members.
    6. Both English and Assamese localizations render accurately without corrupting user data.
    7. Caregivers are prevented from accessing the patient dashboard (403 Forbidden).
    8. The 4 core pillars of Cognicare are preserved below the suggestion card.
    """

    def setUp(self):
        self.client = Client()

        # Primary Patient
        self.patient = User.objects.create_user(
            username='patient_joy',
            email='joy@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Joyprada',
            last_name='Baruah'
        )

        # Secondary Patient for isolation testing
        self.other_patient = User.objects.create_user(
            username='patient_ratul',
            email='ratul@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Ratul',
            last_name='Sarma'
        )

        # Caregiver user
        self.caregiver = User.objects.create_user(
            username='caregiver_mina',
            email='mina@example.com',
            password='Password123!',
            role=Role.CAREGIVER,
            first_name='Mina',
            last_name='Baruah'
        )

        # Retrieve registered games
        self.game_memory = Game.objects.get(slug='memory-market')
        self.game_journey = Game.objects.get(slug='daily-life-journey')
        self.game_focus = Game.objects.get(slug='focus-finder')

    # =========================================================================
    # 1. COLD START DASHBOARD RENDERING
    # =========================================================================
    def test_patient_portal_renders_cold_start_suggestion(self):
        """A new patient sees 'Today's Gentle Suggestion' with Memory Market at Level 1."""
        self.client.force_login(self.patient)
        url = reverse('accounts:patient_portal')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('recommendation', response.context)
        rec = response.context['recommendation']
        self.assertIsNotNone(rec)
        self.assertEqual(rec['game_slug'], 'memory-market')
        self.assertEqual(rec['recommended_difficulty'], 1)

        # HTML content assertions
        content = response.content.decode('utf-8')
        self.assertIn("Today's Gentle Suggestion", content)
        self.assertIn("Memory Market", content)
        self.assertIn("Working Memory", content)
        self.assertIn("Level 1: Gentle", content)
        self.assertIn("This is a gentle activity for today&#x27;s practice.", content)

        # Action form and buttons
        expected_start_url = reverse('games:start_session', kwargs={'slug': 'memory-market'})
        self.assertIn(f'action="{expected_start_url}"', content)
        self.assertIn('name="difficulty" value="1"', content)
        self.assertIn("Play Activity", content)

        # "How to Play" link
        expected_detail_url = reverse('games:detail', kwargs={'slug': 'memory-market'})
        self.assertIn(f'href="{expected_detail_url}"', content)
        self.assertIn("How to Play", content)

    # =========================================================================
    # 2. LAUNCH SESSION VIA POST FORM
    # =========================================================================
    def test_play_activity_form_starts_session_at_recommended_difficulty(self):
        """Clicking 'Play Activity' creates an active GameSession at difficulty 1 and redirects to play."""
        self.client.force_login(self.patient)
        start_url = reverse('games:start_session', kwargs={'slug': 'memory-market'})

        response = self.client.post(start_url, {'difficulty': 1})
        self.assertEqual(response.status_code, 302)

        session = GameSession.objects.filter(member=self.patient, game=self.game_memory).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.difficulty, 1)
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)

        expected_play_url = reverse('games:play', kwargs={'session_id': session.id})
        self.assertRedirects(response, expected_play_url)

    # =========================================================================
    # 3. DIFFICULTY CLAMPING & RESILIENCE
    # =========================================================================
    def test_start_session_clamps_and_handles_invalid_difficulty(self):
        """Difficulty is clamped between 1 and 5 and defaults safely on invalid inputs."""
        self.client.force_login(self.patient)
        start_url = reverse('games:start_session', kwargs={'slug': 'memory-market'})

        # High difficulty clamped to 5
        self.client.post(start_url, {'difficulty': 99})
        session = GameSession.objects.filter(member=self.patient).order_by('-id').first()
        self.assertEqual(session.difficulty, 5)

        # Low difficulty clamped to 1
        self.client.post(start_url, {'difficulty': -3})
        session = GameSession.objects.filter(member=self.patient).order_by('-id').first()
        self.assertEqual(session.difficulty, 1)

        # Malformed non-numeric string defaults to 1
        self.client.post(start_url, {'difficulty': 'invalid_level'})
        session = GameSession.objects.filter(member=self.patient).order_by('-id').first()
        self.assertEqual(session.difficulty, 1)

    # =========================================================================
    # 4. PROGRESSION STATE ON DASHBOARD
    # =========================================================================
    def test_patient_portal_renders_progression_suggestion(self):
        """Consistent high performance triggers Level 2 progression suggestion on dashboard."""
        now = timezone.now()
        for i in range(2):
            GameSession.objects.create(
                member=self.patient,
                game=self.game_memory,
                status=GameSession.Status.COMPLETED,
                difficulty=1,
                score=5,
                max_score=5,
                accuracy=Decimal('90.00'),
                total_time_ms=12000,
                started_at=now - datetime.timedelta(minutes=30 - i * 10),
                completed_at=now - datetime.timedelta(minutes=25 - i * 10)
            )

        self.client.force_login(self.patient)
        response = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(response.status_code, 200)

        rec = response.context['recommendation']
        self.assertEqual(rec['recommended_difficulty'], 2)
        self.assertEqual(rec['game_slug'], 'memory-market')

        content = response.content.decode('utf-8')
        self.assertIn("Level 2: Comfortable", content)
        self.assertIn('name="difficulty" value="2"', content)
        self.assertIn("You have been doing well with this activity", content)

    # =========================================================================
    # 5. GENTLE REINFORCEMENT ON DASHBOARD
    # =========================================================================
    def test_patient_portal_renders_gentle_reinforcement_suggestion(self):
        """Lower accuracy triggers gentle reinforcement at Level 1."""
        now = timezone.now()
        GameSession.objects.create(
            member=self.patient,
            game=self.game_focus,
            status=GameSession.Status.COMPLETED,
            difficulty=2,
            score=2,
            max_score=5,
            accuracy=Decimal('40.00'),
            total_time_ms=25000,
            started_at=now - datetime.timedelta(minutes=20),
            completed_at=now - datetime.timedelta(minutes=15)
        )

        self.client.force_login(self.patient)
        response = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(response.status_code, 200)

        rec = response.context['recommendation']
        self.assertEqual(rec['game_slug'], 'focus-finder')
        self.assertEqual(rec['recommended_difficulty'], 1)

        content = response.content.decode('utf-8')
        self.assertIn("Focus Finder", content)
        self.assertIn("Level 1: Gentle", content)
        self.assertIn("This activity gives you a chance to practice at a comfortable and unhurried pace.", content)

    # =========================================================================
    # 6. TENANT ISOLATION
    # =========================================================================
    def test_dashboard_recommendation_tenant_isolation(self):
        """Patient A's sessions never alter Patient B's recommendations."""
        now = timezone.now()
        # Patient A has multiple completed sessions
        for i in range(3):
            GameSession.objects.create(
                member=self.patient,
                game=self.game_memory,
                status=GameSession.Status.COMPLETED,
                difficulty=1,
                score=5,
                max_score=5,
                accuracy=Decimal('100.00'),
                total_time_ms=10000,
                started_at=now - datetime.timedelta(minutes=30 - i * 5),
                completed_at=now - datetime.timedelta(minutes=25 - i * 5)
            )

        # Other patient has 0 sessions (Cold Start)
        self.client.force_login(self.other_patient)
        response = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(response.status_code, 200)

        rec = response.context['recommendation']
        self.assertTrue(rec['is_cold_start'])
        self.assertEqual(rec['recommended_difficulty'], 1)
        self.assertEqual(rec['stats']['total_completed_sessions'], 0)

    # =========================================================================
    # 7. CAREGIVER ACCESS PROTECTION
    # =========================================================================
    def test_caregiver_cannot_access_patient_portal(self):
        """Caregiver cannot view the patient portal and receives 403 Forbidden."""
        self.client.force_login(self.caregiver)
        response = self.client.get(reverse('accounts:patient_portal'))
        # @patient_required returns 403 for caregivers
        self.assertEqual(response.status_code, 403)

    # =========================================================================
    # 8. ASSAMESE LOCALIZATION & USER DATA INTEGRITY
    # =========================================================================
    def test_dashboard_recommendation_assamese_localization(self):
        """Assamese translation renders correctly while user and game names remain intact."""
        self.client.force_login(self.patient)

        # Activate Assamese language
        with translation.override('as'):
            response = self.client.get(reverse('accounts:patient_portal'), HTTP_ACCEPT_LANGUAGE='as')
            self.assertEqual(response.status_code, 200)

            content = response.content.decode('utf-8')

            # Localized suggestion header and domain
            self.assertIn("আজিৰ শান্ত পৰামৰ্শ", content)
            self.assertIn("কাৰ্য্যকৰী স্মৃতি", content)
            self.assertIn("স্তৰ 1: শান্তিময়", content)
            self.assertIn("কাৰ্যকলাপ আৰম্ভ কৰক", content)
            self.assertIn("কেনেকৈ খেলিব", content)
            self.assertIn("আজিৰ অনুশীলনৰ বাবে এইটো এটি শান্তিময় কাৰ্যকলাপ।", content)

            # User data and game name must NOT be translated/altered
            self.assertIn("Joyprada", content)
            self.assertIn("Memory Market", content)

    # =========================================================================
    # 9. PRESERVATION OF 4 CORE PILLARS
    # =========================================================================
    def test_patient_portal_preserves_all_core_pillars(self):
        """The 4 core pillars (Cognitive Games, My Memories, Today's Routine, Voice Assistant) are preserved."""
        self.client.force_login(self.patient)
        response = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn("Cognitive Games", content)
        self.assertIn("My Memories", content)
        self.assertIn("Today's Routine", content)
        self.assertIn("Voice Assistant", content)

    # =========================================================================
    # 10. VOICE ASSISTANT DEDICATED PAGE & STT INTEGRATION
    # =========================================================================
    def test_patient_portal_voice_assistant_link_and_dedicated_page(self):
        """Patient portal links to dedicated Voice Assistant page which has accessible STT button and direct touch shortcuts."""
        self.client.force_login(self.patient)
        response = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('id="open-voice-assistant-btn"', content)
        va_url = reverse('accounts:voice_assistant')
        self.assertIn(va_url, content)

        # Now test the dedicated page
        va_response = self.client.get(va_url)
        self.assertEqual(va_response.status_code, 200)
        va_content = va_response.content.decode('utf-8')
        self.assertIn('id="va-mic-btn"', va_content)
        self.assertIn('id="va-status-area"', va_content)
        self.assertIn('class="btn-speech va-hero-mic-btn"', va_content)
        # Direct touch shortcuts present
        self.assertIn(reverse('games:list'), va_content)
        self.assertIn(reverse('routines:patient_routine'), va_content)
        self.assertIn(reverse('memories:patient_memories'), va_content)
        self.assertIn(reverse('accounts:patient_portal'), va_content)

    def test_patient_portal_voice_assistant_localized_in_assamese(self):
        """Voice Assistant dedicated page renders in authentic Assamese when language is 'as'."""
        self.client.post(reverse('set_language'), data={'language': 'as'}, follow=True)
        self.client.force_login(self.patient)
        va_url = reverse('accounts:voice_assistant')
        response = self.client.get(va_url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('কণ্ঠ সহায়ক', content)
        self.assertIn('কবলৈ স্পৰ্শ কৰক', content)
        self.assertIn('পোনপটীয়া স্পৰ্শৰ চৰ্টকাটসমূহ:', content)

