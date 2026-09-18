from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Role
from apps.memories.models import Memory

CustomUser = get_user_model()


class MemoryModelTests(TestCase):
    """Tests for the Memory model."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='memory_member',
            email='mm@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='memory_caregiver',
            email='mc@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )

    def test_valid_memory_creation(self):
        mem = Memory.objects.create(
            member=self.member,
            title='Picnic in Kaziranga',
            description='A beautiful sunny day by the tea garden.'
        )
        self.assertEqual(mem.member, self.member)
        self.assertEqual(mem.title, 'Picnic in Kaziranga')
        self.assertEqual(mem.description, 'A beautiful sunny day by the tea garden.')
        self.assertIsNotNone(mem.created_at)
        self.assertIn('Picnic in Kaziranga', str(mem))

    def test_member_can_have_multiple_memories(self):
        Memory.objects.create(member=self.member, title='Memory 1')
        Memory.objects.create(member=self.member, title='Memory 2')
        self.assertEqual(self.member.memories.count(), 2)

    def test_caregiver_cannot_be_memory_owner(self):
        with self.assertRaises(ValidationError):
            mem = Memory(
                member=self.caregiver,  # Invalid: has Role.CAREGIVER
                title='Invalid Memory'
            )
            mem.save()


from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import CaregiverMemberRelationship
from apps.memories.models import FamiliarPerson


class FamiliarPersonModelTests(TestCase):
    """Tests for FamiliarPerson model and image upload validation."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='person_member',
            email='pm@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='person_caregiver',
            email='pc@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        # Valid dummy image bytes
        self.valid_jpeg = SimpleUploadedFile(
            name='test_photo.jpg',
            content=b'\xff\xd8\xff\xe0' + b'0' * 500,
            content_type='image/jpeg'
        )
        self.valid_png = SimpleUploadedFile(
            name='test_photo.png',
            content=b'\x89PNG\r\n\x1a\n' + b'0' * 500,
            content_type='image/png'
        )
        self.valid_webp = SimpleUploadedFile(
            name='test_photo.webp',
            content=b'RIFF\x00\x00\x00\x00WEBPVP8 ' + b'0' * 500,
            content_type='image/webp'
        )

    def test_valid_familiar_person_creation(self):
        person = FamiliarPerson(
            member=self.member,
            name='Ananya Sharma',
            relationship='Daughter',
            photo=self.valid_jpeg,
            is_active=True
        )
        person.full_clean()
        person.save()

        self.assertEqual(person.member, self.member)
        self.assertEqual(person.name, 'Ananya Sharma')
        self.assertEqual(person.relationship, 'Daughter')
        self.assertTrue(person.is_active)
        self.assertIn('Ananya Sharma', str(person))
        self.assertIn('Daughter', str(person))

    def test_valid_png_and_webp_creation(self):
        p_png = FamiliarPerson(
            member=self.member,
            name='Rohan',
            relationship='Son',
            photo=self.valid_png
        )
        p_png.full_clean()
        p_png.save()
        self.assertEqual(p_png.name, 'Rohan')

        p_webp = FamiliarPerson(
            member=self.member,
            name='Maya',
            relationship='Granddaughter',
            photo=self.valid_webp
        )
        p_webp.full_clean()
        p_webp.save()
        self.assertEqual(p_webp.name, 'Maya')

    def test_caregiver_cannot_own_familiar_person(self):
        person = FamiliarPerson(
            member=self.caregiver,
            name='Invalid Owner',
            relationship='Friend',
            photo=self.valid_jpeg
        )
        with self.assertRaises(ValidationError):
            person.full_clean()

    def test_invalid_file_extension_rejected(self):
        bad_file = SimpleUploadedFile(
            name='document.pdf',
            content=b'%PDF-1.4\n' + b'0' * 100,
            content_type='application/pdf'
        )
        person = FamiliarPerson(
            member=self.member,
            name='Bad Extension',
            relationship='Friend',
            photo=bad_file
        )
        with self.assertRaises(ValidationError) as ctx:
            person.full_clean()
        self.assertIn('photo', ctx.exception.message_dict)

    def test_corrupted_magic_bytes_rejected(self):
        # Named .jpg but contents are plain text
        fake_jpg = SimpleUploadedFile(
            name='fake.jpg',
            content=b'This is just a text file with a fake jpg extension.',
            content_type='image/jpeg'
        )
        person = FamiliarPerson(
            member=self.member,
            name='Fake Jpg',
            relationship='Friend',
            photo=fake_jpg
        )
        with self.assertRaises(ValidationError) as ctx:
            person.full_clean()
        self.assertIn('photo', ctx.exception.message_dict)

    def test_file_size_exceeding_5mb_rejected(self):
        oversized_data = b'\xff\xd8\xff\xe0' + (b'0' * (5 * 1024 * 1024 + 10))
        big_jpg = SimpleUploadedFile(
            name='huge.jpg',
            content=oversized_data,
            content_type='image/jpeg'
        )
        person = FamiliarPerson(
            member=self.member,
            name='Big Photo',
            relationship='Friend',
            photo=big_jpg
        )
        with self.assertRaises(ValidationError) as ctx:
            person.full_clean()
        self.assertIn('photo', ctx.exception.message_dict)


class FamiliarPersonCaregiverViewTests(TestCase):
    """Tests for Caregiver Familiar Person management views and authorization."""

    def setUp(self):
        self.client = Client()
        self.caregiver = CustomUser.objects.create_user(
            username='cg_alpha',
            email='alpha@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.caregiver_other = CustomUser.objects.create_user(
            username='cg_beta',
            email='beta@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.patient = CustomUser.objects.create_user(
            username='patient_alpha',
            email='p_alpha@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.patient_other = CustomUser.objects.create_user(
            username='patient_beta',
            email='p_beta@example.com',
            password='Password123!',
            role=Role.PATIENT
        )

        # Active supervision link: caregiver -> patient
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver,
            member=self.patient,
            is_active=True
        )
        # Active supervision link: caregiver_other -> patient_other
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver_other,
            member=self.patient_other,
            is_active=True
        )

        self.valid_jpeg = SimpleUploadedFile(
            name='valid.jpg',
            content=b'\xff\xd8\xff\xe0' + b'0' * 500,
            content_type='image/jpeg'
        )
        self.person = FamiliarPerson.objects.create(
            member=self.patient,
            name='Grandma Devi',
            relationship='Mother',
            photo=self.valid_jpeg,
            is_active=True
        )

    def test_patient_cannot_access_caregiver_management(self):
        self.client.login(username='patient_alpha', password='Password123!')
        res = self.client.get(reverse('memories:manage_familiar_people') + f'?member={self.patient.id}')
        # Should redirect to patient portal or deny
        self.assertNotEqual(res.status_code, 200)

    def test_caregiver_without_supervision_denied_access(self):
        self.client.login(username='cg_alpha', password='Password123!')
        # caregiver tries to view patient_other (supervised by cg_beta)
        res = self.client.get(reverse('memories:manage_familiar_people') + f'?member={self.patient_other.id}')
        self.assertEqual(res.status_code, 403)

    def test_authorized_caregiver_can_view_list(self):
        self.client.login(username='cg_alpha', password='Password123!')
        res = self.client.get(reverse('memories:manage_familiar_people') + f'?member={self.patient.id}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Grandma Devi')
        self.assertContains(res, 'Mother')

    def test_authorized_caregiver_can_add_person(self):
        self.client.login(username='cg_alpha', password='Password123!')
        photo = SimpleUploadedFile(
            name='new_person.jpg',
            content=b'\xff\xd8\xff\xe0' + b'0' * 500,
            content_type='image/jpeg'
        )
        res = self.client.post(
            reverse('memories:add_familiar_person') + f'?member={self.patient.id}',
            data={
                'name': 'Aarav',
                'relationship': 'Grandson',
                'photo': photo,
                'is_active': True,
            }
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(FamiliarPerson.objects.filter(member=self.patient, name='Aarav').exists())

    def test_authorized_caregiver_can_edit_person(self):
        self.client.login(username='cg_alpha', password='Password123!')
        res = self.client.post(
            reverse('memories:edit_familiar_person', kwargs={'person_id': self.person.id}) + f'?member={self.patient.id}',
            data={
                'name': 'Devi Sharma',
                'relationship': 'Mother',
                'is_active': True,
            }
        )
        self.assertEqual(res.status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.name, 'Devi Sharma')

    def test_authorized_caregiver_can_toggle_active(self):
        self.client.login(username='cg_alpha', password='Password123!')
        self.assertTrue(self.person.is_active)
        res = self.client.post(
            reverse('memories:toggle_familiar_person_active', kwargs={'person_id': self.person.id}) + f'?member={self.patient.id}'
        )
        self.assertEqual(res.status_code, 302)
        self.person.refresh_from_db()
        self.assertFalse(self.person.is_active)

    def test_authorized_caregiver_can_delete_person(self):
        self.client.login(username='cg_alpha', password='Password123!')
        res = self.client.post(
            reverse('memories:delete_familiar_person', kwargs={'person_id': self.person.id}) + f'?member={self.patient.id}'
        )
        self.assertEqual(res.status_code, 302)
        self.assertFalse(FamiliarPerson.objects.filter(id=self.person.id).exists())

    def test_cross_tenant_caregiver_cannot_modify_other_patient_person(self):
        # cg_alpha tries to edit/toggle/delete cg_beta's patient's person
        beta_jpeg = SimpleUploadedFile(
            name='beta.jpg',
            content=b'\xff\xd8\xff\xe0' + b'0' * 500,
            content_type='image/jpeg'
        )
        beta_person = FamiliarPerson.objects.create(
            member=self.patient_other,
            name='Uncle Joe',
            relationship='Uncle',
            photo=beta_jpeg
        )

        self.client.login(username='cg_alpha', password='Password123!')

        # Attempt edit
        res_edit = self.client.post(
            reverse('memories:edit_familiar_person', kwargs={'person_id': beta_person.id}) + f'?member={self.patient_other.id}',
            data={'name': 'Hacked', 'relationship': 'None', 'is_active': True}
        )
        self.assertEqual(res_edit.status_code, 403)

        # Attempt toggle
        res_toggle = self.client.post(
            reverse('memories:toggle_familiar_person_active', kwargs={'person_id': beta_person.id}) + f'?member={self.patient_other.id}'
        )
        self.assertEqual(res_toggle.status_code, 403)

        # Attempt delete
        res_del = self.client.post(
            reverse('memories:delete_familiar_person', kwargs={'person_id': beta_person.id}) + f'?member={self.patient_other.id}'
        )
        self.assertEqual(res_del.status_code, 403)


class MemoryViewTests(TestCase):
    """Tests for caregiver Memory CRUD views and patient reminiscence portal."""

    def setUp(self):
        self.client = Client()
        self.patient_1 = CustomUser.objects.create_user(
            username='patient_one',
            email='p1@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Ananya'
        )
        self.patient_2 = CustomUser.objects.create_user(
            username='patient_two',
            email='p2@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Rajesh'
        )
        self.caregiver_1 = CustomUser.objects.create_user(
            username='caregiver_one',
            email='c1@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.caregiver_2 = CustomUser.objects.create_user(
            username='caregiver_two',
            email='c2@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        # Link caregiver_1 -> patient_1
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver_1,
            member=self.patient_1,
            is_active=True
        )
        # Link caregiver_2 -> patient_2
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver_2,
            member=self.patient_2,
            is_active=True
        )
        # Create a memory for patient_1
        self.memory_1 = Memory.objects.create(
            member=self.patient_1,
            title='Bihu Celebration 2025',
            description='Enjoying pitha and dhol music with family.'
        )

    def test_anonymous_redirected_from_memories(self):
        res = self.client.get(reverse('memories:manage_memories'))
        self.assertEqual(res.status_code, 302)
        res_patient = self.client.get(reverse('memories:patient_memories'))
        self.assertEqual(res_patient.status_code, 302)

    def test_caregiver_can_view_supervised_member_memories(self):
        self.client.login(username='caregiver_one', password='Password123!')
        res = self.client.get(reverse('memories:manage_memories') + f'?member={self.patient_1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Bihu Celebration 2025')
        self.assertContains(res, 'Enjoying pitha and dhol music with family.')

    def test_caregiver_can_create_memory(self):
        self.client.login(username='caregiver_one', password='Password123!')
        res = self.client.post(
            reverse('memories:add_memory') + f'?member={self.patient_1.id}',
            data={
                'title': 'Tea Garden Stroll',
                'description': 'Walking near Dibrugarh tea estates.',
            }
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Memory.objects.filter(title='Tea Garden Stroll', member=self.patient_1).exists())

    def test_caregiver_can_edit_memory(self):
        self.client.login(username='caregiver_one', password='Password123!')
        res = self.client.post(
            reverse('memories:edit_memory', args=[self.memory_1.id]),
            data={
                'title': 'Bihu Celebration 2025 Updated',
                'description': 'Enjoying pitha with everyone.',
            }
        )
        self.assertEqual(res.status_code, 302)
        self.memory_1.refresh_from_db()
        self.assertEqual(self.memory_1.title, 'Bihu Celebration 2025 Updated')

    def test_caregiver_can_delete_memory(self):
        self.client.login(username='caregiver_one', password='Password123!')
        res = self.client.post(reverse('memories:delete_memory', args=[self.memory_1.id]))
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Memory.objects.filter(id=self.memory_1.id).exists())

    def test_cross_tenant_caregiver_blocked(self):
        # Caregiver 2 tries to edit/delete patient 1's memory
        self.client.login(username='caregiver_two', password='Password123!')
        res_edit = self.client.post(
            reverse('memories:edit_memory', args=[self.memory_1.id]),
            data={'title': 'Hacked Title', 'description': 'Hacked Desc'}
        )
        self.assertEqual(res_edit.status_code, 403)

        res_del = self.client.post(reverse('memories:delete_memory', args=[self.memory_1.id]))
        self.assertEqual(res_del.status_code, 403)

    def test_patient_can_view_own_memories(self):
        self.client.login(username='patient_one', password='Password123!')
        res = self.client.get(reverse('memories:patient_memories'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Bihu Celebration 2025')
        self.assertContains(res, 'Enjoying pitha and dhol music with family.')

    def test_patient_cannot_view_caregiver_manage_memories(self):
        self.client.login(username='patient_one', password='Password123!')
        res = self.client.get(reverse('memories:manage_memories'))
        self.assertEqual(res.status_code, 403)

    def test_memory_form_includes_speech_to_text_bindings(self):
        self.client.login(username='caregiver_one', password='Password123!')
        res = self.client.get(reverse('memories:add_memory') + f'?member={self.patient_1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-speech-target="id_title"')
        self.assertContains(res, 'data-speech-target="id_description"')
        self.assertContains(res, 'btn-speech')

    def test_familiar_person_form_includes_speech_to_text_bindings(self):
        self.client.login(username='caregiver_one', password='Password123!')
        res = self.client.get(reverse('memories:add_familiar_person') + f'?member={self.patient_1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-speech-target="id_name"')
        self.assertContains(res, 'data-speech-target="id_relationship"')
        self.assertContains(res, 'btn-speech')

    def test_user_created_content_preserved_in_assamese(self):
        self.client.post(reverse('set_language'), data={'language': 'as'}, follow=True)
        self.client.login(username='patient_one', password='Password123!')
        res = self.client.get(reverse('memories:patient_memories'))
        self.assertEqual(res.status_code, 200)
        # User content intact
        self.assertContains(res, 'Bihu Celebration 2025')
        self.assertContains(res, 'Enjoying pitha and dhol music with family.')
        # System text translated
        self.assertContains(res, 'মোৰ মৰমৰ স্মৃতিসমূহ')
