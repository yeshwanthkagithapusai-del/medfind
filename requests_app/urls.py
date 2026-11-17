from django.urls import path
from . import views

urlpatterns = [
    path('create/<int:pharmacy_id>/<int:medicine_id>/', views.create_request_view, name='create_request'),
    path('my-requests/', views.customer_requests_list_view, name='customer_requests'),
    path('pharmacy-inbox/', views.pharmacy_inbox_view, name='pharmacy_inbox'),
    path('<int:pk>/respond/', views.respond_request_view, name='respond_request'),
    path('<int:pk>/cancel/', views.cancel_request_view, name='cancel_request'),
]
