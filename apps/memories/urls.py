from django.urls import path
from apps.memories import views

app_name = 'memories'

urlpatterns = [
    path('people/', views.manage_familiar_people_view, name='manage_familiar_people'),
    path('people/add/', views.add_familiar_person_view, name='add_familiar_person'),
    path('people/<int:person_id>/edit/', views.edit_familiar_person_view, name='edit_familiar_person'),
    path('people/<int:person_id>/toggle/', views.toggle_familiar_person_active_view, name='toggle_familiar_person_active'),
    path('people/<int:person_id>/delete/', views.delete_familiar_person_view, name='delete_familiar_person'),
]
