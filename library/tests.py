from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase


class UserPrivilegeSecurityTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='root',
            email='root@example.com',
            password='rootpass123'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
        )
        self.student = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='studentpass123',
            is_staff=False,
        )

    def test_standard_admin_cannot_create_superuser(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/v1/users/',
            {
                'username': 'evil-root',
                'email': 'evil-root@example.com',
                'password': 'strongpass123',
                'is_staff': False,
                'is_superuser': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(username='evil-root').exists())

    def test_standard_admin_cannot_promote_user_via_update(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/v1/users/{self.student.id}/',
            {'is_staff': True},
            format='json',
        )

        self.student.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.student.is_staff)

    def test_superuser_can_promote_user_via_update(self):
        self.client.force_authenticate(user=self.superuser)

        response = self.client.patch(
            f'/api/v1/users/{self.student.id}/',
            {'is_staff': True},
            format='json',
        )

        self.student.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.student.is_staff)


    def test_superuser_can_update_own_account(self):
        self.client.force_authenticate(user=self.superuser)

        response = self.client.patch(
            f'/api/v1/users/{self.superuser.id}/',
            {'first_name': 'RootUpdated'},
            format='json',
        )

        self.superuser.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.superuser.first_name, 'RootUpdated')

    def test_superuser_can_update_other_superuser(self):
        other_superuser = User.objects.create_superuser(
            username='root2',
            email='root2@example.com',
            password='rootpass123',
        )
        self.client.force_authenticate(user=self.superuser)

        response = self.client.patch(
            f'/api/v1/users/{other_superuser.id}/',
            {'last_name': 'AdminTwo'},
            format='json',
        )

        other_superuser.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_superuser.last_name, 'AdminTwo')
    def test_admin_without_manage_users_cannot_delete_student(self):
        from .models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        profile.can_manage_users = False
        profile.save()

        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'/api/v1/users/{self.student.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=self.student.id).exists())

    def test_admin_with_manage_users_can_delete_student(self):
        from .models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        profile.can_manage_users = True
        profile.save()

        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'/api/v1/users/{self.student.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.student.id).exists())

    def test_superadmin_update_permissions_affect_admin_immediately(self):
        """Superuser updates an admin's RBAC flag and it should take effect immediately."""
        from .models import UserProfile

        # ensure admin initially cannot manage users
        profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        profile.can_manage_users = False
        profile.save()

        # admin should NOT be able to delete a student now
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'/api/v1/users/{self.student.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=self.student.id).exists())

        # superuser enables the permission via RBAC endpoint
        self.client.force_authenticate(user=self.superuser)
        resp2 = self.client.patch(f'/api/v1/manager/rbac/{self.admin.id}/update_permissions/', {'permissions': {'can_manage_users': True}}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertIn('user', resp2.data)
        self.assertTrue(resp2.data['user'].get('can_manage_users') or resp2.data['user'].get('profile', {}).get('can_manage_users'))

        # reload profile from DB and ensure it's updated
        profile.refresh_from_db()
        self.assertTrue(profile.can_manage_users)

        # now admin should be able to delete the student
        self.client.force_authenticate(user=self.admin)
        resp3 = self.client.delete(f'/api/v1/users/{self.student.id}/')
        self.assertEqual(resp3.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.student.id).exists())


class GlobalSearchTests(APITestCase):
    def test_resource_url_uses_resource_node_id(self):
        admin = User.objects.create_user(
            username='admin2',
            email='admin2@example.com',
            password='adminpass123',
            is_staff=True,
        )

        from .models import KnowledgeNode, Resource

        node = KnowledgeNode.objects.create(name='Algebra', node_type='TOPIC')
        resource = Resource.objects.create(
            title='Algebra Basics PDF',
            resource_type='PDF',
            node=node,
            google_drive_id='1234567890123456789012345',
        )

        self.client.force_authenticate(user=admin)
        response = self.client.get('/api/v1/global-search/', {'q': 'Algebra'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resource_result = next(item for item in response.data if item['type'] == 'RESOURCE' and item['id'] == resource.id)
        self.assertEqual(resource_result['url'], f'/admin/tree/{node.id}')


class MediaUploadTests(APITestCase):
    def setUp(self):
        # endpoint is restricted to superusers in the viewset
        self.superuser = User.objects.create_superuser(username='rootm', email='rootm@example.com', password='rootpass')
        self.client.force_authenticate(user=self.superuser)

    def test_upload_requires_name_and_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        img = SimpleUploadedFile('x.png', b'pngcontent', content_type='image/png')

        # Missing name -> 400
        resp = self.client.post('/api/v1/manager/media/upload/', {'file': img}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Both 'file' and 'name' are required", str(resp.data))

        # Missing file -> 400
        resp2 = self.client.post('/api/v1/manager/media/upload/', {'name': 'x.png'}, format='multipart')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)


class UserProfileTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='root2',
            email='root2@example.com',
            password='rootpass123'
        )
        self.client.force_authenticate(user=self.superuser)

    def test_create_user_with_nested_profile_avatar(self):
        resp = self.client.post('/api/v1/users/', {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'strongpass123',
            'is_staff': False,
            'profile': {'avatar_url': 'https://example.com/a.png'}
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        from .models import UserProfile
        user = User.objects.get(username='newuser')
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.avatar_url, 'https://example.com/a.png')

    def test_update_user_with_nested_profile_avatar_and_clear(self):
        user = User.objects.create_user(username='upuser', email='u@example.com', password='pwd123')
        from .models import UserProfile
        UserProfile.objects.create(user=user, avatar_url='https://old.example/x.png')

        # update via nested profile
        resp = self.client.patch(f'/api/v1/users/{user.id}/', {
            'first_name': 'Updated',
            'profile': {'avatar_url': 'https://new.example/y.png'}
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.avatar_url, 'https://new.example/y.png')

        # clear avatar using empty string
        resp2 = self.client.patch(f'/api/v1/users/{user.id}/', {
            'profile': {'avatar_url': ''}
        }, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        profile.refresh_from_db()
        self.assertEqual(profile.avatar_url, '')

    def test_update_user_with_flat_avatar_field_fallback(self):
        user = User.objects.create_user(username='flatuser', email='flat@example.com', password='pwd123')
        from .models import UserProfile
        UserProfile.objects.create(user=user, avatar_url='https://old.flat/a.png')

        # legacy payload with top-level avatar_url should still work
        resp = self.client.patch(f'/api/v1/users/{user.id}/', {
            'avatar_url': 'https://flat.new/b.png'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.avatar_url, 'https://flat.new/b.png')


class KnowledgeNodeTreeFormatTests(APITestCase):
    def test_nodes_list_returns_deeply_nested_children_for_student_app(self):
        from .models import KnowledgeNode

        root = KnowledgeNode.objects.create(name='Math', node_type='DOMAIN', order=1)
        subject = KnowledgeNode.objects.create(name='Algebra', node_type='SUBJECT', parent=root, order=1)
        section = KnowledgeNode.objects.create(name='Linear Equations', node_type='SECTION', parent=subject, order=1)
        topic = KnowledgeNode.objects.create(name='Solving by elimination', node_type='TOPIC', parent=section, order=1)

        response = self.client.get('/api/v1/nodes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payload = response.data['results'] if isinstance(response.data, dict) else response.data

        self.assertGreaterEqual(len(payload), 1)
        root_item = next(item for item in payload if item['id'] == root.id)
        self.assertIn('children', root_item)

        subject_item = next(item for item in root_item['children'] if item['id'] == subject.id)
        self.assertIn('children', subject_item)

        section_item = next(item for item in subject_item['children'] if item['id'] == section.id)
        self.assertIn('children', section_item)

        topic_item = next(item for item in section_item['children'] if item['id'] == topic.id)
        self.assertEqual(topic_item['children'], [])


class PublicAdmissionEndpointSecurityTests(APITestCase):
    def test_public_admissions_disallow_get_and_patch(self):
        create_resp = self.client.post('/api/v1/public/admissions/', {
            'student_name': 'A Student',
            'email': 'student-public@example.com',
            'phone': '1234567890',
            'class_grade': '10',
            'learning_goal': 'Learn fast'
        }, format='json')
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)

        list_resp = self.client.get('/api/v1/public/admissions/')
        self.assertEqual(list_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        patch_resp = self.client.patch('/api/v1/public/admissions/1/', {'student_name': 'Hacked'}, format='json')
        self.assertEqual(patch_resp.status_code, status.HTTP_404_NOT_FOUND)


class ManagerEndpointRobustnessTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='rootmanager',
            email='rootmanager@example.com',
            password='rootpass123'
        )
        self.client.force_authenticate(user=self.superuser)

    def test_media_upload_returns_503_when_supabase_missing(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        img = SimpleUploadedFile('x.png', b'pngcontent', content_type='image/png')

        with patch('library.api.v1.manager.views.get_supabase_client', side_effect=ValueError('Supabase configuration missing.')):
            resp = self.client.post(
                '/api/v1/manager/media/upload/',
                {'file': img, 'name': 'x'},
                format='multipart'
            )

        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('Supabase configuration missing.', str(resp.data))

    def test_email_flush_reports_sent_and_failed_counts(self):
        from library.models import QueuedEmail
        from unittest.mock import patch

        first = QueuedEmail.objects.create(
            recipient_email='a@example.com',
            subject='s1',
            body='b1'
        )
        second = QueuedEmail.objects.create(
            recipient_email='b@example.com',
            subject='s2',
            body='b2'
        )

        def fake_send(email):
            return email.id == first.id

        with patch('library.api.v1.manager.views.send_queued_email', side_effect=fake_send):
            resp = self.client.post('/api/v1/manager/emails/flush/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['sent'], 1)
        self.assertEqual(resp.data['failed'], 1)
        self.assertIn('Attempted to send 2 emails', resp.data['status'])
