"""
Comprehensive Unit Tests for Cognicare Personalization Engine.
Phase 13C-3A: Explainable Personalization Service.
"""

import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone, translation

from apps.accounts.models import Role
from apps.games.models import Game, GameSession
from apps.games.personalization import (
    get_personalized_recommendation,
    RecommendationCategory,
    DIFFICULTY_LABELS,
    GAME_COGNITIVE_DOMAINS,
)
from apps.memories.models import FamiliarPerson

User = get_user_model()


class PersonalizationEngineTests(TestCase):
    """
    Tests the deterministic, explainable personalization service across
    all four cases, member isolation, deterministic tie-breaking, and language safety.
    """

    def setUp(self):
        translation.activate('en')
        # Create test patient 1
        self.patient = User.objects.create_user(
            username='personalization_patient',
            email='pt@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Ananya',
            last_name='Barua'
        )

        # Create test patient 2 (for tenant isolation tests)
        self.patient2 = User.objects.create_user(
            username='other_patient',
            email='pt2@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Bikram',
            last_name='Saikia'
        )

        # Create caregiver (for role validation tests)
        self.caregiver = User.objects.create_user(
            username='caregiver_user',
            email='cg@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )

        # Retrieve registered games
        self.game_memory = Game.objects.get(slug='memory-market')
        self.game_journey = Game.objects.get(slug='daily-life-journey')
        self.game_focus = Game.objects.get(slug='focus-finder')
        self.game_words = Game.objects.get(slug='word-connections')
        self.game_pattern = Game.objects.get(slug='pattern-detective')
        self.game_faces = Game.objects.get(slug='familiar-faces')

    def tearDown(self):
        translation.deactivate()
        super().tearDown()

    # =========================================================================
    # 1. COLD START
    # =========================================================================
    def test_cold_start_recommendation_when_no_history(self):
        """A new patient with 0 completed sessions receives a cold-start recommendation."""
        rec = get_personalized_recommendation(self.patient)

        self.assertIsNotNone(rec)
        self.assertEqual(rec['game_slug'], 'memory-market')
        self.assertEqual(rec['recommended_difficulty'], 1)
        self.assertEqual(rec['difficulty_label'], str(DIFFICULTY_LABELS[1]))
        self.assertEqual(rec['reason_category'], RecommendationCategory.COLD_START)
        self.assertTrue(rec['is_cold_start'])
        self.assertEqual(rec['stats']['total_completed_sessions'], 0)
        self.assertIsNone(rec['stats']['recent_accuracy'])
        self.assertIn("Welcome", str(rec['supportive_headline']))
        self.assertIn("gentle activity", str(rec['supportive_rationale']))

    # =========================================================================
    # 2. ONE COMPLETED GAME
    # =========================================================================
    def test_one_completed_game_recommends_unplayed_domain(self):
        """A patient with 1 completed game with good score is recommended an unplayed domain."""
        now = timezone.now()
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=5,
            max_score=5,
            accuracy=Decimal('100.00'),
            total_time_ms=15000,
            started_at=now - datetime.timedelta(minutes=10),
            completed_at=now - datetime.timedelta(minutes=5)
        )

        rec = get_personalized_recommendation(self.patient)

        self.assertIsNotNone(rec)
        # Next unplayed active game by display_order is daily-life-journey
        self.assertEqual(rec['game_slug'], 'daily-life-journey')
        self.assertEqual(rec['recommended_difficulty'], 1)
        self.assertEqual(rec['reason_category'], RecommendationCategory.DOMAIN_VARIETY)
        self.assertFalse(rec['is_cold_start'])
        self.assertEqual(rec['stats']['total_completed_sessions'], 1)

    # =========================================================================
    # 3. MULTIPLE COMPLETED GAMES
    # =========================================================================
    def test_multiple_completed_games_rotates_to_unplayed_domain(self):
        """Patient with multiple completed games is recommended an unplayed domain."""
        now = timezone.now()
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=4,
            max_score=5,
            accuracy=Decimal('80.00'),
            started_at=now - datetime.timedelta(days=2),
            completed_at=now - datetime.timedelta(days=2)
        )
        GameSession.objects.create(
            member=self.patient,
            game=self.game_journey,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=3,
            max_score=3,
            accuracy=Decimal('100.00'),
            started_at=now - datetime.timedelta(days=1),
            completed_at=now - datetime.timedelta(days=1)
        )

        rec = get_personalized_recommendation(self.patient)

        self.assertIsNotNone(rec)
        # familiar-faces lacks photos, so next eligible is focus-finder
        self.assertEqual(rec['game_slug'], 'focus-finder')
        self.assertEqual(rec['reason_category'], RecommendationCategory.DOMAIN_VARIETY)
        self.assertEqual(rec['recommended_difficulty'], 1)

    # =========================================================================
    # 4. LOWER-PERFORMING GAME / GENTLE REINFORCEMENT
    # =========================================================================
    def test_lower_performing_game_triggers_gentle_reinforcement(self):
        """A game with recent average accuracy < 70% is recommended for gentle practice."""
        now = timezone.now()
        # Game 1: strong performance
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=5,
            max_score=5,
            accuracy=Decimal('95.00'),
            started_at=now - datetime.timedelta(hours=3),
            completed_at=now - datetime.timedelta(hours=3)
        )
        # Game 2: lower performance (50% < 70%)
        GameSession.objects.create(
            member=self.patient,
            game=self.game_journey,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=1,
            max_score=3,
            accuracy=Decimal('50.00'),
            started_at=now - datetime.timedelta(hours=1),
            completed_at=now - datetime.timedelta(hours=1)
        )

        rec = get_personalized_recommendation(self.patient)

        self.assertIsNotNone(rec)
        self.assertEqual(rec['game_slug'], 'daily-life-journey')
        self.assertEqual(rec['recommended_difficulty'], 1)
        self.assertEqual(rec['reason_category'], RecommendationCategory.GENTLE_REINFORCEMENT)
        self.assertIn("Gentle Practice", str(rec['supportive_headline']))
        self.assertIn("comfortable and unhurried pace", str(rec['supportive_rationale']))
        self.assertEqual(rec['stats']['recent_accuracy'], 50.0)

    # =========================================================================
    # 5. STRONG RECENT PERFORMANCE / PROGRESSION
    # =========================================================================
    def test_strong_recent_performance_triggers_progression(self):
        """Consistent strong performance (>= 85% across 2+ sessions) suggests difficulty progression."""
        now = timezone.now()
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=5,
            max_score=5,
            accuracy=Decimal('90.00'),
            started_at=now - datetime.timedelta(hours=2),
            completed_at=now - datetime.timedelta(hours=2)
        )
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=5,
            max_score=5,
            accuracy=Decimal('100.00'),
            started_at=now - datetime.timedelta(hours=1),
            completed_at=now - datetime.timedelta(hours=1)
        )

        rec = get_personalized_recommendation(self.patient)

        self.assertIsNotNone(rec)
        self.assertEqual(rec['game_slug'], 'memory-market')
        self.assertEqual(rec['recommended_difficulty'], 2)  # Stepped up from 1 to 2
        self.assertEqual(rec['reason_category'], RecommendationCategory.PROGRESSION)
        self.assertEqual(rec['difficulty_label'], str(DIFFICULTY_LABELS[2]))
        self.assertIn("Engaging", str(rec['supportive_headline']))
        self.assertEqual(rec['stats']['sessions_at_current_difficulty'], 2)

    def test_single_high_score_does_not_prematurely_advance_difficulty(self):
        """A single session with 100% accuracy does NOT advance difficulty prematurely."""
        now = timezone.now()
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=5,
            max_score=5,
            accuracy=Decimal('100.00'),
            started_at=now - datetime.timedelta(hours=1),
            completed_at=now - datetime.timedelta(hours=1)
        )

        rec = get_personalized_recommendation(self.patient)

        # Should NOT be progression because min sessions for progression is 2
        self.assertNotEqual(rec['reason_category'], RecommendationCategory.PROGRESSION)
        self.assertEqual(rec['reason_category'], RecommendationCategory.DOMAIN_VARIETY)

    # =========================================================================
    # 6. DETERMINISTIC TIE-BREAKING
    # =========================================================================
    def test_multiple_tied_candidates_deterministic_result(self):
        """Tied candidates resolve deterministically across repeated invocations."""
        now = timezone.now()
        # Both focus-finder and word-connections are unplayed
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            accuracy=Decimal('80.00'),
            completed_at=now - datetime.timedelta(days=2)
        )
        GameSession.objects.create(
            member=self.patient,
            game=self.game_journey,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            accuracy=Decimal('80.00'),
            completed_at=now - datetime.timedelta(days=1)
        )

        results = [get_personalized_recommendation(self.patient)['game_slug'] for _ in range(5)]
        # All 5 invocations must produce the exact same game
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(results[0], 'focus-finder')

    def test_tied_low_accuracy_resolves_deterministically(self):
        """Two games with exact same low accuracy resolve by completion time, then display_order."""
        now = timezone.now()
        # Memory Market completed 2 hours ago with 50%
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            accuracy=Decimal('50.00'),
            completed_at=now - datetime.timedelta(hours=2)
        )
        # Daily Life Journey completed 1 hour ago with 50%
        GameSession.objects.create(
            member=self.patient,
            game=self.game_journey,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            accuracy=Decimal('50.00'),
            completed_at=now - datetime.timedelta(hours=1)
        )

        # Least recently completed (oldest timestamp = Memory Market 2 hours ago) wins
        rec = get_personalized_recommendation(self.patient)
        self.assertEqual(rec['game_slug'], 'memory-market')
        self.assertEqual(rec['reason_category'], RecommendationCategory.GENTLE_REINFORCEMENT)

    # =========================================================================
    # 7 & 8. INCOMPLETE AND ABANDONED SESSIONS IGNORED
    # =========================================================================
    def test_in_progress_sessions_ignored(self):
        """Sessions with IN_PROGRESS status are strictly ignored."""
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.IN_PROGRESS,
            difficulty=1,
            accuracy=Decimal('20.00')
        )

        rec = get_personalized_recommendation(self.patient)
        self.assertTrue(rec['is_cold_start'])
        self.assertEqual(rec['stats']['total_completed_sessions'], 0)

    def test_abandoned_sessions_ignored(self):
        """Sessions with ABANDONED status are strictly ignored."""
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.ABANDONED,
            difficulty=1,
            accuracy=Decimal('10.00')
        )

        rec = get_personalized_recommendation(self.patient)
        self.assertTrue(rec['is_cold_start'])
        self.assertEqual(rec['stats']['total_completed_sessions'], 0)

    # =========================================================================
    # 9. MEMBER ISOLATION / PRIVACY
    # =========================================================================
    def test_another_patient_sessions_do_not_affect_recommendation(self):
        """Another patient's session history never leaks into or alters this patient's recommendation."""
        now = timezone.now()
        # Patient 2 plays 20 sessions with 100% accuracy
        for _ in range(10):
            GameSession.objects.create(
                member=self.patient2,
                game=self.game_focus,
                status=GameSession.Status.COMPLETED,
                difficulty=3,
                accuracy=Decimal('100.00'),
                completed_at=now
            )

        # Patient 1 has 0 sessions -> must be cold start
        rec1 = get_personalized_recommendation(self.patient)
        self.assertTrue(rec1['is_cold_start'])
        self.assertEqual(rec1['game_slug'], 'memory-market')
        self.assertEqual(rec1['stats']['total_completed_sessions'], 0)

    # =========================================================================
    # 10. DIFFICULTY BOUNDS
    # =========================================================================
    def test_recommendation_stays_within_valid_difficulty_range(self):
        """Difficulty level never drops below 1 or exceeds 5."""
        now = timezone.now()
        # Create 5 sessions at difficulty 5 with 100% accuracy
        for i in range(5):
            GameSession.objects.create(
                member=self.patient,
                game=self.game_memory,
                status=GameSession.Status.COMPLETED,
                difficulty=5,
                score=5,
                max_score=5,
                accuracy=Decimal('100.00'),
                started_at=now - datetime.timedelta(hours=5 - i),
                completed_at=now - datetime.timedelta(hours=5 - i)
            )

        rec = get_personalized_recommendation(self.patient)
        # Capped at 5, cannot be 6
        self.assertLessEqual(rec['recommended_difficulty'], 5)
        self.assertGreaterEqual(rec['recommended_difficulty'], 1)

    # =========================================================================
    # 11. NON-CLINICAL / SUPPORTIVE LANGUAGE SAFETY
    # =========================================================================
    def test_recommendation_contains_no_medical_or_diagnostic_language(self):
        """Ensures all returned headlines and rationales are completely free of clinical/diagnostic words."""
        prohibited_words = [
            'dementia', 'alzheimer', 'decline', 'impair', 'worse', 'poor',
            'fail', 'deficit', 'diagnosis', 'medical', 'clinical', 'disease',
            'deteriorat', 'patient error', 'retarded'
        ]

        now = timezone.now()
        # Test across different generated states
        # State 1: Cold start
        rec1 = get_personalized_recommendation(self.patient)

        # State 2: Reinforcement
        s1 = GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            accuracy=Decimal('40.00'),
            completed_at=now
        )
        rec2 = get_personalized_recommendation(self.patient)

        # State 3: Progression
        s1.accuracy = Decimal('95.00')
        s1.save()
        GameSession.objects.create(
            member=self.patient,
            game=self.game_memory,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            accuracy=Decimal('95.00'),
            completed_at=now + datetime.timedelta(minutes=5)
        )
        rec3 = get_personalized_recommendation(self.patient)

        for rec in [rec1, rec2, rec3]:
            text_to_check = f"{rec['supportive_headline']} {rec['supportive_rationale']}".lower()
            for bad_word in prohibited_words:
                self.assertNotIn(bad_word, text_to_check, f"Found prohibited clinical word '{bad_word}' in recommendation text!")

    # =========================================================================
    # 12. ROLE VALIDATION
    # =========================================================================
    def test_non_patient_role_raises_value_error(self):
        """Calling recommendation with a non-patient user or None raises ValueError."""
        with self.assertRaises(ValueError):
            get_personalized_recommendation(self.caregiver)

        with self.assertRaises(ValueError):
            get_personalized_recommendation(None)

    # =========================================================================
    # 13. PREREQUISITE PLAYABILITY FILTERING
    # =========================================================================
    def test_familiar_faces_not_recommended_until_photos_exist(self):
        """Familiar Faces requires at least 4 photos; cannot be recommended when unready."""
        # Member has no familiar people -> Familiar Faces cannot be recommended
        rec = get_personalized_recommendation(self.patient)
        self.assertNotEqual(rec['game_slug'], 'familiar-faces')

        # Now add 4 familiar people with valid photos
        valid_img_bytes = b'\xff\xd8\xff\xe0' + b'0' * 500
        for i in range(4):
            dummy_img = SimpleUploadedFile(f"face_{i}.jpg", valid_img_bytes, content_type="image/jpeg")
            FamiliarPerson.objects.create(
                member=self.patient,
                name=f"Relative {i}",
                relationship="Family",
                photo=dummy_img,
                is_active=True
            )

        # Verify it can now be an eligible game
        from apps.games.personalization import is_game_playable_for_member
        self.assertTrue(is_game_playable_for_member(self.game_faces, self.patient))
