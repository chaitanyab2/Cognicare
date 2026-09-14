from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from apps.accounts.models import Role


def role_required(allowed_roles):
    """
    Decorator for views that checks that the user is logged in and has
    one of the allowed roles, raising PermissionDenied (HTTP 403) if not.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return login_required(view_func)(request, *args, **kwargs)
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")
        return _wrapped_view
    return decorator


def patient_required(view_func):
    """View decorator requiring the Patient role."""
    return role_required([Role.PATIENT])(view_func)


def caregiver_required(view_func):
    """View decorator requiring the Caregiver role."""
    return role_required([Role.CAREGIVER])(view_func)


class RoleRequiredMixin(AccessMixin):
    """CBV Mixin to enforce required roles."""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            raise PermissionDenied("You do not have permission to access this page.")
        return super().dispatch(request, *args, **kwargs)


class PatientRequiredMixin(RoleRequiredMixin):
    """CBV Mixin requiring Patient role."""
    allowed_roles = [Role.PATIENT]


class CaregiverRequiredMixin(RoleRequiredMixin):
    """CBV Mixin requiring Caregiver role."""
    allowed_roles = [Role.CAREGIVER]
