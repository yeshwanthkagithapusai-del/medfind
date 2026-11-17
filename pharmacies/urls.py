from django.urls import path
from . import views

urlpatterns = [
    path('', views.pharmacy_discovery_view, name='pharmacy_discovery'),
    path('<int:pk>/', views.pharmacy_detail_view, name='pharmacy_detail'),
    path('profile/edit/', views.edit_pharmacy_profile_view, name='edit_pharmacy_profile'),
    path('manage/list/', views.admin_pharmacy_list_view, name='admin_pharmacy_list'),
    path('manage/<int:pk>/toggle-approval/', views.toggle_pharmacy_approval_view, name='toggle_pharmacy_approval'),
    path('manage/users/', views.admin_user_list_view, name='admin_user_list'),
    path('manage/requests/', views.admin_request_monitor_view, name='admin_request_monitor'),
]
