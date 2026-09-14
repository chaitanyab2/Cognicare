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


# ==========================================================================
# Phase 10: Word Connections Tests
# ==========================================================================

from apps.games.services import WordConnectionsEngine, WORD_CONNECTIONS_CATALOG, GAME_ENGINES


class WordConnectionsEngineTests(TestCase):
    """Unit tests for WordConnectionsEngine logic, catalog validity, and deterministic planning."""

    def test_engine_registered(self):
        """Confirms 'word-connections' is registered in GAME_ENGINES."""
        self.assertIn('word-connections', GAME_ENGINES)
        self.assertIs(GAME_ENGINES['word-connections'], WordConnectionsEngine)

    def test_catalog_completeness_and_validity(self):
        """Verifies at least 20 scenarios, complete metadata, valid distractor counts, and unique IDs."""
        self.assertGreaterEqual(len(WORD_CONNECTIONS_CATALOG), 20)
        approved_themes = {
            'Food & Kitchen', 'Crafts & Trades', 'Garden & Nature',
            'Daily Routines', 'Nature & Seasons', 'Home & Hearth',
            'Community & Culture'
        }

        for s_id, scenario in WORD_CONNECTIONS_CATALOG.items():
            self.assertEqual(scenario['scenario_id'], s_id)
            self.assertIn(scenario['theme'], approved_themes)
            self.assertTrue(scenario['prompt'])
            self.assertTrue(scenario['concept'])
            self.assertTrue(scenario['contextual_clue'])
            self.assertTrue(scenario['target_word_id'])
            self.assertTrue(scenario['target_word'])
            self.assertTrue(scenario['explanation'])

            t_id = scenario['target_word_id']
            t_word = scenario['target_word']

            for diff in range(1, 6):
                distractors = scenario['distractors'].get(diff, [])
                expected_distractors = 3 if diff in (1, 2) else (4 if diff in (3, 4) else 5)
                self.assertEqual(
                    len(distractors),
                    expected_distractors,
                    f"Scenario {s_id} Level {diff} must have {expected_distractors} distractors"
                )

                d_ids = [d[0] for d in distractors]
                d_words = [d[1] for d in distractors]

                self.assertNotIn(t_id, d_ids, f"Target ID {t_id} cannot be in distractors for {s_id} L{diff}")
                self.assertNotIn(t_word, d_words, f"Target word {t_word} cannot be in distractors for {s_id} L{diff}")
                self.assertEqual(len(d_ids), len(set(d_ids)), f"Duplicate distractor IDs in {s_id} L{diff}")

    def test_instructions(self):
        """Verifies elder-friendly 4-step instructions."""
        instructions = WordConnectionsEngine.get_instructions()
        self.assertEqual(len(instructions), 4)
        for i, step in enumerate(instructions, 1):
            self.assertEqual(step['number'], i)
            self.assertTrue(step['title'])
            self.assertTrue(step['description'])

    def test_difficulty_choice_counts(self):
        """Verifies choice counts across all 5 difficulty tiers (Level 1: 4, Level 2: 4, Level 3: 5, Level 4: 5, Level 5: 6)."""
        expected_counts = {1: 4, 2: 4, 3: 5, 4: 5, 5: 6}
        for diff, count in expected_counts.items():
            plan = WordConnectionsEngine.get_session_plan(session=None, difficulty=diff)
            self.assertEqual(len(plan), 3)
            for r in range(1, 4):
                round_plan = plan[r]
                self.assertEqual(len(round_plan['choices']), count)
                self.assertEqual(len(round_plan['choice_ids']), count)
                self.assertEqual(len(round_plan['distractor_ids']), count - 1)
                t_id = round_plan['target_word_id']
                self.assertIn(t_id, round_plan['choice_ids'])
                self.assertEqual(round_plan['choice_ids'].count(t_id), 1)
                self.assertNotIn(t_id, round_plan['distractor_ids'])

    def test_session_plan_determinism_and_distinct_scenarios(self):
        """Confirms identical session and difficulty produce an identical plan and distinct scenarios."""
        class MockSession:
            id = 77
            difficulty = 3

        session = MockSession()
        plan1 = WordConnectionsEngine.get_session_plan(session=session)
        plan2 = WordConnectionsEngine.get_session_plan(session=session)

        # Scenarios across rounds 1, 2, 3 must be distinct
        scenarios = [plan1[r]['scenario_id'] for r in range(1, 4)]
        self.assertEqual(len(set(scenarios)), 3)

        for r in range(1, 4):
            self.assertEqual(plan1[r]['scenario_id'], plan2[r]['scenario_id'])
            self.assertEqual(plan1[r]['target_word_id'], plan2[r]['target_word_id'])
            self.assertEqual(plan1[r]['choice_ids'], plan2[r]['choice_ids'])

    def test_evaluate_round_correct(self):
        """Selecting target word yields is_correct=True, score=1, mistake_count=0, success tone."""
        round_data = WordConnectionsEngine.get_round_data(1)
        target_id = round_data['target_word_id']

        eval_res = WordConnectionsEngine.evaluate_round(1, [target_id], response_time_ms=2100)
        self.assertTrue(eval_res['is_correct'])
        self.assertEqual(eval_res['score'], 1)
        self.assertEqual(eval_res['max_score'], 1)
        self.assertEqual(eval_res['mistake_count'], 0)
        self.assertEqual(eval_res['correct_ids'], [target_id])
        self.assertEqual(eval_res['distractor_ids'], [])
        self.assertEqual(eval_res['feedback_tone'], 'success')
        self.assertIn("Wonderful!", eval_res['feedback_message'])

    def test_evaluate_round_incorrect(self):
        """Selecting a distractor yields is_correct=False, score=0, mistake_count=1, encouraging tone."""
        round_data = WordConnectionsEngine.get_round_data(1)
        distractor_id = round_data['distractor_ids'][0]

        eval_res = WordConnectionsEngine.evaluate_round(1, [distractor_id], response_time_ms=2800)
        self.assertFalse(eval_res['is_correct'])
        self.assertEqual(eval_res['score'], 0)
        self.assertEqual(eval_res['max_score'], 1)
        self.assertEqual(eval_res['mistake_count'], 1)
        self.assertEqual(eval_res['correct_ids'], [])
        self.assertEqual(eval_res['distractor_ids'], [distractor_id])
        self.assertEqual(eval_res['missed_ids'], [round_data['target_word_id']])
        self.assertEqual(eval_res['feedback_tone'], 'encouraging')
        self.assertIn("Good effort!", eval_res['feedback_message'])

    def test_evaluate_round_empty_alien_or_multiple(self):
        """Empty, alien, or multiple IDs are safely evaluated as incorrect."""
        # Empty
        eval_empty = WordConnectionsEngine.evaluate_round(1, [], response_time_ms=1000)
        self.assertFalse(eval_empty['is_correct'])
        self.assertEqual(eval_empty['score'], 0)
        self.assertEqual(eval_empty['mistake_count'], 1)

        # Alien
        eval_alien = WordConnectionsEngine.evaluate_round(1, ['alien_word_id_999'], response_time_ms=1000)
        self.assertFalse(eval_alien['is_correct'])
        self.assertEqual(eval_alien['score'], 0)

        # Multiple
        round_data = WordConnectionsEngine.get_round_data(1)
        t_id = round_data['target_word_id']
        d_id = round_data['distractor_ids'][0]
        eval_multi = WordConnectionsEngine.evaluate_round(1, [t_id, d_id], response_time_ms=1000)
        self.assertFalse(eval_multi['is_correct'])
        self.assertEqual(eval_multi['score'], 0)


class WordConnectionsSessionFlowTests(TestCase):
    """Integration tests for Word Connections session lifecycle, security, telemetry, and caregiver analytics."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='player_words',
            email='pw@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Arthur',
            last_name='Dent'
        )
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_words',
            email='cw@example.com',
            password='Password123!',
            role=Role.CAREGIVER,
            first_name='Trillian',
            last_name='Astra'
        )
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.member,
            is_active=True
        )
        self.game = Game.objects.get(slug='word-connections')

    def test_patient_can_start_word_connections_session(self):
        """Patient can initiate Word Connections session with chosen difficulty."""
        self.client.login(username='player_words', password='Password123!')
        res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 4}
        )
        self.assertEqual(res.status_code, 302)

        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        self.assertEqual(session.difficulty, 4)
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)
        self.assertEqual(session.score, 0)
        self.assertEqual(session.max_score, 3)
        self.assertEqual(session.accuracy, Decimal('0.00'))

    def test_caregiver_blocked_from_playing(self):
        """Caregiver cannot directly start or play Word Connections."""
        self.client.login(username='caregiver_words', password='Password123!')
        res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 1}
        )
        self.assertEqual(res.status_code, 403)

    def test_gameplay_view_renders_word_connections(self):
        """Active gameplay delivers word_connections.html with concept card and choices."""
        self.client.login(username='player_words', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 2}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'games/word_connections.html')
        self.assertContains(res, 'Word Connections')
        self.assertContains(res, 'Central Concept')
        self.assertContains(res, 'Select the Matching Word:')
        self.assertContains(res, 'Confirm My Selection')

    def test_full_three_round_gameplay_and_scoring(self):
        """Plays 3 rounds (2 correct, 1 incorrect), finalizes session, verifies score=2/3 and accuracy=66.67%."""
        self.client.login(username='player_words', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = WordConnectionsEngine.get_session_plan(session=session)
        t1 = plan[1]['target_word_id']
        t2 = plan[2]['target_word_id']
        d3 = plan[3]['distractor_ids'][0]

        # Round 1 (Correct)
        res1 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 2000}),
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
            data=json.dumps({'round_number': 2, 'selected_ids': [t2], 'response_time_ms': 2200}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2['evaluation']['is_correct'])
        self.assertTrue(data2['has_next_round'])
        self.assertEqual(data2['next_round_number'], 3)

        # Round 3 (Incorrect)
        res3 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 3, 'selected_ids': [d3], 'response_time_ms': 2600}),
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
        self.assertEqual(session.score, 2)
        self.assertEqual(session.max_score, 3)
        self.assertEqual(session.accuracy, Decimal('66.67'))
        self.assertEqual(session.rounds.count(), 3)
        self.assertEqual(session.total_time_ms, 6800)

        # Check results view
        results_res = self.client.get(reverse('games:results', kwargs={'session_id': session.id}))
        self.assertEqual(results_res.status_code, 200)
        self.assertContains(results_res, 'Connections Made')
        self.assertContains(results_res, '✓ Connection Identified')

    def test_duplicate_submission_blocked(self):
        """Submitting round 1 twice triggers a validation error (HTTP 400)."""
        self.client.login(username='player_words', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = WordConnectionsEngine.get_session_plan(session=session)
        t1 = plan[1]['target_word_id']

        res1 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1500}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)

        # Duplicate submission
        res2 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1500}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 400)

    def test_tamper_rejection_on_completed_session(self):
        """Cannot submit rounds to an already finalized session."""
        self.client.login(username='player_words', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = WordConnectionsEngine.get_session_plan(session=session)
        for r in range(1, 4):
            t = plan[r]['target_word_id']
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
            data=json.dumps({'round_number': 1, 'selected_ids': ['yeast'], 'response_time_ms': 1000}),
            content_type='application/json'
        )
        self.assertEqual(tamper_res.status_code, 400)

    def test_premature_completion_rejected(self):
        """Cannot finalize session before all 3 rounds are submitted."""
        self.client.login(username='player_words', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = WordConnectionsEngine.get_session_plan(session=session)
        t1 = plan[1]['target_word_id']

        self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1500}),
            content_type='application/json'
        )

        comp_res = self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )
        self.assertEqual(comp_res.status_code, 400)

    def test_privacy_telemetry_stimulus_data(self):
        """Confirms stimulus_data contains only scenario_id, target_word_id, distractor_word_ids, choice_word_ids."""
        self.client.login(username='player_words', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 3}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = WordConnectionsEngine.get_session_plan(session=session)
        t1 = plan[1]['target_word_id']

        sub_res = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1900}),
            content_type='application/json'
        )
        self.assertEqual(sub_res.status_code, 200)

        round_obj = session.rounds.get(round_number=1)
        stimulus = round_obj.stimulus_data

        # Verify key presence and structure
        self.assertIn('scenario_id', stimulus)
        self.assertIn('target_word_id', stimulus)
        self.assertEqual(stimulus['target_word_id'], t1)
        self.assertIn('distractor_word_ids', stimulus)
        self.assertIn('choice_word_ids', stimulus)
        self.assertEqual(len(stimulus['choice_word_ids']), 5)  # Diff 3 has 5 choices

        # Verify absence of personal or HTML presentation data
        self.assertNotIn('user_id', stimulus)
        self.assertNotIn('username', stimulus)
        self.assertNotIn('explanation', stimulus)
        self.assertNotIn('contextual_clue', stimulus)
        self.assertNotIn('html', stimulus)

        # Expected and actual response telemetry
        self.assertEqual(round_obj.expected_response, {'target_ids': [t1]})
        self.assertEqual(round_obj.actual_response['selected_ids'], [t1])
        self.assertEqual(round_obj.actual_response['correct_ids'], [t1])
        self.assertTrue(round_obj.is_correct)

    def test_caregiver_dashboard_reflects_word_connections(self):
        """Verifies that completed Word Connections games appear under 'Semantic Memory' in Caregiver Dashboard."""
        self.client.login(username='player_words', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 5}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = WordConnectionsEngine.get_session_plan(session=session)
        for r in range(1, 4):
            t = plan[r]['target_word_id']
            self.client.post(
                reverse('games:submit_round', kwargs={'session_id': session.id}),
                data=json.dumps({'round_number': r, 'selected_ids': [t], 'response_time_ms': 2400}),
                content_type='application/json'
            )
        self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )

        dashboard_data = get_caregiver_dashboard_data(self.caregiver, member_id=self.member.id)
        wc_metrics = [g for g in dashboard_data['games_performance'] if g['slug'] == 'word-connections'][0]

        self.assertTrue(wc_metrics['is_active'])
        self.assertEqual(wc_metrics['domain'], 'Semantic Memory')
        self.assertEqual(wc_metrics['completed_count'], 1)
        self.assertEqual(wc_metrics['current_difficulty'], 5)
        self.assertEqual(wc_metrics['avg_accuracy'], 100.0)
        self.assertEqual(wc_metrics['avg_response_time_ms'], 2400)



# ==============================================================================
# Phase 11: Pattern Detective (Visual Pattern Recognition) Tests
# ==============================================================================

from apps.games.services import PATTERN_DETECTIVE_CATALOG, PatternDetectiveEngine


class PatternDetectiveCatalogTests(TestCase):
    """Verifies content integrity, difficulty distribution, and SVG validity for Pattern Detective."""

    def test_catalog_size_and_difficulty_distribution(self):
        """Catalog must contain at least 25 puzzles, exactly 5 per difficulty level (1-5)."""
        self.assertGreaterEqual(len(PATTERN_DETECTIVE_CATALOG), 25)
        diff_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for pid, puzzle in PATTERN_DETECTIVE_CATALOG.items():
            diff = puzzle['difficulty']
            self.assertIn(diff, diff_counts, f"Invalid difficulty {diff} in {pid}")
            diff_counts[diff] += 1

        for diff, count in diff_counts.items():
            self.assertEqual(count, 5, f"Expected exactly 5 puzzles for difficulty {diff}, got {count}")

    def test_puzzle_structure_and_valid_svg(self):
        """Every puzzle must have valid structure, non-empty text, and valid XML SVG."""
        for pid, puzzle in PATTERN_DETECTIVE_CATALOG.items():
            self.assertIn('title', puzzle)
            self.assertIn('prompt', puzzle)
            self.assertIn('explanation', puzzle)
            self.assertIn('pattern_type', puzzle)
            self.assertIn('layout', puzzle)
            self.assertIn(puzzle['layout'], ('linear_sequence', 'matrix_2x2'))

            # Check target
            target = puzzle['target_tile']
            self.assertIn('id', target)
            self.assertIn('name', target)
            self.assertIn('svg', target)
            self.assertTrue(len(target['svg']) > 0)
            # Must parse as XML without error
            ET.fromstring(target['svg'])

            # Check distractors
            for d in puzzle['distractors']:
                self.assertIn('id', d)
                self.assertIn('name', d)
                self.assertIn('svg', d)
                self.assertTrue(len(d['svg']) > 0)
                ET.fromstring(d['svg'])

    def test_choice_counts_and_target_uniqueness(self):
        """Choices count matches difficulty specification: L1=3, L2=4, L3=4, L4=5, L5=6."""
        expected_choices = {1: 3, 2: 4, 3: 4, 4: 5, 5: 6}
        for pid, puzzle in PATTERN_DETECTIVE_CATALOG.items():
            diff = puzzle['difficulty']
            target = puzzle['target_tile']
            distractors = puzzle['distractors']
            self.assertEqual(len(distractors), expected_choices[diff] - 1)

            choices = [target] + distractors
            choice_ids = [c['id'] for c in choices]
            # No duplicate IDs
            self.assertEqual(len(choice_ids), len(set(choice_ids)), f"Duplicate choice IDs in {pid}")
            # Target not in distractors
            self.assertNotIn(target['id'], [d['id'] for d in distractors])


class PatternDetectiveEngineTests(TestCase):
    """Tests for PatternDetectiveEngine logic, deterministic session planning, and evaluation."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='pd_player',
            email='pd@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.game = Game.objects.get(slug='pattern-detective')

    def test_deterministic_session_plan(self):
        """Same session ID and difficulty generates identical 3 distinct puzzles."""
        session1 = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=3,
            status=GameSession.Status.IN_PROGRESS
        )
        plan1 = PatternDetectiveEngine.get_session_plan(session1)
        plan2 = PatternDetectiveEngine.get_session_plan(session1)

        self.assertEqual(len(plan1), 3)
        self.assertEqual(len(plan2), 3)

        pids1 = [plan1[r]['puzzle_id'] for r in range(1, 4)]
        pids2 = [plan2[r]['puzzle_id'] for r in range(1, 4)]

        # Must be 3 distinct puzzles
        self.assertEqual(len(set(pids1)), 3)
        # Deterministic
        self.assertEqual(pids1, pids2)

    def test_round_data_retrieval(self):
        """Valid round numbers return plan; invalid numbers raise ValueError."""
        session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=1,
            status=GameSession.Status.IN_PROGRESS
        )
        for r in range(1, 4):
            data = PatternDetectiveEngine.get_round_data(r, session=session)
            self.assertEqual(data['round_number'], r)
            self.assertEqual(data['total_rounds'], 3)
            self.assertIn('target_tile_id', data)
            self.assertIn('choices', data)

        with self.assertRaises(ValueError):
            PatternDetectiveEngine.get_round_data(0, session=session)
        with self.assertRaises(ValueError):
            PatternDetectiveEngine.get_round_data(4, session=session)

    def test_server_authoritative_evaluation_correct(self):
        """Correct selection returns is_correct=True, score=1, mistake_count=0."""
        session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=2,
            status=GameSession.Status.IN_PROGRESS
        )
        plan = PatternDetectiveEngine.get_session_plan(session=session)
        t1 = plan[1]['target_tile_id']

        result = PatternDetectiveEngine.evaluate_round(1, [t1], 2100, session=session)
        self.assertTrue(result['is_correct'])
        self.assertEqual(result['score'], 1)
        self.assertEqual(result['max_score'], 1)
        self.assertEqual(result['mistake_count'], 0)
        self.assertEqual(result['correct_ids'], [t1])
        self.assertEqual(result['distractor_ids'], [])
        self.assertEqual(result['feedback_tone'], 'success')

    def test_server_authoritative_evaluation_incorrect(self):
        """Incorrect selection returns is_correct=False, score=0, mistake_count=1."""
        session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=2,
            status=GameSession.Status.IN_PROGRESS
        )
        plan = PatternDetectiveEngine.get_session_plan(session=session)
        d1 = plan[1]['distractor_tile_ids'][0]

        result = PatternDetectiveEngine.evaluate_round(1, [d1], 2400, session=session)
        self.assertFalse(result['is_correct'])
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['max_score'], 1)
        self.assertEqual(result['mistake_count'], 1)
        self.assertEqual(result['correct_ids'], [])
        self.assertEqual(result['distractor_ids'], [d1])
        self.assertEqual(result['feedback_tone'], 'encouraging')

    def test_alien_and_multiple_and_empty_selection_evaluation(self):
        """Empty, multiple, or foreign IDs return is_correct=False, score=0 without error."""
        session = GameSession.objects.create(
            member=self.member,
            game=self.game,
            difficulty=4,
            status=GameSession.Status.IN_PROGRESS
        )
        plan = PatternDetectiveEngine.get_session_plan(session=session)
        t1 = plan[1]['target_tile_id']

        # Empty
        res_empty = PatternDetectiveEngine.evaluate_round(1, [], 1000, session=session)
        self.assertFalse(res_empty['is_correct'])
        self.assertEqual(res_empty['score'], 0)

        # Multiple
        res_multi = PatternDetectiveEngine.evaluate_round(1, [t1, 'alien_tile'], 1000, session=session)
        self.assertFalse(res_multi['is_correct'])
        self.assertEqual(res_multi['score'], 0)

        # Alien ID
        res_alien = PatternDetectiveEngine.evaluate_round(1, ['completely_alien_id'], 1000, session=session)
        self.assertFalse(res_alien['is_correct'])
        self.assertEqual(res_alien['score'], 0)


class PatternDetectiveViewsTests(TestCase):
    """Integration and view tests for Pattern Detective lifecycle, UI, security, and privacy."""

    def setUp(self):
        self.client = Client()
        self.member = CustomUser.objects.create_user(
            username='player_pd',
            email='player_pd@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.other_member = CustomUser.objects.create_user(
            username='other_pd',
            email='other_pd@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_pd',
            email='caregiver_pd@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.member,
            is_active=True
        )
        self.game = Game.objects.get(slug='pattern-detective')

    def test_detail_view_shows_instructions_and_is_playable(self):
        """Detail view renders step-by-step instructions and start button for patient."""
        self.client.login(username='player_pd', password='Password123!')
        res = self.client.get(reverse('games:detail', kwargs={'slug': 'pattern-detective'}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Pattern Detective')
        self.assertContains(res, 'Observe the Visual Pattern')
        self.assertContains(res, 'Start Activity')
        self.assertTrue(res.context['is_playable'])

    def test_start_session_creates_fresh_in_progress_session(self):
        """Starting session creates a fresh IN_PROGRESS session and redirects to gameplay."""
        self.client.login(username='player_pd', password='Password123!')
        res = self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 2}
        )
        self.assertEqual(res.status_code, 302)
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        self.assertEqual(session.status, GameSession.Status.IN_PROGRESS)
        self.assertEqual(session.difficulty, 2)
        self.assertEqual(session.max_score, 3)
        self.assertRedirects(res, reverse('games:play', kwargs={'session_id': session.id}))

    def test_gameplay_view_renders_pattern_and_choices(self):
        """Active gameplay view serves the template with prompt and pattern choices."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'games/pattern_detective.html')
        self.assertContains(res, 'Pattern Detective')
        self.assertContains(res, 'Round 1 of 3')
        self.assertContains(res, 'Confirm My Selection')

    def test_full_three_round_gameplay_flow_and_results(self):
        """Completing 3 rounds finalizes session and displays results page correctly."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 3}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = PatternDetectiveEngine.get_session_plan(session=session)
        t1 = plan[1]['target_tile_id']
        t2 = plan[2]['target_tile_id']
        d3 = plan[3]['distractor_tile_ids'][0]

        # Round 1: Correct
        res1 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1800}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()['evaluation']['is_correct'])
        self.assertTrue(res1.json()['has_next_round'])

        # Round 2: Correct
        res2 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 2, 'selected_ids': [t2], 'response_time_ms': 2100}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()['evaluation']['is_correct'])
        self.assertTrue(res2.json()['has_next_round'])

        # Round 3: Incorrect
        res3 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 3, 'selected_ids': [d3], 'response_time_ms': 2500}),
            content_type='application/json'
        )
        self.assertEqual(res3.status_code, 200)
        self.assertFalse(res3.json()['evaluation']['is_correct'])
        self.assertFalse(res3.json()['has_next_round'])

        # Finalize
        comp_res = self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )
        self.assertEqual(comp_res.status_code, 200)

        session.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.COMPLETED)
        self.assertEqual(session.score, 2)
        self.assertEqual(session.max_score, 3)
        self.assertEqual(session.accuracy, Decimal('66.67'))
        self.assertEqual(session.total_time_ms, 6400)

        # Results page inspection
        results_res = self.client.get(reverse('games:results', kwargs={'session_id': session.id}))
        self.assertEqual(results_res.status_code, 200)
        self.assertContains(results_res, 'Patterns Solved')
        self.assertContains(results_res, '✓ Pattern Completed')

    def test_duplicate_submission_blocked(self):
        """Submitting the same round twice returns HTTP 400."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        plan = PatternDetectiveEngine.get_session_plan(session=session)
        t1 = plan[1]['target_tile_id']

        res1 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1500}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)

        res2 = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1500}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 400)

    def test_tamper_rejection_on_completed_session(self):
        """Submitting to a completed session is rejected."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        plan = PatternDetectiveEngine.get_session_plan(session=session)
        for r in range(1, 4):
            t = plan[r]['target_tile_id']
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
            data=json.dumps({'round_number': 1, 'selected_ids': ['leaf_teal'], 'response_time_ms': 1000}),
            content_type='application/json'
        )
        self.assertEqual(tamper_res.status_code, 400)

    def test_premature_completion_rejected(self):
        """Cannot complete session before 3 rounds are submitted."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        res = self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)

    def test_caregiver_cannot_start_or_play(self):
        """Caregivers cannot initiate or play Pattern Detective."""
        self.client.login(username='caregiver_pd', password='Password123!')
        res_detail = self.client.get(reverse('games:detail', kwargs={'slug': 'pattern-detective'}))
        self.assertEqual(res_detail.status_code, 403)

        res_start = self.client.post(reverse('games:start_session', kwargs={'slug': 'pattern-detective'}))
        self.assertEqual(res_start.status_code, 403)

    def test_another_patient_cannot_access_session(self):
        """A different patient cannot view or submit to another member's session."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        self.client.login(username='other_pd', password='Password123!')
        res_play = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res_play.status_code, 404)

        res_sub = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': ['leaf_teal'], 'response_time_ms': 1000}),
            content_type='application/json'
        )
        self.assertEqual(res_sub.status_code, 404)

    def test_client_supplied_score_ignored(self):
        """Server ignores client-supplied score, is_correct, and accuracy fields."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        plan = PatternDetectiveEngine.get_session_plan(session=session)
        d1 = plan[1]['distractor_tile_ids'][0]

        # Client submits incorrect ID but claims score=99, is_correct=True
        tampered_res = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({
                'round_number': 1,
                'selected_ids': [d1],
                'response_time_ms': 1200,
                'score': 99,
                'is_correct': True,
                'accuracy': 100.0
            }),
            content_type='application/json'
        )
        self.assertEqual(tampered_res.status_code, 200)
        eval_data = tampered_res.json()['evaluation']
        self.assertFalse(eval_data['is_correct'])
        self.assertEqual(eval_data['score'], 0)

        round_obj = session.rounds.get(round_number=1)
        self.assertFalse(round_obj.is_correct)

    def test_telemetry_privacy_invariants(self):
        """GameRound.stimulus_data contains ONLY stable IDs and metadata; no SVG, HTML, or PII."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 2}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')
        plan = PatternDetectiveEngine.get_session_plan(session=session)
        t1 = plan[1]['target_tile_id']

        sub_res = self.client.post(
            reverse('games:submit_round', kwargs={'session_id': session.id}),
            data=json.dumps({'round_number': 1, 'selected_ids': [t1], 'response_time_ms': 1900}),
            content_type='application/json'
        )
        self.assertEqual(sub_res.status_code, 200)

        round_obj = session.rounds.get(round_number=1)
        stimulus = round_obj.stimulus_data

        # Verify key presence and structure
        self.assertIn('puzzle_id', stimulus)
        self.assertIn('pattern_type', stimulus)
        self.assertIn('target_tile_id', stimulus)
        self.assertEqual(stimulus['target_tile_id'], t1)
        self.assertIn('distractor_tile_ids', stimulus)
        self.assertIn('choice_tile_ids', stimulus)
        self.assertEqual(len(stimulus['choice_tile_ids']), 4)  # Diff 2 has 4 choices

        # Verify strict absence of SVG, HTML, or PII
        stimulus_str = json.dumps(stimulus)
        self.assertNotIn('<svg', stimulus_str)
        self.assertNotIn('</svg>', stimulus_str)
        self.assertNotIn('user_id', stimulus)
        self.assertNotIn('username', stimulus)
        self.assertNotIn('player_pd', stimulus_str)
        self.assertNotIn('explanation', stimulus)
        self.assertNotIn('prompt', stimulus)

        # Expected and actual responses
        self.assertEqual(round_obj.expected_response, {'target_ids': [t1]})
        self.assertEqual(round_obj.actual_response['selected_ids'], [t1])
        self.assertEqual(round_obj.actual_response['correct_ids'], [t1])
        self.assertTrue(round_obj.is_correct)

    def test_caregiver_dashboard_reflects_pattern_detective(self):
        """Caregiver dashboard automatically aggregates completed Pattern Detective sessions under 'Reasoning & Logic'."""
        self.client.login(username='player_pd', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 4}
        )
        session = GameSession.objects.filter(member=self.member, game=self.game).latest('created_at')

        plan = PatternDetectiveEngine.get_session_plan(session=session)
        for r in range(1, 4):
            t = plan[r]['target_tile_id']
            self.client.post(
                reverse('games:submit_round', kwargs={'session_id': session.id}),
                data=json.dumps({'round_number': r, 'selected_ids': [t], 'response_time_ms': 2200}),
                content_type='application/json'
            )
        self.client.post(
            reverse('games:complete_session', kwargs={'session_id': session.id}),
            content_type='application/json'
        )

        dashboard_data = get_caregiver_dashboard_data(self.caregiver, member_id=self.member.id)
        pd_metrics = [g for g in dashboard_data['games_performance'] if g['slug'] == 'pattern-detective'][0]

        self.assertTrue(pd_metrics['is_active'])
        self.assertEqual(pd_metrics['domain'], 'Reasoning & Logic')
        self.assertEqual(pd_metrics['completed_count'], 1)
        self.assertEqual(pd_metrics['current_difficulty'], 4)
        self.assertEqual(pd_metrics['avg_accuracy'], 100.0)
        self.assertEqual(pd_metrics['avg_response_time_ms'], 2200)


class GlobalVoiceSystemTests(TestCase):
    """Verifies Phase 12: Global Cognicare Voice System across all games and shared views."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='player_voice',
            email='pv@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_voice',
            email='cv@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.member.assigned_caregiver = self.caregiver
        self.member.save()

    def test_base_template_loads_voice_script(self):
        """Confirms cognicare-voice.js is loaded in base.html."""
        self.client.login(username='player_voice', password='Password123!')
        res = self.client.get(reverse('games:list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'js/cognicare-voice.js')

    def test_all_game_detail_pages_have_voice_buttons(self):
        """Verifies that all 6 games have voice listen buttons on their detail / instruction page."""
        self.client.login(username='player_voice', password='Password123!')
        slugs = [
            'memory-market',
            'daily-life-journey',
            'familiar-faces',
            'focus-finder',
            'word-connections',
            'pattern-detective',
        ]
        for slug in slugs:
            res = self.client.get(reverse('games:detail', kwargs={'slug': slug}))
            self.assertEqual(res.status_code, 200, f"Detail page failed for {slug}")
            self.assertContains(res, 'btn-voice', msg_prefix=f"{slug} missing btn-voice")
            self.assertContains(res, 'data-voice-target="#game-overview-text"', msg_prefix=f"{slug} missing overview voice")
            self.assertContains(res, 'data-voice-target="#instructions-content"', msg_prefix=f"{slug} missing instructions voice")

    def test_game_results_page_has_voice_button(self):
        """Verifies results page contains voice read-aloud button for summary and encouragement."""
        self.client.login(username='player_voice', password='Password123!')
        game = Game.objects.get(slug='memory-market')
        session = GameSession.objects.create(
            member=self.member,
            game=game,
            difficulty=1,
            status=GameSession.Status.COMPLETED,
            score=3,
            max_score=3,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )
        for r in range(1, 4):
            GameRound.objects.create(
                session=session,
                round_number=r,
                is_correct=True,
                response_time_ms=1200,
            )
        res = self.client.get(reverse('games:results', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="btn-speak-results"')
        self.assertContains(res, 'btn-voice')
        self.assertContains(res, 'data-voice-speak')

    def test_memory_market_template_voice_hooks(self):
        """Confirms Memory Market active game page renders voice buttons in memory, selection, and feedback stages."""
        self.client.login(username='player_voice', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'memory-market'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game__slug='memory-market').latest('created_at')
        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="btn-speak-targets"')
        self.assertContains(res, 'id="btn-speak-selection-prompt"')
        self.assertContains(res, 'id="btn-speak-feedback"')
        self.assertContains(res, 'js/gameplay_engine.js')

    def test_daily_life_journey_template_voice_hooks(self):
        """Confirms Daily Life Journey active game page renders voice buttons for scenario and feedback."""
        self.client.login(username='player_voice', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'daily-life-journey'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game__slug='daily-life-journey').latest('created_at')
        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="btn-speak-scenario"')
        self.assertContains(res, 'id="btn-speak-feedback"')
        self.assertContains(res, 'js/daily_life_journey.js')

    def test_familiar_faces_template_voice_hooks(self):
        """Confirms Familiar Faces renders question voice button, feedback voice button, and choice voice buttons."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.memories.models import FamiliarPerson
        self.client.login(username='player_voice', password='Password123!')
        for i in range(1, 6):
            photo = SimpleUploadedFile(
                name=f'person_voice_{i}.jpg',
                content=b'\xff\xd8\xff\xe0' + b'0' * 500,
                content_type='image/jpeg'
            )
            FamiliarPerson.objects.create(
                member=self.member,
                name=f'Relative {i}',
                relationship=f'Relation {i}',
                photo=photo,
                is_active=True
            )
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'familiar-faces'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game__slug='familiar-faces').latest('created_at')
        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="btn-speak-prompt"')
        self.assertContains(res, 'id="btn-speak-feedback"')
        self.assertContains(res, 'choice-voice-btn')
        self.assertContains(res, 'js/familiar_faces.js')

    def test_focus_finder_template_voice_hooks(self):
        """Confirms Focus Finder renders target voice button and feedback voice button with .btn-voice."""
        self.client.login(username='player_voice', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'focus-finder'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game__slug='focus-finder').latest('created_at')
        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="btn-speak-target"')
        self.assertContains(res, 'id="btn-speak-feedback"')
        self.assertContains(res, 'class="btn-voice"')
        self.assertContains(res, 'js/focus_finder.js')

    def test_word_connections_template_voice_hooks(self):
        """Confirms Word Connections renders prompt voice button, feedback voice button, and word card audio buttons."""
        self.client.login(username='player_voice', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'word-connections'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game__slug='word-connections').latest('created_at')
        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="btn-speak-prompt"')
        self.assertContains(res, 'id="btn-speak-feedback"')
        self.assertContains(res, 'word-card-audio-btn')
        self.assertContains(res, 'js/word_connections.js')

    def test_pattern_detective_template_voice_hooks(self):
        """Confirms Pattern Detective renders prompt voice button, feedback voice button, and choice audio buttons."""
        self.client.login(username='player_voice', password='Password123!')
        self.client.post(
            reverse('games:start_session', kwargs={'slug': 'pattern-detective'}),
            data={'difficulty': 1}
        )
        session = GameSession.objects.filter(member=self.member, game__slug='pattern-detective').latest('created_at')
        res = self.client.get(reverse('games:play', kwargs={'session_id': session.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="btn-speak-prompt"')
        self.assertContains(res, 'id="btn-speak-feedback"')
        self.assertContains(res, 'pattern-tile-audio-btn')
        self.assertContains(res, 'js/pattern_detective.js')

    def test_zero_emoji_in_voice_controls_across_templates(self):
        """Confirms strictly zero emoji characters in all game templates, base, detail, and results."""
        import os
        from django.conf import settings

        template_files = [
            'base.html',
            'games/game_detail.html',
            'games/game_results.html',
            'games/memory_market.html',
            'games/daily_life_journey.html',
            'games/familiar_faces.html',
            'games/focus_finder.html',
            'games/word_connections.html',
            'games/pattern_detective.html',
        ]
        forbidden_emojis = ['🔊', '⏹', '🗣']

        for rel_path in template_files:
            full_path = os.path.join(settings.BASE_DIR, 'templates', rel_path)
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            for emoji in forbidden_emojis:
                self.assertNotIn(
                    emoji,
                    content,
                    f"Template {rel_path} must not contain emoji '{emoji}'"
                )

    def test_voice_singleton_js_content_and_safety(self):
        """Inspects static/js/cognicare-voice.js for required safety and singleton architecture."""
        import os
        from django.conf import settings

        voice_js_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'cognicare-voice.js')
        self.assertTrue(os.path.exists(voice_js_path), "cognicare-voice.js must exist")

        with open(voice_js_path, 'r', encoding='utf-8') as f:
            code = f.read()

        self.assertIn('window.CognicareVoice', code)
        self.assertIn('isSupported', code)
        self.assertIn('isSpeaking', code)
        self.assertIn('speak(', code)
        self.assertIn('stop(', code)
        self.assertIn('toggle(', code)
        self.assertIn('pagehide', code)
        self.assertIn('beforeunload', code)
        self.assertIn('_activeUtterance', code)
        self.assertIn('0.9', code)

    def test_voice_css_styles_exist(self):
        """Inspects static/css/cognicare.css for Phase 12 voice styles."""
        import os
        from django.conf import settings

        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'cognicare.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('.btn-voice', css)
        self.assertIn('.btn-voice.is-speaking', css)
        self.assertIn('.btn-voice-sm', css)
        self.assertIn('.choice-voice-btn', css)
        self.assertIn('min-height: 44px', css)

