from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.games.models import Game, GameSession, GameRound

CustomUser = get_user_model()


class GameModelTests(TestCase):
    """Verifies Game registry and the six approved initial games."""

    def test_six_approved_games_exist(self):
        expected_slugs = [
            'memory-market',
            'daily-life-journey',
            'familiar-faces',
            'focus-finder',
            'word-connections',
            'pattern-detective',
        ]
        games = list(Game.objects.filter(slug__in=expected_slugs))
        self.assertEqual(len(games), 6)

        slugs = [g.slug for g in games]
        for slug in expected_slugs:
            self.assertIn(slug, slugs)

    def test_game_display_ordering(self):
        games = list(Game.objects.all().order_by('display_order'))
        display_orders = [g.display_order for g in games]
        self.assertEqual(display_orders, sorted(display_orders))

    def test_game_str_representation(self):
        game = Game.objects.get(slug='memory-market')
        self.assertEqual(str(game), 'Memory Market')


class GameSessionTests(TestCase):
    """Tests for GameSession data model, constraints, and validation."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='session_member',
            email='sm@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='session_caregiver',
            email='sc@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.game = Game.objects.get(slug='memory-market')

    def test_valid_game_session_creation(self):
        session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            status=GameSession.Status.IN_PROGRESS,
            difficulty=2,
            score=4,
            max_score=5,
            accuracy=80.00,
            total_time_ms=12500
        )
        self.assertEqual(session.member, self.member)
        self.assertEqual(session.game, self.game)
        self.assertEqual(session.difficulty, 2)
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)
        self.assertEqual(session.score, 4)
        self.assertEqual(session.max_score, 5)
        self.assertEqual(float(session.accuracy), 80.00)
        self.assertEqual(session.total_time_ms, 12500)
        self.assertIsNotNone(session.started_at)
        self.assertIn("Memory Market", str(session))

    def test_status_choices(self):
        for status_val in [GameSession.Status.IN_PROGRESS, GameSession.Status.COMPLETED, GameSession.Status.ABANDONED]:
            session = GameSession.objects.create(
                member=self.member,
                game=self.game,
                status=status_val
            )
            self.assertEqual(session.status, status_val)

    def test_invalid_difficulty_low_rejected(self):
        with self.assertRaises(ValidationError):
            session = GameSession(
                member=self.member,
                game=self.game,
                difficulty=0  # Below 1
            )
            session.save()

    def test_invalid_difficulty_high_rejected(self):
        with self.assertRaises(ValidationError):
            session = GameSession(
                member=self.member,
                game=self.game,
                difficulty=6  # Above 5
            )
            session.save()

    def test_negative_time_rejected(self):
        with self.assertRaises(ValidationError):
            session = GameSession(
                member=self.member,
                game=self.game,
                total_time_ms=-100
            )
            session.save()

    def test_negative_score_rejected(self):
        with self.assertRaises(ValidationError):
            session = GameSession(
                member=self.member,
                game=self.game,
                score=-1
            )
            session.save()

    def test_accuracy_out_of_bounds_rejected(self):
        with self.assertRaises(ValidationError):
            session = GameSession(
                member=self.member,
                game=self.game,
                accuracy=105.00
            )
            session.save()

    def test_negative_max_score_rejected(self):
        with self.assertRaises(ValidationError):
            session = GameSession(
                member=self.member,
                game=self.game,
                max_score=-5
            )
            session.save()

    def test_completed_at_nullable(self):
        session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            status=GameSession.Status.IN_PROGRESS,
            completed_at=None
        )
        self.assertIsNone(session.completed_at)

    def test_caregiver_cannot_be_session_member(self):
        # A user with Role.CAREGIVER must be rejected by clean()
        with self.assertRaises(ValidationError):
            session = GameSession(
                member=self.caregiver,
                game=self.game
            )
            session.save()


class GameRoundTests(TestCase):
    """Tests for GameRound data model, telemetry storage, and constraints."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='round_member',
            email='rm@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.game = Game.objects.get(slug='memory-market')
        self.session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=1
        )

    def test_valid_round_creation_with_json_data(self):
        stimulus = {'items': ['tea', 'ginger', 'honey']}
        expected = {'selection': ['tea', 'ginger']}
        actual = {'selection': ['tea', 'ginger']}

        round_obj = GameRound.objects.create(
            session=self.session,
            round_number=1,
            stimulus_data=stimulus,
            expected_response=expected,
            actual_response=actual,
            is_correct=True,
            response_time_ms=1850,
            mistake_count=0,
            hints_used=0
        )
        self.assertEqual(round_obj.session, self.session)
        self.assertEqual(round_obj.round_number, 1)
        self.assertEqual(round_obj.stimulus_data['items'], ['tea', 'ginger', 'honey'])
        self.assertEqual(round_obj.actual_response['selection'], ['tea', 'ginger'])
        self.assertTrue(round_obj.is_correct)
        self.assertEqual(round_obj.response_time_ms, 1850)
        self.assertIn("Correct", str(round_obj))

    def test_duplicate_round_number_in_same_session_prevented(self):
        GameRound.objects.create(
            session=self.session,
            round_number=1,
            is_correct=True
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            GameRound.objects.create(
                session=self.session,
                round_number=1,  # Duplicate round in same session
                is_correct=False
            )

    def test_different_sessions_can_have_same_round_number(self):
        session2 = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=1
        )
        r1 = GameRound.objects.create(session=self.session, round_number=1)
        r2 = GameRound.objects.create(session=session2, round_number=1)
        self.assertEqual(r1.round_number, r2.round_number)

    def test_round_number_must_be_positive(self):
        with self.assertRaises(ValidationError):
            round_obj = GameRound(
                session=self.session,
                round_number=0  # Invalid, must be >= 1
            )
            round_obj.save()

    def test_negative_response_time_rejected(self):
        with self.assertRaises((ValidationError, IntegrityError)):
            round_obj = GameRound(
                session=self.session,
                round_number=2,
                response_time_ms=-50
            )
            round_obj.save()

    def test_negative_mistake_count_rejected(self):
        with self.assertRaises((ValidationError, IntegrityError)):
            round_obj = GameRound(
                session=self.session,
                round_number=2,
                mistake_count=-1
            )
            round_obj.save()

    def test_negative_hints_used_rejected(self):
        with self.assertRaises((ValidationError, IntegrityError)):
            round_obj = GameRound(
                session=self.session,
                round_number=2,
                hints_used=-2
            )
            round_obj.save()


class GameRoutingTests(TestCase):
    """Verifies authentication and patient-role access rules on gameplay endpoints."""

    def setUp(self):
        self.client = Client()
        self.patient = CustomUser.objects.create_user(
            username='patient_gamer',
            email='pg@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_viewer',
            email='cv@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.game = Game.objects.get(slug='memory-market')

    def test_games_catalog_requires_authentication(self):
        url = reverse('games:list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_patient_can_access_games_catalog(self):
        self.client.login(username='patient_gamer', password='Password123!')
        response = self.client.get(reverse('games:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'games/game_list.html')
        self.assertContains(response, "Memory Market")
        self.assertContains(response, "Ready to Play")

    def test_caregiver_forbidden_from_games_catalog(self):
        self.client.login(username='caregiver_viewer', password='Password123!')
        response = self.client.get(reverse('games:list'))
        self.assertEqual(response.status_code, 403)

    def test_patient_can_access_memory_market_detail(self):
        self.client.login(username='patient_gamer', password='Password123!')
        response = self.client.get(reverse('games:detail', kwargs={'slug': 'memory-market'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'games/game_detail.html')
        self.assertContains(response, "How to Play")
        self.assertContains(response, "Start Activity")

    def test_caregiver_forbidden_from_game_detail(self):
        self.client.login(username='caregiver_viewer', password='Password123!')
        response = self.client.get(reverse('games:detail', kwargs={'slug': 'memory-market'}))
        self.assertEqual(response.status_code, 403)

    def test_invalid_game_slug_returns_404(self):
        self.client.login(username='patient_gamer', password='Password123!')
        response = self.client.get(reverse('games:detail', kwargs={'slug': 'non-existent-game'}))
        self.assertEqual(response.status_code, 404)


class MemoryMarketSessionLifecycleTests(TestCase):
    """Verifies complete multi-round session lifecycle, telemetry, and calculations."""

    def setUp(self):
        self.client = Client()
        self.patient = CustomUser.objects.create_user(
            username='memory_tester',
            email='mt@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.client.login(username='memory_tester', password='Password123!')
        self.game = Game.objects.get(slug='memory-market')

    def test_start_activity_creates_fresh_in_progress_session(self):
        start_url = reverse('games:start_session', kwargs={'slug': 'memory-market'})
        response = self.client.post(start_url, {'difficulty': 1})
        
        self.assertEqual(response.status_code, 302)
        session = GameSession.objects.filter(member=self.patient, game=self.game).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)
        self.assertEqual(session.difficulty, 1)
        self.assertEqual(session.score, 0)
        self.assertEqual(session.max_score, 11)
        self.assertIsNone(session.completed_at)
        self.assertEqual(response.url, reverse('games:play', kwargs={'session_id': session.id}))

    def test_every_start_action_creates_fresh_session(self):
        start_url = reverse('games:start_session', kwargs={'slug': 'memory-market'})
        self.client.post(start_url, {'difficulty': 1})
        self.client.post(start_url, {'difficulty': 1})
        
        count = GameSession.objects.filter(member=self.patient, game=self.game).count()
        self.assertEqual(count, 2)

    def test_full_three_round_gameplay_and_completion(self):
        # 1. Start Session
        start_url = reverse('games:start_session', kwargs={'slug': 'memory-market'})
        self.client.post(start_url, {'difficulty': 1})
        session = GameSession.objects.filter(member=self.patient).latest('id')

        # 2. Access Gameplay
        play_url = reverse('games:play', kwargs={'session_id': session.id})
        res = self.client.get(play_url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'games/memory_market.html')
        self.assertContains(res, "Round 1 of 3")

        # 3. Submit Round 1 (3 items: apples, milk, bread)
        submit_url = reverse('games:submit_round', kwargs={'session_id': session.id})
        r1_payload = {
            'round_number': 1,
            'selected_ids': ['apples', 'milk', 'bread'],
            'response_time_ms': 2500,
            'hints_used': 0
        }
        res_r1 = self.client.post(submit_url, r1_payload, content_type='application/json')
        self.assertEqual(res_r1.status_code, 200)
        data_r1 = res_r1.json()
        self.assertTrue(data_r1['success'])
        self.assertTrue(data_r1['evaluation']['is_correct'])
        self.assertTrue(data_r1['has_next_round'])
        self.assertEqual(data_r1['next_round_number'], 2)

        # Verify Round 1 stored in DB
        round1_obj = session.rounds.get(round_number=1)
        self.assertTrue(round1_obj.is_correct)
        self.assertEqual(round1_obj.response_time_ms, 2500)
        self.assertEqual(round1_obj.mistake_count, 0)
        self.assertEqual(round1_obj.actual_response['selected_ids'], ['apples', 'milk', 'bread'])

        # Duplicate round 1 rejected
        res_dup = self.client.post(submit_url, r1_payload, content_type='application/json')
        self.assertEqual(res_dup.status_code, 400)

        # 4. Submit Round 2 (targets: tea, honey, rice, bananas - submit 3 correct, 1 missed)
        r2_payload = {
            'round_number': 2,
            'selected_ids': ['tea', 'honey', 'rice'],
            'response_time_ms': 3200,
            'hints_used': 0
        }
        res_r2 = self.client.post(submit_url, r2_payload, content_type='application/json')
        self.assertEqual(res_r2.status_code, 200)
        data_r2 = res_r2.json()
        self.assertFalse(data_r2['evaluation']['is_correct'])  # Missed bananas
        self.assertEqual(data_r2['evaluation']['score'], 3)
        self.assertEqual(data_r2['evaluation']['mistake_count'], 1)  # 1 missed
        self.assertTrue(data_r2['has_next_round'])

        # 5. Submit Round 3 (final round: targets: carrots, potatoes, flowers, oranges)
        r3_payload = {
            'round_number': 3,
            'selected_ids': ['carrots', 'potatoes', 'flowers', 'oranges'],
            'response_time_ms': 4000,
            'hints_used': 0
        }
        res_r3 = self.client.post(submit_url, r3_payload, content_type='application/json')
        self.assertEqual(res_r3.status_code, 200)
        data_r3 = res_r3.json()
        self.assertTrue(data_r3['evaluation']['is_correct'])
        self.assertFalse(data_r3['has_next_round'])  # Final round complete

        # 6. Complete Session
        complete_url = reverse('games:complete_session', kwargs={'session_id': session.id})
        res_comp = self.client.post(complete_url, {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_comp.status_code, 200)

        session.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.COMPLETED)
        self.assertIsNotNone(session.completed_at)
        # Round 1: 3/3, Round 2: 3/4, Round 3: 4/4 => Total: 10/11
        self.assertEqual(session.score, 10)
        self.assertEqual(session.max_score, 11)
        expected_accuracy = round((10 / 11) * 100, 2)
        self.assertEqual(float(session.accuracy), expected_accuracy)
        self.assertEqual(session.total_time_ms, 2500 + 3200 + 4000)

        # 7. Results Page
        results_url = reverse('games:results', kwargs={'session_id': session.id})
        res_results = self.client.get(results_url)
        self.assertEqual(res_results.status_code, 200)
        self.assertTemplateUsed(res_results, 'games/game_results.html')
        self.assertContains(res_results, "10")
        self.assertContains(res_results, "11")
        self.assertContains(res_results, "Play Again")

    def test_premature_completion_rejected_when_rounds_incomplete(self):
        # 1. Start Session
        start_url = reverse('games:start_session', kwargs={'slug': 'memory-market'})
        self.client.post(start_url, {'difficulty': 1})
        session = GameSession.objects.filter(member=self.patient).latest('id')

        # 2. Complete/save only Round 1
        submit_url = reverse('games:submit_round', kwargs={'session_id': session.id})
        r1_payload = {
            'round_number': 1,
            'selected_ids': ['apples', 'milk', 'bread'],
            'response_time_ms': 2000,
            'hints_used': 0
        }
        res_r1 = self.client.post(submit_url, r1_payload, content_type='application/json')
        self.assertEqual(res_r1.status_code, 200)
        self.assertEqual(session.rounds.count(), 1)

        # 3. Attempt premature POST to complete-session
        complete_url = reverse('games:complete_session', kwargs={'session_id': session.id})
        res_premature = self.client.post(complete_url)

        # 4. Verify HTTP 400 Bad Request
        self.assertEqual(res_premature.status_code, 400)

        # 5. Verify session.status remains IN_PROGRESS
        session.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)

        # 6. Verify session.completed_at remains None
        self.assertIsNone(session.completed_at)

        # 7. Verify session has not been finalized
        self.assertEqual(session.score, 0)
        self.assertEqual(session.total_time_ms, 0)


class GameSecurityTests(TestCase):
    """Verifies security isolation between members and safeguards against tampering."""

    def setUp(self):
        self.client = Client()
        self.patient_a = CustomUser.objects.create_user(
            username='patient_alice',
            email='pa@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.patient_b = CustomUser.objects.create_user(
            username='patient_bob',
            email='pb@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_eve',
            email='ce@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.game = Game.objects.get(slug='memory-market')
        self.session_a = GameSession.objects.create(
            member=self.patient_a,
            game=self.game,
            status=GameSession.Status.IN_PROGRESS
        )

    def test_patient_cannot_view_another_patients_session(self):
        self.client.login(username='patient_bob', password='Password123!')
        url = reverse('games:play', kwargs={'session_id': self.session_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_patient_cannot_submit_rounds_to_another_patients_session(self):
        self.client.login(username='patient_bob', password='Password123!')
        url = reverse('games:submit_round', kwargs={'session_id': self.session_a.id})
        response = self.client.post(
            url,
            {'round_number': 1, 'selected_ids': ['apples'], 'response_time_ms': 1000},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)

    def test_caregiver_cannot_access_patient_session_endpoints(self):
        self.client.login(username='caregiver_eve', password='Password123!')
        url = reverse('games:play', kwargs={'session_id': self.session_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_cannot_submit_rounds_to_completed_session(self):
        self.session_a.status = GameSession.Status.COMPLETED
        self.session_a.save()

        self.client.login(username='patient_alice', password='Password123!')
        url = reverse('games:submit_round', kwargs={'session_id': self.session_a.id})
        response = self.client.post(
            url,
            {'round_number': 1, 'selected_ids': ['apples'], 'response_time_ms': 1000},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


class DailyLifeJourneyTests(TestCase):
    """
    Phase 6: Daily Life Journey cognitive sequencing game tests.
    Verifies engine configuration, session initialization with max_score=11,
    positional scoring, round progression, full telemetry, and access security.
    """

    def setUp(self):
        self.client = Client()
        self.patient = CustomUser.objects.create_user(
            username='dlj_patient',
            email='dlj_p@example.com',
            password='Password123!',
            role=Role.PATIENT,
        )
        self.caregiver = CustomUser.objects.create_user(
            username='dlj_caregiver',
            email='dlj_c@example.com',
            password='Password123!',
            role=Role.CAREGIVER,
        )
        self.other_patient = CustomUser.objects.create_user(
            username='dlj_other_patient',
            email='dlj_op@example.com',
            password='Password123!',
            role=Role.PATIENT,
        )
        self.game = Game.objects.get(slug='daily-life-journey')

    def test_engine_configuration_and_instructions(self):
        from apps.games.services import DailyLifeJourneyEngine, GAME_ENGINES
        self.assertIn('daily-life-journey', GAME_ENGINES)
        self.assertEqual(DailyLifeJourneyEngine.TOTAL_ROUNDS, 3)
        self.assertEqual(DailyLifeJourneyEngine.TEMPLATE_NAME, 'games/daily_life_journey.html')

        instructions = DailyLifeJourneyEngine.get_instructions()
        self.assertEqual(len(instructions), 4)
        for inst in instructions:
            self.assertIn('number', inst)
            self.assertIn('title', inst)
            self.assertIn('description', inst)

    def test_engine_get_round_data(self):
        from apps.games.services import DailyLifeJourneyEngine
        for r_num in [1, 2, 3]:
            data = DailyLifeJourneyEngine.get_round_data(r_num)
            self.assertEqual(data['round_number'], r_num)
            self.assertEqual(data['total_rounds'], 3)
            self.assertTrue(len(data['scenario_title']) > 0)
            self.assertTrue(len(data['scenario_instruction']) > 0)
            self.assertEqual(len(data['available_steps']), len(data['target_ids']))

        # Round 1: 3 steps
        self.assertEqual(len(DailyLifeJourneyEngine.get_round_data(1)['target_ids']), 3)
        # Round 2: 4 steps
        self.assertEqual(len(DailyLifeJourneyEngine.get_round_data(2)['target_ids']), 4)
        # Round 3: 4 steps
        self.assertEqual(len(DailyLifeJourneyEngine.get_round_data(3)['target_ids']), 4)

    def test_round_evaluation_positional_scoring(self):
        from apps.games.services import DailyLifeJourneyEngine

        # Perfect Round 1
        r1_eval = DailyLifeJourneyEngine.evaluate_round(
            1, ['tea_boil', 'tea_leaves', 'tea_steep'], 2500
        )
        self.assertTrue(r1_eval['is_correct'])
        self.assertEqual(r1_eval['score'], 3)
        self.assertEqual(r1_eval['max_score'], 3)
        self.assertEqual(r1_eval['mistake_count'], 0)
        self.assertEqual(len(r1_eval['correct_ids']), 3)

        # Partial Round 1 (index 1 tea_leaves is correct, 0 and 2 swapped)
        r1_partial = DailyLifeJourneyEngine.evaluate_round(
            1, ['tea_steep', 'tea_leaves', 'tea_boil'], 2500
        )
        self.assertFalse(r1_partial['is_correct'])
        self.assertEqual(r1_partial['score'], 1)
        self.assertEqual(r1_partial['mistake_count'], 2)
        self.assertEqual(r1_partial['correct_ids'], ['tea_leaves'])

    def test_session_creation_initializes_with_max_score_11(self):
        from apps.games.services import create_fresh_game_session
        session = create_fresh_game_session(
            member=self.patient,
            game_slug='daily-life-journey',
            difficulty=1,
        )
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)
        self.assertEqual(session.max_score, 11)  # 3 + 4 + 4 = 11
        self.assertEqual(session.score, 0)
        self.assertIsNone(session.completed_at)

    def test_catalog_shows_daily_life_journey_ready_to_play(self):
        self.client.login(username='dlj_patient', password='Password123!')
        response = self.client.get(reverse('games:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Daily Life Journey')
        self.assertContains(response, 'Ready to Play')
        active_slugs = response.context['active_game_slugs']
        self.assertIn('daily-life-journey', active_slugs)
        self.assertIn('memory-market', active_slugs)

    def test_detail_view_renders_instructions(self):
        self.client.login(username='dlj_patient', password='Password123!')
        response = self.client.get(reverse('games:detail', kwargs={'slug': 'daily-life-journey'}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_playable'])
        self.assertContains(response, 'Daily Life Journey')
        self.assertContains(response, 'Read the Daily Story')
        self.assertContains(response, 'Start Activity')

    def test_complete_gameplay_flow_and_telemetry(self):
        self.client.login(username='dlj_patient', password='Password123!')

        # 1. Start Session
        start_res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'daily-life-journey'}),
            {'difficulty': 1}
        )
        self.assertEqual(start_res.status_code, 302)
        session = GameSession.objects.filter(member=self.patient, game=self.game).latest('id')
        self.assertEqual(session.max_score, 11)
        self.assertEqual(session.score, 0)

        # 2. Access Gameplay View
        play_res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(play_res.status_code, 200)
        self.assertTemplateUsed(play_res, 'games/daily_life_journey.html')
        self.assertContains(play_res, 'Making a Morning Cup of Tea')

        # 3. Submit Round 1 (All correct: 3 points)
        submit_url = reverse('games:submit_round', kwargs={'session_id': session.id})
        r1_payload = {
            'round_number': 1,
            'selected_ids': ['tea_boil', 'tea_leaves', 'tea_steep'],
            'response_time_ms': 3000,
            'hints_used': 0,
        }
        res_r1 = self.client.post(submit_url, r1_payload, content_type='application/json')
        self.assertEqual(res_r1.status_code, 200)
        data_r1 = res_r1.json()
        self.assertTrue(data_r1['success'])
        self.assertTrue(data_r1['has_next_round'])
        self.assertEqual(data_r1['next_round_number'], 2)
        self.assertEqual(data_r1['evaluation']['score'], 3)

        # 4. Attempt premature complete - must fail with 400
        complete_url = reverse('games:complete_session', kwargs={'session_id': session.id})
        premature_res = self.client.post(complete_url)
        self.assertEqual(premature_res.status_code, 400)

        # 5. Submit Round 2 (Partial correct: 2 out of 4)
        # Expected: ['walk_weather', 'walk_shoes', 'walk_keys', 'walk_door']
        # Submitted: ['walk_weather', 'walk_keys', 'walk_shoes', 'walk_door'] -> walk_weather (0) and walk_door (3) match!
        r2_payload = {
            'round_number': 2,
            'selected_ids': ['walk_weather', 'walk_keys', 'walk_shoes', 'walk_door'],
            'response_time_ms': 4000,
            'hints_used': 0,
        }
        res_r2 = self.client.post(submit_url, r2_payload, content_type='application/json')
        self.assertEqual(res_r2.status_code, 200)
        data_r2 = res_r2.json()
        self.assertTrue(data_r2['success'])
        self.assertTrue(data_r2['has_next_round'])
        self.assertEqual(data_r2['next_round_number'], 3)
        self.assertEqual(data_r2['evaluation']['score'], 2)

        # 6. Submit Round 3 (All correct: 4 points)
        r3_payload = {
            'round_number': 3,
            'selected_ids': ['wash_water', 'wash_soap', 'wash_rinse', 'wash_dry'],
            'response_time_ms': 3500,
            'hints_used': 0,
        }
        res_r3 = self.client.post(submit_url, r3_payload, content_type='application/json')
        self.assertEqual(res_r3.status_code, 200)
        data_r3 = res_r3.json()
        self.assertTrue(data_r3['success'])
        self.assertFalse(data_r3['has_next_round'])
        self.assertIsNone(data_r3['next_round_number'])
        self.assertEqual(data_r3['evaluation']['score'], 4)

        # 7. Finalize Session
        complete_res = self.client.post(complete_url, content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(complete_res.status_code, 200)
        self.assertTrue(complete_res.json()['success'])

        # 8. Verify GameSession Database Telemetry
        session.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.COMPLETED)
        self.assertIsNotNone(session.completed_at)
        # Score = 3 (R1) + 2 (R2) + 4 (R3) = 9
        self.assertEqual(session.score, 9)
        self.assertEqual(session.max_score, 11)
        # Accuracy = (9 / 11) * 100 = 81.82%
        from decimal import Decimal
        self.assertEqual(session.accuracy, Decimal('81.82'))
        self.assertEqual(session.total_time_ms, 3000 + 4000 + 3500)
        self.assertEqual(session.rounds.count(), 3)

        # 9. Verify Results Page
        results_url = reverse('games:results', kwargs={'session_id': session.id})
        res_page = self.client.get(results_url)
        self.assertEqual(res_page.status_code, 200)
        self.assertContains(res_page, 'Activity Completed')
        self.assertContains(res_page, 'Steps in Natural Order')
        self.assertContains(res_page, '9')
        self.assertContains(res_page, '11')

    def test_security_caregiver_blocked_and_isolation(self):
        # Caregiver cannot start session
        self.client.login(username='dlj_caregiver', password='Password123!')
        start_res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'daily-life-journey'}),
            {'difficulty': 1}
        )
        self.assertEqual(start_res.status_code, 403)

        # Caregiver cannot view game list
        list_res = self.client.get(reverse('games:list'))
        self.assertEqual(list_res.status_code, 403)

        # Create session as patient
        from apps.games.services import create_fresh_game_session
        session = create_fresh_game_session(member=self.patient, game_slug='daily-life-journey')

        # Other patient cannot access session
        self.client.login(username='dlj_other_patient', password='Password123!')
        play_res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(play_res.status_code, 404)


import json
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.games.services import FamiliarFacesEngine, create_fresh_game_session
from apps.memories.models import FamiliarPerson


class FamiliarFacesEngineTests(TestCase):
    """Unit tests for FamiliarFacesEngine configuration, selection, and evaluation."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='faces_player',
            email='faces@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.game = Game.objects.get(slug='familiar-faces')

        # Create 5 active familiar people with valid photo bytes
        self.people = []
        for i in range(1, 6):
            photo = SimpleUploadedFile(
                name=f'person_{i}.jpg',
                content=b'\xff\xd8\xff\xe0' + b'0' * 500,
                content_type='image/jpeg'
            )
            person = FamiliarPerson.objects.create(
                member=self.member,
                name=f'Relative {i}',
                relationship=f'Relation {i}',
                photo=photo,
                is_active=True
            )
            self.people.append(person)

        self.session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=1,
            status=GameSession.Status.IN_PROGRESS,
            score=0,
            max_score=3,
            accuracy=Decimal('0.00'),
            total_time_ms=0,
        )

    def test_insufficient_people_raises_value_error(self):
        # Deactivate 2 people so only 3 remain
        self.people[0].is_active = False
        self.people[0].save()
        self.people[1].is_active = False
        self.people[1].save()

        with self.assertRaises(ValueError):
            FamiliarFacesEngine.get_session_plan(self.session)

    def test_session_plan_three_distinct_targets(self):
        plan = FamiliarFacesEngine.get_session_plan(self.session)
        self.assertEqual(len(plan), 3)

        targets = [plan[r]['target'] for r in [1, 2, 3]]
        target_ids = [t.id for t in targets]
        # All 3 targets must be unique
        self.assertEqual(len(set(target_ids)), 3)

        # Choice counts
        self.assertEqual(len(plan[1]['choices']), 3)  # 1 target + 2 distractors
        self.assertEqual(len(plan[2]['choices']), 4)  # 1 target + 3 distractors
        self.assertEqual(len(plan[3]['choices']), 4)  # 1 target + 3 distractors

        # Target must be present in choices for each round
        for r in [1, 2, 3]:
            choice_ids = [p.id for p in plan[r]['choices']]
            self.assertIn(plan[r]['target'].id, choice_ids)

    def test_session_plan_is_deterministic(self):
        plan1 = FamiliarFacesEngine.get_session_plan(self.session)
        plan2 = FamiliarFacesEngine.get_session_plan(self.session)

        for r in [1, 2, 3]:
            self.assertEqual(plan1[r]['target'].id, plan2[r]['target'].id)
            choices1 = [p.id for p in plan1[r]['choices']]
            choices2 = [p.id for p in plan2[r]['choices']]
            self.assertEqual(choices1, choices2)

    def test_round_data_structure(self):
        data = FamiliarFacesEngine.get_round_data(1, session=self.session)
        self.assertEqual(data['round_number'], 1)
        self.assertEqual(data['total_rounds'], 3)
        self.assertIn('target_photo_url', data)
        self.assertIn('target_name', data)
        self.assertIn('target_relationship', data)
        self.assertEqual(len(data['choices']), 3)
        self.assertEqual(len(data['target_ids']), 1)

    def test_evaluation_correct_choice(self):
        round_data = FamiliarFacesEngine.get_round_data(1, session=self.session)
        target_id = round_data['target_ids'][0]

        eval_res = FamiliarFacesEngine.evaluate_round(
            1,
            actual_selected_ids=[target_id],
            response_time_ms=2500,
            session=self.session
        )
        self.assertTrue(eval_res['is_correct'])
        self.assertEqual(eval_res['score'], 1)
        self.assertEqual(eval_res['mistake_count'], 0)
        self.assertEqual(eval_res['correct_ids'], [target_id])
        self.assertEqual(eval_res['feedback_tone'], 'success')
        self.assertIn('Wonderful', eval_res['feedback_message'])

    def test_evaluation_incorrect_choice(self):
        round_data = FamiliarFacesEngine.get_round_data(1, session=self.session)
        target_id = round_data['target_ids'][0]
        # Pick a choice that is not the target
        distractor_id = [c['id'] for c in round_data['choices'] if c['id'] != target_id][0]

        eval_res = FamiliarFacesEngine.evaluate_round(
            1,
            actual_selected_ids=[distractor_id],
            response_time_ms=3100,
            session=self.session
        )
        self.assertFalse(eval_res['is_correct'])
        self.assertEqual(eval_res['score'], 0)
        self.assertEqual(eval_res['mistake_count'], 1)
        self.assertEqual(eval_res['distractor_ids'], [distractor_id])
        self.assertEqual(eval_res['missed_ids'], [target_id])
        self.assertEqual(eval_res['feedback_tone'], 'encouraging')

    def test_create_fresh_game_session_initializes_max_score_three(self):
        new_session = create_fresh_game_session(self.member, 'familiar-faces', difficulty=1)
        self.assertEqual(new_session.max_score, 3)
        self.assertEqual(new_session.score, 0)
        self.assertEqual(new_session.status, GameSession.Status.IN_PROGRESS)

    def test_create_fresh_game_session_fails_if_insufficient_people(self):
        # Deactivate people so only 2 remain
        for p in self.people[:3]:
            p.is_active = False
            p.save()

        with self.assertRaises(ValidationError):
            create_fresh_game_session(self.member, 'familiar-faces', difficulty=1)


class FamiliarFacesGameplayIntegrationTests(TestCase):
    """End-to-end multi-round gameplay session flow for Familiar Faces."""

    def setUp(self):
        self.client = Client()
        self.member = CustomUser.objects.create_user(
            username='player_ff',
            email='pff@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.game = Game.objects.get(slug='familiar-faces')

        # Create 4 active people with photos
        self.people = []
        for i in range(1, 5):
            photo = SimpleUploadedFile(
                name=f'p_{i}.jpg',
                content=b'\xff\xd8\xff\xe0' + b'0' * 500,
                content_type='image/jpeg'
            )
            p = FamiliarPerson.objects.create(
                member=self.member,
                name=f'Family Member {i}',
                relationship=f'Kin {i}',
                photo=photo,
                is_active=True
            )
            self.people.append(p)

    def test_game_detail_shows_ready_when_enough_people(self):
        self.client.login(username='player_ff', password='Password123!')
        res = self.client.get(reverse('games:detail', kwargs={'slug': 'familiar-faces'}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Start Activity')

    def test_game_detail_shows_photos_needed_when_insufficient(self):
        # Deactivate all people
        for p in self.people:
            p.is_active = False
            p.save()

        self.client.login(username='player_ff', password='Password123!')
        res = self.client.get(reverse('games:detail', kwargs={'slug': 'familiar-faces'}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Photos Needed')

    def test_complete_three_round_gameplay_lifecycle(self):
        self.client.login(username='player_ff', password='Password123!')

        # 1. Start Session
        start_res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'familiar-faces'}),
            data={'difficulty': 1}
        )
        self.assertEqual(start_res.status_code, 302)
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)
        self.assertEqual(session.max_score, 3)

        # 2. Play Round 1 (Submit correct target)
        round1_data = FamiliarFacesEngine.get_round_data(1, session=session)
        target1 = round1_data['target_ids'][0]
        sub1 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({
                'round_number': 1,
                'selected_ids': [target1],
                'response_time_ms': 2000,
                'hints_used': 0
            }),
            content_type='application/json'
        )
        self.assertEqual(sub1.status_code, 200)
        data1 = sub1.json()
        self.assertTrue(data1['success'])
        self.assertTrue(data1['evaluation']['is_correct'])
        self.assertTrue(data1['has_next_round'])
        self.assertEqual(data1['next_round_number'], 2)

        # 3. Play Round 2 (Submit correct target)
        round2_data = FamiliarFacesEngine.get_round_data(2, session=session)
        target2 = round2_data['target_ids'][0]
        sub2 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({
                'round_number': 2,
                'selected_ids': [target2],
                'response_time_ms': 2400,
                'hints_used': 0
            }),
            content_type='application/json'
        )
        self.assertEqual(sub2.status_code, 200)
        data2 = sub2.json()
        self.assertTrue(data2['has_next_round'])
        self.assertEqual(data2['next_round_number'], 3)

        # 4. Play Round 3 (Submit incorrect target)
        round3_data = FamiliarFacesEngine.get_round_data(3, session=session)
        target3 = round3_data['target_ids'][0]
        distractor3 = [c['id'] for c in round3_data['choices'] if c['id'] != target3][0]
        sub3 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({
                'round_number': 3,
                'selected_ids': [distractor3],
                'response_time_ms': 3000,
                'hints_used': 0
            }),
            content_type='application/json'
        )
        self.assertEqual(sub3.status_code, 200)
        data3 = sub3.json()
        self.assertFalse(data3['evaluation']['is_correct'])
        self.assertFalse(data3['has_next_round'])

        # 5. Complete Session
        comp_res = self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )
        self.assertEqual(comp_res.status_code, 200)

        # 6. Verify Session Finalization
        session.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.COMPLETED)
        self.assertEqual(session.score, 2)  # 2 correct rounds out of 3
        self.assertEqual(session.max_score, 3)
        self.assertEqual(session.accuracy, Decimal('66.67'))
        self.assertEqual(session.rounds.count(), 3)
        self.assertEqual(session.total_time_ms, 7400)

        # 7. Tamper Rejection: cannot submit rounds to finalized session
        tamper_res = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [target1], 'response_time_ms': 1000}),
            content_type='application/json'
        )
        self.assertEqual(tamper_res.status_code, 400)

    def test_stimulus_data_stores_only_stable_ids_and_no_personal_data(self):
        """
        Privacy requirement verification:
        GameRound.stimulus_data stores only target_id and choice_ids.
        It must NOT store target_photo_url, target_name, target_relationship, or full choices.
        expected_response and actual_response still store the correct IDs.
        """
        self.client.login(username='player_ff', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'familiar-faces'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        round1_data = FamiliarFacesEngine.get_round_data(1, session=session)
        target1 = round1_data['target_ids'][0]

        sub_res = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({
                'round_number': 1,
                'selected_ids': [target1],
                'response_time_ms': 1800,
                'hints_used': 0
            }),
            content_type='application/json'
        )
        self.assertEqual(sub_res.status_code, 200)

        round_obj = session.rounds.get(round_number=1)
        stimulus = round_obj.stimulus_data

        # 1. stimulus_data contains target_id and choice_ids
        self.assertIn('target_id', stimulus)
        self.assertEqual(stimulus['target_id'], target1)
        self.assertIn('choice_ids', stimulus)
        self.assertEqual(len(stimulus['choice_ids']), 3)

        # 2. stimulus_data must NOT contain sensitive personal information
        self.assertNotIn('target_photo_url', stimulus)
        self.assertNotIn('target_name', stimulus)
        self.assertNotIn('target_relationship', stimulus)
        self.assertNotIn('choices', stimulus)

        # 3. expected_response still contains correct target ID
        self.assertEqual(round_obj.expected_response, {'target_ids': [target1]})

        # 4. actual_response still records selected ID and evaluation
        self.assertEqual(round_obj.actual_response['selected_ids'], [target1])
        self.assertEqual(round_obj.actual_response['correct_ids'], [target1])
        self.assertTrue(round_obj.is_correct)


# ==========================================================================
# Phase 9: Focus Finder Tests
# ==========================================================================

import xml.etree.ElementTree as ET
from decimal import Decimal
from apps.games.services import FocusFinderEngine, FOCUS_FINDER_CATALOG
from apps.accounts.models import CaregiverMemberRelationship
from apps.accounts.services import get_caregiver_dashboard_data


class FocusFinderEngineTests(TestCase):
    """Unit tests for FocusFinderEngine logic, item catalog, and deterministic planning."""

    def test_catalog_integrity(self):
        """Validates that all 24 catalog items are complete, well-formed SVG, and free of emoji."""
        self.assertGreaterEqual(len(FOCUS_FINDER_CATALOG), 20)
        approved_categories = {'Flowers', 'Foliage & Botanicals', 'Kitchen & Table', 'Keepsakes'}

        for item_id, item in FOCUS_FINDER_CATALOG.items():
            self.assertEqual(item['id'], item_id)
            self.assertTrue(item['name'])
            self.assertIn(item['category'], approved_categories)
            self.assertTrue(item['svg_icon'])

            # Verify XML parsing of SVG
            try:
                root = ET.fromstring(item['svg_icon'])
                self.assertIn('svg', root.tag)
            except Exception as e:
                self.fail(f"Item '{item_id}' has invalid SVG XML: {e}")

    def test_instructions_present_and_structured(self):
        """Verifies elder-friendly 4-step instructions."""
        instructions = FocusFinderEngine.get_instructions()
        self.assertEqual(len(instructions), 4)
        for i, step in enumerate(instructions, 1):
            self.assertEqual(step['number'], i)
            self.assertTrue(step['title'])
            self.assertTrue(step['description'])

    def test_difficulty_configurations(self):
        """Validates all 5 difficulty levels for grid dimensions, item counts, and single targets."""
        expected_configs = {
            1: (2, 3, 6),
            2: (3, 3, 9),
            3: (3, 4, 12),
            4: (4, 4, 16),
            5: (4, 5, 20),
        }

        for diff, (rows, cols, total_items) in expected_configs.items():
            plan = FocusFinderEngine.get_session_plan(session=None, difficulty=diff)
            self.assertEqual(len(plan), 3)

            targets_in_session = [plan[r]['target_ids'][0] for r in range(1, 4)]
            self.assertEqual(len(set(targets_in_session)), 3, f"Targets must be distinct across rounds for diff {diff}")

            for r in range(1, 4):
                round_data = plan[r]
                self.assertEqual(round_data['grid_size'], {'rows': rows, 'cols': cols})
                self.assertEqual(len(round_data['grid_items']), total_items)
                self.assertEqual(len(round_data['grid_item_ids']), total_items)
                self.assertEqual(len(round_data['distractor_ids']), total_items - 1)

                target_id = round_data['target_ids'][0]
                self.assertIn(target_id, round_data['grid_item_ids'])
                self.assertEqual(round_data['grid_item_ids'].count(target_id), 1)
                self.assertNotIn(target_id, round_data['distractor_ids'])

    def test_session_plan_determinism(self):
        """Confirms that the same session ID and difficulty produce an identical plan on repeated calls."""
        class DummySession:
            id = 42
            difficulty = 3

        session = DummySession()
        plan1 = FocusFinderEngine.get_session_plan(session=session)
        plan2 = FocusFinderEngine.get_session_plan(session=session)

        for r in range(1, 4):
            self.assertEqual(plan1[r]['target_ids'], plan2[r]['target_ids'])
            self.assertEqual(plan1[r]['grid_item_ids'], plan2[r]['grid_item_ids'])
            self.assertEqual(plan1[r]['distractor_ids'], plan2[r]['distractor_ids'])

    def test_get_round_data_validation(self):
        """Verifies get_round_data structure and boundary handling."""
        round1 = FocusFinderEngine.get_round_data(1)
        self.assertEqual(round1['round_number'], 1)
        self.assertEqual(round1['total_rounds'], 3)
        self.assertIn('target_item', round1)
        self.assertIn('target_ids', round1)
        self.assertIn('grid_items', round1)
        self.assertIn('grid_size', round1)

        with self.assertRaises(ValueError):
            FocusFinderEngine.get_round_data(0)

        with self.assertRaises(ValueError):
            FocusFinderEngine.get_round_data(4)

    def test_evaluate_round_correct_selection(self):
        """Verifies scoring and feedback when matching target is selected."""
        round_data = FocusFinderEngine.get_round_data(1)
        target_id = round_data['target_ids'][0]

        eval_res = FocusFinderEngine.evaluate_round(1, [target_id], response_time_ms=2200)
        self.assertTrue(eval_res['is_correct'])
        self.assertEqual(eval_res['score'], 1)
        self.assertEqual(eval_res['max_score'], 1)
        self.assertEqual(eval_res['mistake_count'], 0)
        self.assertEqual(eval_res['correct_ids'], [target_id])
        self.assertEqual(eval_res['distractor_ids'], [])
        self.assertEqual(eval_res['feedback_tone'], 'success')
        self.assertIn("Wonderful!", eval_res['feedback_message'])

    def test_evaluate_round_incorrect_selection(self):
        """Verifies scoring and gentle feedback when a distractor is selected."""
        round_data = FocusFinderEngine.get_round_data(1)
        target_id = round_data['target_ids'][0]
        distractor_id = [item['id'] for item in round_data['grid_items'] if item['id'] != target_id][0]

        eval_res = FocusFinderEngine.evaluate_round(1, [distractor_id], response_time_ms=3500)
        self.assertFalse(eval_res['is_correct'])
        self.assertEqual(eval_res['score'], 0)
        self.assertEqual(eval_res['max_score'], 1)
        self.assertEqual(eval_res['mistake_count'], 1)
        self.assertEqual(eval_res['correct_ids'], [])
        self.assertEqual(eval_res['distractor_ids'], [distractor_id])
        self.assertEqual(eval_res['missed_ids'], [target_id])
        self.assertEqual(eval_res['feedback_tone'], 'encouraging')
        self.assertIn("Good effort!", eval_res['feedback_message'])

    def test_evaluate_round_alien_or_empty_selection(self):
        """Verifies graceful handling of empty or invalid IDs."""
        eval_empty = FocusFinderEngine.evaluate_round(1, [], response_time_ms=1000)
        self.assertFalse(eval_empty['is_correct'])
        self.assertEqual(eval_empty['score'], 0)
        self.assertEqual(eval_empty['mistake_count'], 1)

        eval_alien = FocusFinderEngine.evaluate_round(1, ['alien_id_999'], response_time_ms=1000)
        self.assertFalse(eval_alien['is_correct'])
        self.assertEqual(eval_alien['score'], 0)


class FocusFinderSessionFlowTests(TestCase):
    """Integration tests for full Focus Finder session lifecycle, views, and caregiver reporting."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='player_focus',
            email='pf@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Clara',
            last_name='Oswald'
        )
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_focus',
            email='cgf@example.com',
            password='Password123!',
            role=Role.CAREGIVER,
            first_name='Martha',
            last_name='Jones'
        )
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.member,
            is_active=True
        )
        self.game = Game.objects.get(slug='focus-finder')

    def test_patient_can_start_focus_finder_session(self):
        """A patient can initiate a Focus Finder session with a configured difficulty."""
        self.client.login(username='player_focus', password='Password123!')
        res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 3}
        )
        self.assertEqual(res.status_code, 302)

        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        self.assertEqual(session.difficulty, 3)
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)
        self.assertEqual(session.score, 0)
        self.assertEqual(session.max_score, 3)
        self.assertEqual(session.accuracy, Decimal('0.00'))

    def test_caregiver_cannot_start_patient_session(self):
        """A caregiver is not allowed to initiate a gameplay session directly."""
        self.client.login(username='caregiver_focus', password='Password123!')
        res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 1}
        )
        self.assertEqual(res.status_code, 403)

    def test_gameplay_view_renders_focus_finder(self):
        """Active gameplay view delivers the focus_finder.html template with target and grid."""
        self.client.login(username='player_focus', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 2}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'games/focus_finder.html')
        self.assertContains(res, 'Focus Finder')
        self.assertContains(res, 'Target to Find')
        self.assertContains(res, 'Picture Grid:')
        self.assertContains(res, 'Confirm My Selection')

    def test_full_three_round_gameplay_and_scoring(self):
        """Executes full 3-round gameplay session (2 correct, 1 incorrect) and validates completion."""
        self.client.login(username='player_focus', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = FocusFinderEngine.get_session_plan(session=session)
        target1 = plan[1]['target_ids'][0]
        target2 = plan[2]['target_ids'][0]
        # Distractor for round 3 to simulate incorrect pick
        distractor3 = plan[3]['distractor_ids'][0]

        # Round 1 (Correct)
        res1 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [target1], 'response_time_ms': 2000}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertTrue(data1['evaluation']['is_correct'])
        self.assertTrue(data1['has_next_round'])
        self.assertEqual(data1['next_round_number'], 2)

        # Round 2 (Correct)
        res2 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 2, 'selected_ids': [target2], 'response_time_ms': 2500}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2['evaluation']['is_correct'])
        self.assertTrue(data2['has_next_round'])
        self.assertEqual(data2['next_round_number'], 3)

        # Round 3 (Incorrect pick)
        res3 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 3, 'selected_ids': [distractor3], 'response_time_ms': 3000}),
            content_type='application/json'
        )
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        self.assertFalse(data3['evaluation']['is_correct'])
        self.assertFalse(data3['has_next_round'])

        # Finalize session
        comp_res = self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )
        self.assertEqual(comp_res.status_code, 200)

        # Verify database metrics
        session.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.COMPLETED)
        self.assertEqual(session.score, 2)  # 2 of 3 correct
        self.assertEqual(session.max_score, 3)
        self.assertEqual(session.accuracy, Decimal('66.67'))
        self.assertEqual(session.rounds.count(), 3)
        self.assertEqual(session.total_time_ms, 7500)

        # Check results view
        results_res = self.client.get(reverse('games:results', kwargs={'session_id': session.id}))
        self.assertEqual(results_res.status_code, 200)
        self.assertContains(results_res, 'Targets Spotted')
        self.assertContains(results_res, '✓ Target Found')

    def test_premature_completion_rejected(self):
        """Cannot finalize session before all 3 rounds are submitted."""
        self.client.login(username='player_focus', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = FocusFinderEngine.get_session_plan(session=session)
        target1 = plan[1]['target_ids'][0]

        self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [target1], 'response_time_ms': 1500}),
            content_type='application/json'
        )

        comp_res = self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )
        self.assertEqual(comp_res.status_code, 400)

    def test_duplicate_round_submission_rejected(self):
        """Submitting round 1 twice triggers a validation error."""
        self.client.login(username='player_focus', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = FocusFinderEngine.get_session_plan(session=session)
        target1 = plan[1]['target_ids'][0]

        res1 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [target1], 'response_time_ms': 1500}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)

        # Duplicate submission
        res2 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [target1], 'response_time_ms': 1500}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 400)

    def test_tamper_rejection_on_completed_session(self):
        """Cannot submit rounds to an already finalized session."""
        self.client.login(username='player_focus', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = FocusFinderEngine.get_session_plan(session=session)
        for r in range(1, 4):
            t = plan[r]['target_ids'][0]
            self.client.post(
                reverse('games:submit_round', kwargs={'session_id': session.id}),
                data=json.dumps({'round_number': r, 'selected_ids': [t], 'response_time_ms': 1000}),
                content_type='application/json'
            )
        self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )

        tamper_res = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': ['marigold'], 'response_time_ms': 1000}),
            content_type='application/json'
        )
        self.assertEqual(tamper_res.status_code, 400)

    def test_stimulus_data_stores_only_safe_ids_and_grid_size(self):
        """Privacy verification: GameRound.stimulus_data stores only target_id, distractor_ids, grid_item_ids, grid_size."""
        self.client.login(username='player_focus', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = FocusFinderEngine.get_session_plan(session=session)
        target1 = plan[1]['target_ids'][0]

        sub_res = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [target1], 'response_time_ms': 1800}),
            content_type='application/json'
        )
        self.assertEqual(sub_res.status_code, 200)

        round_obj = session.rounds.get(round_number=1)
        stimulus = round_obj.stimulus_data

        # Verify key presence and structure
        self.assertIn('target_id', stimulus)
        self.assertEqual(stimulus['target_id'], target1)
        self.assertIn('distractor_ids', stimulus)
        self.assertIn('grid_item_ids', stimulus)
        self.assertIn('grid_size', stimulus)
        self.assertEqual(stimulus['grid_size'], {'rows': 2, 'cols': 3})

        # Verify absence of personal or media data
        self.assertNotIn('user_id', stimulus)
        self.assertNotIn('username', stimulus)
        self.assertNotIn('photo_url', stimulus)
        self.assertNotIn('svg_icon', stimulus)

        # Expected and actual response telemetry
        self.assertEqual(round_obj.expected_response, {'target_ids': [target1]})
        self.assertEqual(round_obj.actual_response['selected_ids'], [target1])
        self.assertEqual(round_obj.actual_response['correct_ids'], [target1])
        self.assertTrue(round_obj.is_correct)

    def test_caregiver_dashboard_reflects_focus_finder(self):
        """Verifies that completed Focus Finder games appear seamlessly in the Caregiver Dashboard."""
        self.client.login(username='player_focus', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 4}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = FocusFinderEngine.get_session_plan(session=session)
        for r in range(1, 4):
            t = plan[r]['target_ids'][0]
            self.client.post(
                reverse('games:submit_round', kwargs={'session_id': session.id}),
                data=json.dumps({'round_number': r, 'selected_ids': [t], 'response_time_ms': 2100}),
                content_type='application/json'
            )
        self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )

        dashboard_data = get_caregiver_dashboard_data(self.caregiver, member_id=self.member.id)
        ff_metrics = [g for g in dashboard_data['games_performance'] if g['slug'] == 'focus-finder'][0]

        self.assertTrue(ff_metrics['is_active'])
        self.assertEqual(ff_metrics['domain'], 'Visual Attention')
        self.assertEqual(ff_metrics['completed_count'], 1)
        self.assertEqual(ff_metrics['current_difficulty'], 4)
        self.assertEqual(ff_metrics['avg_accuracy'], 100.0)
        self.assertEqual(ff_metrics['avg_response_time_ms'], 2100)
