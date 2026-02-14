from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """Students can read. Admins can edit ONLY IF they have the 'can_manage_content' flag."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Superusers can do everything
        if request.user and request.user.is_superuser:
            return True

        # Standard Admins need the specific content flag
        if request.user and request.user.is_staff:
            if hasattr(request.user, 'profile') and request.user.profile.can_manage_content:
                return True

        return False

class IsSuperAdminOnly(permissions.BasePermission):
    """Strictly for endpoints that control the app's core settings and permissions"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)