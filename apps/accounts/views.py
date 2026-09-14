from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.generic import CreateView, View

from apps.accounts.decorators import patient_required, caregiver_required
from apps.accounts.forms import PatientRegistrationForm, CaregiverRegistrationForm, LoginForm
from apps.accounts.models import Role
from apps.accounts.services import get_caregiver_dashboard_data


class CustomLoginView(DjangoLoginView):
    """
    Standard authentication login view with role-based redirection.
    """
    form_class = LoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_to = self.request.GET.get('next') or self.request.POST.get('next')
        if redirect_to and url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure()
        ):
            return redirect_to

        # Role-based redirection
        user = self.request.user
        if user.is_authenticated:
            if user.role == Role.PATIENT:
                return reverse_lazy('accounts:patient_portal')
            elif user.role == Role.CAREGIVER:
                return reverse_lazy('accounts:caregiver_portal')

        return reverse_lazy('accounts:login')


class PatientSignupView(CreateView):
    """Registration view for Patients."""
    form_class = PatientRegistrationForm
    template_name = 'accounts/patient_signup.html'
    success_url = reverse_lazy('accounts:patient_portal')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, _("Patient account created successfully."))
        return redirect(self.success_url)


class CaregiverSignupView(CreateView):
    """Registration view for Caregivers."""
    form_class = CaregiverRegistrationForm
    template_name = 'accounts/caregiver_signup.html'
    success_url = reverse_lazy('accounts:caregiver_portal')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, _("Caregiver account created successfully."))
        return redirect(self.success_url)


class CustomLogoutView(View):
    """Standard logout view redirecting to login."""
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.info(request, _("You have been logged out."))
        return redirect('accounts:login')

    def post(self, request, *args, **kwargs):
        logout(request)
        messages.info(request, _("You have been logged out."))
        return redirect('accounts:login')


@login_required
def login_redirect_view(request):
    """Dispatches logged-in users to their role portal."""
    if request.user.role == Role.PATIENT:
        return redirect('accounts:patient_portal')
    elif request.user.role == Role.CAREGIVER:
        return redirect('accounts:caregiver_portal')
    return redirect('accounts:login')


# Verification stubs for role-based access protection (Phase 2 foundation)
@patient_required
def patient_portal_view(request):
    """Role-guarded endpoint for Patients."""
    return render(request, 'accounts/patient_portal.html', {'user': request.user})


@caregiver_required
def caregiver_portal_view(request):
    """
    Role-guarded endpoint for Caregivers.
    Provides real cognitive gameplay telemetry, KPI summaries, game breakdown,
    routine adherence, and accuracy trends for supervised patients.
    """
    member_id = request.GET.get('member')
    dashboard_data = get_caregiver_dashboard_data(caregiver=request.user, member_id=member_id)

    context = {
        'user': request.user,
        'dashboard': dashboard_data,
    }
    return render(request, 'accounts/caregiver_portal.html', context)

