from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Students → Read only
    Staff → Edit ONLY if can_manage_content = True
    Superuser → Full access
    """

    def has_permission(self, request, view):

        # 1️⃣ Public read access
        if request.method in permissions.SAFE_METHODS:
            return True

        # 2️⃣ Must be authenticated for write actions
        if not request.user or not request.user.is_authenticated:
            return False

        # 3️⃣ Superusers → full control
        if request.user.is_superuser:
            return True

        # 4️⃣ Staff with content permission
        if request.user.is_staff:
            profile = getattr(request.user, "profile", None)
            return getattr(profile, "can_manage_content", False)

        return False


class IsSuperAdminOnly(permissions.BasePermission):
    """
    Strictly for system-level controls:
    - RBAC
    - Email dispatch
    - Media storage
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )

def get_user_profile(user):
    """
    Cached profile fetch to prevent repeated DB hits.
    """
    if not hasattr(user, "_cached_profile"):
        user._cached_profile, _ = UserProfile.objects.get_or_create(user=user)
    return user._cached_profile
    
class CanManageContent(permissions.BasePermission):
    """
    Allows only admins with content control.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if request.user.is_staff:
            profile = get_user_profile(request.user)
            return profile.can_manage_content

        return False


class CanApproveAdmissions(permissions.BasePermission):
    """
    Allows only admins who can approve students.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if request.user.is_staff:
            profile = get_user_profile(request.user)
            return profile.can_approve_admissions

        return False
        
class CanManageUsers(permissions.BasePermission):
    """
    Allows only admins who can manage users.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if request.user.is_staff:
            profile = get_user_profile(request.user)
            return profile.can_manage_users

        return False
        
        