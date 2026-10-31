from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
]

