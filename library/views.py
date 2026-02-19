import logging
from rest_framework import viewsets, filters, permissions, status, exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.db import transaction
from django.core.cache import cache

from .models import (
    KnowledgeNode,
    Resource,
    ProgramContext,
    StudentProgress,
    UserProfile
)

from .serializers import (
    KnowledgeNodeSerializer,
    ResourceSerializer,
    ProgramContextSerializer,
    UserSerializer,
    StudentProgressSerializer
)

from .permissions import IsAdminOrReadOnly


class ProgramContextViewSet(viewsets.ModelViewSet):
    queryset = ProgramContext.objects.all()
    serializer_class = ProgramContextSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None


class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all().order_by("order")
    serializer_class = ResourceSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "contexts__name", "node__name"]

    def get_queryset(self):
        queryset = Resource.objects.all()

        node_id = self.request.query_params.get("node")
        r_type = self.request.query_params.get("type")
        context_id = self.request.query_params.get("context")

        if node_id:
            queryset = queryset.filter(node_id=node_id)

        if r_type and r_type != "ALL":
            queryset = queryset.filter(resource_type=r_type)

        if context_id and context_id != "ALL":
            queryset = queryset.filter(contexts__id=context_id)

        return queryset.order_by("order")

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAdminUser])
    @transaction.atomic
    def reorder(self, request):
        ids = request.data.get("ids", [])

        if not ids:
            raise ValidationError("No resource IDs provided.")

        if len(ids) != len(set(ids)):
            raise ValidationError("Duplicate IDs detected.")

        resources = Resource.objects.filter(id__in=ids)

        if resources.count() != len(ids):
            raise ValidationError("Some resource IDs are invalid or missing.")

        id_positions = {rid: index for index, rid in enumerate(ids)}

        for resource in resources:
            resource.order = id_positions[resource.id]

        Resource.objects.bulk_update(resources, ["order"])

        return Response({"status": "order updated"}, status=status.HTTP_200_OK)


class KnowledgeNodeViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeNodeSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        return KnowledgeNode.objects.select_related(
            "parent"
        ).prefetch_related(
            "children",
            "resources"
        ).annotate(
            resource_count=Count("resources", distinct=True),
            items_count=Count("children", distinct=True),
        ).order_by("order", "name")

    def build_tree(self, nodes, depth):
        if depth == 0:
            return []

        data = []

        for node in nodes:
            serialized = KnowledgeNodeSerializer(
                node,
                context={"request": self.request}
            ).data

            children = node.children.all()

            serialized["children"] = self.build_tree(
                children,
                depth - 1 if depth > 0 else -1
            )

            data.append(serialized)

        return data

    def list(self, request, *args, **kwargs):
        depth_param = request.query_params.get("depth", "full")

        if depth_param == "full":
            depth = -1
        else:
            try:
                depth = int(depth_param)
            except ValueError:
                depth = 1

        cache_key = f"knowledge_tree_depth_{depth_param}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        root_nodes = self.get_queryset().filter(parent__isnull=True)

        tree_data = self.build_tree(root_nodes, depth)

        cache.set(cache_key, tree_data, timeout=300)

        return Response(tree_data)

    def invalidate_tree_cache(self):
        cache.clear()

    def perform_create(self, serializer):
        serializer.save()
        self.invalidate_tree_cache()

    def perform_update(self, serializer):
        serializer.save()
        self.invalidate_tree_cache()

    def perform_destroy(self, instance):
        instance.delete()
        self.invalidate_tree_cache()


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.select_related("profile").all().order_by("-date_joined")
        return User.objects.select_related("profile").filter(is_staff=False).order_by("-date_joined")

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        logger = logging.getLogger(__name__)

        try:
            UserProfile.objects.get_or_create(user=request.user)
        except Exception as e:
            logger.warning(f"Profile healing warning: {str(e)}")

        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    def perform_create(self, serializer):
        is_creating_admin = serializer.validated_data.get("is_staff", False)
        is_creating_superuser = serializer.validated_data.get("is_superuser", False)

        if (is_creating_admin or is_creating_superuser) and not self.request.user.is_superuser:
            raise exceptions.PermissionDenied(
                "Action Forbidden: Only Superusers can create Administrator accounts."
            )

        user = serializer.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.created_by = self.request.user
        profile.save()

    def perform_update(self, serializer):
        requesting_user = self.request.user
        instance = serializer.instance

        if not requesting_user.is_superuser and instance != requesting_user:
            profile, _ = UserProfile.objects.get_or_create(user=requesting_user)
            if not profile.can_manage_users:
                raise exceptions.PermissionDenied(
                    "Action Forbidden: You do not have permission to manage users."
                )

        requested_is_staff = serializer.validated_data.get("is_staff")
        requested_is_superuser = serializer.validated_data.get("is_superuser")

        if not requesting_user.is_superuser and (
            requested_is_staff is not None or requested_is_superuser is not None
        ):
            raise exceptions.PermissionDenied(
                "Action Forbidden: Only Superusers can change user privilege levels."
            )

        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.is_superuser:
            return Response(
                {"error": "Action Forbidden: Cannot delete the Superuser account."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not request.user.is_superuser:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            if not profile.can_manage_users:
                return Response(
                    {"error": "Action Forbidden: You do not have permission to manage users."},
                    status=status.HTTP_403_FORBIDDEN
                )

        if instance.is_staff and not request.user.is_superuser:
            return Response(
                {"error": "Action Forbidden: Only Superusers can delete Administrator accounts."},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().destroy(request, *args, **kwargs)


class StudentProgressViewSet(viewsets.ModelViewSet):
    serializer_class = StudentProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudentProgress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAdminUser])
    def all_admin_view(self, request):
        progress = StudentProgress.objects.all().select_related("user", "resource")

        data = []

        for p in progress:
            data.append({
                "id": p.id,
                "user_details": {
                    "username": p.user.username,
                    "email": p.user.email
                },
                "resource_details": {
                    "title": p.resource.title,
                    "resource_type": p.resource.resource_type
                },
                "is_completed": p.is_completed,
                "last_accessed": p.last_accessed
            })

        return Response(data)


class GlobalSearchView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        query = request.query_params.get("q", "")

        if len(query) < 2:
            return Response({"results": []})

        results = []

        nodes = KnowledgeNode.objects.filter(name__icontains=query)[:5]
        for n in nodes:
            results.append({
                "type": "NODE",
                "id": n.id,
                "title": n.name,
                "subtitle": f"Type: {n.node_type}",
                "url": f"/admin/tree/{n.id}"
            })

        resources = Resource.objects.filter(title__icontains=query)[:5]
        for r in resources:
            results.append({
                "type": "RESOURCE",
                "id": r.id,
                "title": r.title,
                "subtitle": f"File: {r.resource_type}",
                "url": f"/admin/tree/{r.node_id}"
            })

        users_qs = User.objects.filter(username__icontains=query)

        if not request.user.is_superuser:
            users_qs = users_qs.filter(is_staff=False)

        for u in users_qs[:5]:
            results.append({
                "type": "USER",
                "id": u.id,
                "title": u.username,
                "subtitle": u.email,
                "url": "/admin/users"
            })

        return Response(results)


class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        users_by_role = User.objects.aggregate(
            total_admins=Count("id", filter=Q(is_staff=True)),
            total_students=Count("id", filter=Q(is_staff=False)),
        )

        total_nodes = KnowledgeNode.objects.count()
        total_resources = Resource.objects.count()

        type_distribution = Resource.objects.values(
            "resource_type"
        ).annotate(count=Count("id"))

        top_subjects = KnowledgeNode.objects.filter(
            node_type="TOPIC"
        ).annotate(
            resource_count=Count("resources")
        ).order_by("-resource_count")[:5].values(
            "name",
            "resource_count"
        )

        recent_resources = Resource.objects.all().order_by("-created_at")[:5]
        recent_serialized = ResourceSerializer(recent_resources, many=True).data

        return Response({
            "counts": {
                "nodes": total_nodes,
                "admins": users_by_role["total_admins"],
                "students": users_by_role["total_students"],
                "resources": total_resources,
            },
            "charts": {
                "distribution": type_distribution,
                "top_subjects": top_subjects
            },
            "recent_activity": recent_serialized
        })