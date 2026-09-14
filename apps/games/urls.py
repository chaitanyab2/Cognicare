"""
URL configuration for the Cognicare Games application.
Phase 5: Gameplay Foundation + Memory Market.
"""

from django.urls import path
from apps.games import views

app_name = 'games'

urlpatterns = [
    path('', views.game_list_view, name='list'),
    path('<slug:slug>/', views.game_detail_view, name='detail'),
    path('<slug:slug>/start/', views.start_session_view, name='start_session'),
    path('session/<int:session_id>/', views.gameplay_view, name='play'),
    path('session/<int:session_id>/round/', views.submit_round_view, name='submit_round'),
    path('session/<int:session_id>/complete/', views.complete_session_view, name='complete_session'),
    path('session/<int:session_id>/results/', views.game_results_view, name='results'),
]
