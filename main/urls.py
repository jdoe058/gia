from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('test/start/', views.start_test_view, name='start_test'),
    path('test/<int:session_id>/', views.test_view, name='test'),
    path('test/<int:session_id>/answer/', views.answer_view, name='answer'),
    path('test/<int:session_id>/result/', views.result_view, name='test_result'),
]

