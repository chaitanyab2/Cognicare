from django.urls import path
from apps.routines import views

app_name = 'routines'

urlpatterns = [
    # Caregiver Routine Management
    path('', views.manage_routines_view, name='manage_routines'),
    path('add/', views.add_routine_view, name='add_routine'),
    path('<int:routine_id>/edit/', views.edit_routine_view, name='edit_routine'),
    path('<int:routine_id>/delete/', views.delete_routine_view, name='delete_routine'),

    # Caregiver Routine Item Management
    path('<int:routine_id>/items/add/', views.add_routine_item_view, name='add_routine_item'),
    path('items/<int:item_id>/edit/', views.edit_routine_item_view, name='edit_routine_item'),
    path('items/<int:item_id>/delete/', views.delete_routine_item_view, name='delete_routine_item'),

    # Patient Routine Experience
    path('today/', views.patient_routine_view, name='patient_routine'),
    path('items/<int:item_id>/toggle/', views.patient_toggle_item_view, name='toggle_item'),
]
