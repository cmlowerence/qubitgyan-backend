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
