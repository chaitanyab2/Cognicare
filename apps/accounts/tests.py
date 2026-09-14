import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, CaregiverMemberRelationship
from apps.games.models import Game, GameSession, GameRound
from apps.routines.models import Routine, RoutineItem


CustomUser = get_user_model()


class CustomUserModelTests(TestCase):
    """Tests for CustomUser model and role attributes."""

    def test_custom_user_creation(self):
        user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.role, Role.PATIENT)  # default

    def test_patient_role(self):
        patient = CustomUser.objects.create_user(
            username='patient1',
            email='patient1@example.com',
            password='TestPassword123!',
            role=Role.PATIENT
        )
        self.assertEqual(patient.role, Role.PATIENT)
        self.assertTrue(patient.is_patient)
        self.assertFalse(patient.is_caregiver)
        self.assertEqual(str(patient), 'patient1 (Patient)')

    def test_caregiver_role(self):
        caregiver = CustomUser.objects.create_user(
            username='caregiver1',
            email='caregiver1@example.com',
            password='TestPassword123!',
            role=Role.CAREGIVER
        )
        self.assertEqual(caregiver.role, Role.CAREGIVER)
        self.assertTrue(caregiver.is_caregiver)
        self.assertFalse(caregiver.is_patient)
        self.assertEqual(str(caregiver), 'caregiver1 (Caregiver)')

    def test_password_hashing(self):
        password = 'SecurePassword123!'
        user = CustomUser.objects.create_user(
            username='hashuser',
            email='hash@example.com',
            password=password
        )
        # Verify plaintext password is NOT stored
        self.assertNotEqual(user.password, password)
        self.assertTrue(user.password.startswith('pbkdf2_') or user.password.startswith('argon2'))
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.check_password('WrongPassword'))


class AuthenticationFlowTests(TestCase):
    """Tests for registration, login, logout, and access protection."""

    def setUp(self):
        self.client = Client()
        self.patient = CustomUser.objects.create_user(
            username='patient_user',
            email='patient@example.com',
            password='ValidPassword123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_user',
            email='caregiver@example.com',
            password='ValidPassword123!',
            role=Role.CAREGIVER
        )

    def test_successful_login_patient_redirect(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'patient_user',
            'password': 'ValidPassword123!',
        })
        self.assertRedirects(response, reverse('accounts:patient_portal'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.patient.pk)

    def test_successful_login_caregiver_redirect(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'caregiver_user',
            'password': 'ValidPassword123!',
        })
        self.assertRedirects(response, reverse('accounts:caregiver_portal'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.caregiver.pk)

    def test_invalid_login_rejected(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'patient_user',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_patient_signup(self):
        response = self.client.post(reverse('accounts:patient_signup'), {
            'username': 'newpatient',
            'email': 'newpatient@example.com',
            'first_name': 'Aarav',
            'last_name': 'Barua',
            'password1': 'StrongSecret123!',
            'password2': 'StrongSecret123!',
        })
        self.assertRedirects(response, reverse('accounts:patient_portal'))
        created = CustomUser.objects.get(username='newpatient')
        self.assertEqual(created.role, Role.PATIENT)
        self.assertTrue(created.is_patient)
        self.assertEqual(created.first_name, 'Aarav')
        self.assertTrue(created.check_password('StrongSecret123!'))

    def test_caregiver_signup(self):
        response = self.client.post(reverse('accounts:caregiver_signup'), {
            'username': 'newcaregiver',
            'email': 'newcaregiver@example.com',
            'first_name': 'Priya',
            'last_name': 'Barua',
            'password1': 'StrongSecret123!',
            'password2': 'StrongSecret123!',
        })
        self.assertRedirects(response, reverse('accounts:caregiver_portal'))
        created = CustomUser.objects.get(username='newcaregiver')
        self.assertEqual(created.role, Role.CAREGIVER)
        self.assertTrue(created.is_caregiver)
        self.assertEqual(created.first_name, 'Priya')
        self.assertTrue(created.check_password('StrongSecret123!'))

    def test_duplicate_username_signup_rejected(self):
        response = self.client.post(reverse('accounts:patient_signup'), {
            'username': 'patient_user',  # already exists
            'email': 'unique@example.com',
            'first_name': 'Duplicate',
            'last_name': 'User',
            'password1': 'StrongSecret123!',
            'password2': 'StrongSecret123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists.")

    def test_duplicate_email_signup_rejected(self):
        response = self.client.post(reverse('accounts:patient_signup'), {
            'username': 'unique_user',
            'email': 'patient@example.com',  # already exists
            'first_name': 'Duplicate',
            'last_name': 'Email',
            'password1': 'StrongSecret123!',
            'password2': 'StrongSecret123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with this email address already exists.")

    def test_logout_clears_session(self):
        self.client.login(username='patient_user', password='ValidPassword123!')
        self.assertIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_role_based_access_protection(self):
        # 1. Unauthenticated users are redirected to login
        unauth_patient_resp = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(unauth_patient_resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), unauth_patient_resp.url)

        unauth_caregiver_resp = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(unauth_caregiver_resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), unauth_caregiver_resp.url)

        # 2. Patient can access patient portal, but is denied caregiver portal (403)
        self.client.login(username='patient_user', password='ValidPassword123!')
        p_portal_resp = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(p_portal_resp.status_code, 200)
        self.assertContains(p_portal_resp, "My Space")

        p_denied_resp = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(p_denied_resp.status_code, 403)

        self.client.logout()

        # 3. Caregiver can access caregiver portal, but is denied patient portal (403)
        self.client.login(username='caregiver_user', password='ValidPassword123!')
        c_portal_resp = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(c_portal_resp.status_code, 200)
        self.assertContains(c_portal_resp, "Caregiver Portal")

        c_denied_resp = self.client.get(reverse('accounts:patient_portal'))
        self.assertEqual(c_denied_resp.status_code, 403)


class CaregiverMemberRelationshipTests(TestCase):
    """Tests for CaregiverMemberRelationship and role integrity."""

    def setUp(self):
        self.caregiver1 = CustomUser.objects.create_user(
            username='caregiver_alpha',
            email='cg_alpha@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.caregiver2 = CustomUser.objects.create_user(
            username='caregiver_beta',
            email='cg_beta@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.member1 = CustomUser.objects.create_user(
            username='member_one',
            email='m_one@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.member2 = CustomUser.objects.create_user(
            username='member_two',
            email='m_two@example.com',
            password='Password123!',
            role=Role.PATIENT
        )

    def test_valid_relationship_creation(self):
        rel = CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver1,
            member=self.member1,
            is_active=True
        )
        self.assertEqual(rel.caregiver, self.caregiver1)
        self.assertEqual(rel.member, self.member1)
        self.assertTrue(rel.is_active)
        self.assertIn("Active", str(rel))
        self.assertIn("caregiver_alpha", str(rel))

    def test_inactive_relationship_behavior(self):
        rel = CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver1,
            member=self.member1,
            is_active=False
        )
        self.assertFalse(rel.is_active)
        self.assertIn("Inactive", str(rel))

    def test_duplicate_relationship_prevented(self):
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver1,
            member=self.member1
        )
        from django.db import IntegrityError
        with self.assertRaises((IntegrityError, Exception)):
            CaregiverMemberRelationship.objects.create(
                caregiver=self.caregiver1,
                member=self.member1
            )

    def test_caregiver_must_have_caregiver_role(self):
        from django.core.exceptions import ValidationError
        # Attempt to use a PATIENT user as the caregiver
        with self.assertRaises(ValidationError) as ctx:
            rel = CaregiverMemberRelationship(
                caregiver=self.member2,  # Invalid: has Role.PATIENT
                member=self.member1
            )
            rel.save()
        self.assertIn('caregiver', ctx.exception.message_dict)

    def test_member_must_have_patient_role(self):
        from django.core.exceptions import ValidationError
        # Attempt to use a CAREGIVER user as the member
        with self.assertRaises(ValidationError) as ctx:
            rel = CaregiverMemberRelationship(
                caregiver=self.caregiver1,
                member=self.caregiver2  # Invalid: has Role.CAREGIVER
            )
            rel.save()
        self.assertIn('member', ctx.exception.message_dict)

    def test_self_relationship_rejected(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            rel = CaregiverMemberRelationship(
                caregiver=self.caregiver1,
                member=self.caregiver1
            )
            rel.save()

    def test_one_caregiver_multiple_members(self):
        CaregiverMemberRelationship.objects.create(caregiver=self.caregiver1, member=self.member1)
        CaregiverMemberRelationship.objects.create(caregiver=self.caregiver1, member=self.member2)
        self.assertEqual(self.caregiver1.caregiver_relationships.count(), 2)

    def test_one_member_multiple_caregivers(self):
        CaregiverMemberRelationship.objects.create(caregiver=self.caregiver1, member=self.member1)
        CaregiverMemberRelationship.objects.create(caregiver=self.caregiver2, member=self.member1)
        self.assertEqual(self.member1.member_relationships.count(), 2)


class CaregiverDashboardTests(TestCase):
    """Tests for Phase 7 Caregiver Analytics Dashboard."""

    def setUp(self):
        self.client = Client()
        self.caregiver = CustomUser.objects.create_user(
            username='caregiver_mary',
            email='mary@example.com',
            password='Password123!',
            first_name='Mary',
            last_name='Caregiver',
            role=Role.CAREGIVER
        )
        self.other_caregiver = CustomUser.objects.create_user(
            username='caregiver_john',
            email='john@example.com',
            password='Password123!',
            first_name='John',
            role=Role.CAREGIVER
        )
        self.patient1 = CustomUser.objects.create_user(
            username='patient_arthur',
            email='arthur@example.com',
            password='Password123!',
            first_name='Arthur',
            last_name='Pendleton',
            role=Role.PATIENT
        )
        self.patient2 = CustomUser.objects.create_user(
            username='patient_beatrice',
            email='beatrice@example.com',
            password='Password123!',
            first_name='Beatrice',
            last_name='Holloway',
            role=Role.PATIENT
        )
        self.unlinked_patient = CustomUser.objects.create_user(
            username='patient_unlinked',
            email='unlinked@example.com',
            password='Password123!',
            first_name='Unlinked',
            role=Role.PATIENT
        )

        # Establish active supervision relationship for Mary -> Arthur
        self.rel1 = CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.patient1,
            is_active=True
        )

        self.memory_game = Game.objects.get(slug='memory-market')
        self.daily_life_game = Game.objects.get(slug='daily-life-journey')

    def test_caregiver_can_access_dashboard(self):
        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Caregiver Analytics Dashboard")
        self.assertContains(response, "Arthur")
        self.assertContains(response, "Games Completed")
        self.assertContains(response, "Overall Accuracy")
        self.assertContains(response, "Average Response Time")
        self.assertContains(response, "Routine Adherence")

    def test_patient_blocked_from_caregiver_dashboard(self):
        self.client.login(username='patient_arthur', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_dashboard_with_no_linked_patients(self):
        self.client.login(username='caregiver_john', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Member Profiles Connected Yet")
        self.assertFalse(response.context['dashboard']['has_members'])

    def test_dashboard_aggregates_real_session_data(self):
        # Create 2 completed sessions for patient1
        now = timezone.now()
        s1 = GameSession.objects.create(
            member=self.patient1,
            game=self.memory_game,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=3,
            max_score=3,
            accuracy=100.0,
            started_at=now - datetime.timedelta(hours=2),
            completed_at=now - datetime.timedelta(hours=1)
        )
        GameRound.objects.create(
            session=s1,
            round_number=1,
            response_time_ms=2000,
            is_correct=True
        )

        s2 = GameSession.objects.create(
            member=self.patient1,
            game=self.daily_life_game,
            status=GameSession.Status.COMPLETED,
            difficulty=2,
            score=1,
            max_score=2,
            accuracy=50.0,
            started_at=now - datetime.timedelta(minutes=30),
            completed_at=now - datetime.timedelta(minutes=15)
        )
        GameRound.objects.create(
            session=s2,
            round_number=1,
            response_time_ms=4000,
            is_correct=False
        )

        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 200)

        data = response.context['dashboard']
        self.assertEqual(data['total_completed_games'], 2)
        self.assertEqual(data['sessions_past_7_days'], 2)
        self.assertEqual(data['overall_avg_accuracy'], 75.0)
        self.assertEqual(data['avg_response_time_ms'], 3000)
        self.assertEqual(data['avg_response_time_sec'], 3.0)

        # Check HTML renders these values
        self.assertContains(response, "75.0%")
        self.assertContains(response, "3.0s")
        self.assertContains(response, "3000 ms")

    def test_incomplete_sessions_excluded_from_metrics(self):
        now = timezone.now()
        # Completed session (100% accuracy)
        GameSession.objects.create(
            member=self.patient1,
            game=self.memory_game,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=3,
            max_score=3,
            accuracy=100.0,
            started_at=now - datetime.timedelta(hours=1),
            completed_at=now
        )
        # IN_PROGRESS session (should be excluded)
        GameSession.objects.create(
            member=self.patient1,
            game=self.memory_game,
            status=GameSession.Status.IN_PROGRESS,
            difficulty=1,
            score=0,
            max_score=3,
            accuracy=0.0,
            started_at=now
        )
        # ABANDONED session (should be excluded)
        GameSession.objects.create(
            member=self.patient1,
            game=self.memory_game,
            status=GameSession.Status.ABANDONED,
            difficulty=1,
            score=1,
            max_score=3,
            accuracy=Decimal('33.33'),
            started_at=now - datetime.timedelta(days=2)
        )

        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        data = response.context['dashboard']
        self.assertEqual(data['total_completed_games'], 1)
        self.assertEqual(data['overall_avg_accuracy'], 100.0)

    def test_cross_patient_data_isolation(self):
        # Link Mary to patient2 as well
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.patient2,
            is_active=True
        )

        now = timezone.now()
        # Session for patient1: 90%
        GameSession.objects.create(
            member=self.patient1,
            game=self.memory_game,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=9,
            max_score=10,
            accuracy=90.0,
            started_at=now - datetime.timedelta(hours=2),
            completed_at=now - datetime.timedelta(hours=1)
        )
        # Session for patient2: 40%
        GameSession.objects.create(
            member=self.patient2,
            game=self.memory_game,
            status=GameSession.Status.COMPLETED,
            difficulty=1,
            score=4,
            max_score=10,
            accuracy=40.0,
            started_at=now - datetime.timedelta(hours=2),
            completed_at=now - datetime.timedelta(hours=1)
        )

        self.client.login(username='caregiver_mary', password='Password123!')

        # Default view (patient1)
        resp1 = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(resp1.context['dashboard']['selected_member'].id, self.patient1.id)
        self.assertEqual(resp1.context['dashboard']['overall_avg_accuracy'], 90.0)

        # Switch to patient2
        resp2 = self.client.get(f"{reverse('accounts:caregiver_portal')}?member={self.patient2.id}")
        self.assertEqual(resp2.context['dashboard']['selected_member'].id, self.patient2.id)
        self.assertEqual(resp2.context['dashboard']['overall_avg_accuracy'], 40.0)

    def test_multiple_patients_selector(self):
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.patient2,
            is_active=True
        )

        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Switch Supervised Member:')
        self.assertContains(response, 'patient_arthur')
        self.assertContains(response, 'patient_beatrice')

    def test_unauthorized_member_id_returns_404(self):
        self.client.login(username='caregiver_mary', password='Password123!')

        # Unlinked patient id
        resp1 = self.client.get(f"{reverse('accounts:caregiver_portal')}?member={self.unlinked_patient.id}")
        self.assertEqual(resp1.status_code, 404)

        # Nonexistent id
        resp2 = self.client.get(f"{reverse('accounts:caregiver_portal')}?member=999999")
        self.assertEqual(resp2.status_code, 404)

        # Non-numeric id
        resp3 = self.client.get(f"{reverse('accounts:caregiver_portal')}?member=invalid_abc")
        self.assertEqual(resp3.status_code, 404)

    def test_inactive_relationship_excluded(self):
        # Create an inactive relationship for patient2
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.patient2,
            is_active=False
        )
        self.client.login(username='caregiver_mary', password='Password123!')
        # Requesting inactive patient2 should return 404
        response = self.client.get(f"{reverse('accounts:caregiver_portal')}?member={self.patient2.id}")
        self.assertEqual(response.status_code, 404)

    def test_routine_adherence_calculation(self):
        today = timezone.localdate()
        routine = Routine.objects.create(
            member=self.patient1,
            title="Daily Wellness Routine",
            date=today,
            is_active=True
        )
        RoutineItem.objects.create(
            routine=routine,
            title="Morning Hydration",
            is_completed=True,
            display_order=1
        )
        RoutineItem.objects.create(
            routine=routine,
            title="Gentle Walk",
            is_completed=True,
            display_order=2
        )
        RoutineItem.objects.create(
            routine=routine,
            title="Memory Activity",
            is_completed=True,
            display_order=3
        )
        RoutineItem.objects.create(
            routine=routine,
            title="Evening Relaxation",
            is_completed=False,
            display_order=4
        )

        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 200)

        data = response.context['dashboard']
        self.assertEqual(data['routine_total_items'], 4)
        self.assertEqual(data['routine_completed_items'], 3)
        self.assertEqual(data['routine_adherence_pct'], 75)
        self.assertContains(response, "75%")
        self.assertContains(response, "3 of 4 tasks logged today")

    def test_chart_data_points_generation(self):
        now = timezone.now()
        for idx, (score, max_score, acc) in enumerate([(2, 3, Decimal('66.67')), (3, 3, Decimal('100.00')), (2, 2, Decimal('100.00'))], start=1):
            GameSession.objects.create(
                member=self.patient1,
                game=self.memory_game,
                status=GameSession.Status.COMPLETED,
                difficulty=1,
                score=score,
                max_score=max_score,
                accuracy=acc,
                started_at=now - datetime.timedelta(hours=10 - idx),
                completed_at=now - datetime.timedelta(hours=9 - idx)
            )

        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 200)

        data = response.context['dashboard']
        self.assertTrue(data['chart_has_data'])
        self.assertEqual(len(data['chart_points']), 3)
        self.assertTrue(len(data['chart_polyline']) > 0)

        # SVG elements rendered in HTML
        self.assertContains(response, "<polyline")
        self.assertContains(response, "<circle")
        self.assertContains(response, "View chart data as text table")

    def test_all_six_games_in_performance_table(self):
        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertEqual(response.status_code, 200)

        games_perf = response.context['dashboard']['games_performance']
        self.assertEqual(len(games_perf), 6)
        slugs = [g['slug'] for g in games_perf]
        self.assertIn('memory-market', slugs)
        self.assertIn('daily-life-journey', slugs)
        self.assertIn('familiar-faces', slugs)
        self.assertIn('focus-finder', slugs)
        self.assertIn('word-connections', slugs)
        self.assertIn('pattern-detective', slugs)

    def test_non_clinical_disclaimer_present(self):
        self.client.login(username='caregiver_mary', password='Password123!')
        response = self.client.get(reverse('accounts:caregiver_portal'))
        self.assertContains(response, "Platform Notice:")
        self.assertContains(response, "Cognicare is a cognitive wellness and daily engagement platform.")
        # Ensure non-clinical compliance
        self.assertNotContains(response, "cognitive decline")
        self.assertNotContains(response, "dementia diagnosis")
        self.assertNotContains(response, "neurological disease")

