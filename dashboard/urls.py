from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_dispatcher_view, name='dashboard'),
    path('customer/', views.customer_dashboard_view, name='customer_dashboard'),
    path('pharmacy/', views.pharmacy_dashboard_view, name='pharmacy_dashboard'),
    path('admin-portal/', views.admin_dashboard_view, name='admin_dashboard'),
]
