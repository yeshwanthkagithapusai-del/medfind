from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search_medicines_view, name='search_medicines'),
    path('<int:pk>/', views.medicine_detail_view, name='medicine_detail'),
    path('manage/', views.manage_medicines_view, name='manage_medicines'),
    path('add/', views.add_medicine_view, name='add_medicine'),
    path('<int:pk>/edit/', views.edit_medicine_view, name='edit_medicine'),
]
