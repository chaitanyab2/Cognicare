from django.urls import path
from apps.accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('signup/patient/', views.PatientSignupView.as_view(), name='patient_signup'),
    path('signup/caregiver/', views.CaregiverSignupView.as_view(), name='caregiver_signup'),
    path('redirect/', views.login_redirect_view, name='login_redirect'),
    path('portal/patient/', views.patient_portal_view, name='patient_portal'),
    path('portal/caregiver/', views.caregiver_portal_view, name='caregiver_portal'),
]
