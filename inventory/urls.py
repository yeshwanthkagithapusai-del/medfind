from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_list_view, name='inventory_list'),
    path('add/', views.inventory_add_view, name='inventory_add'),
    path('<int:pk>/edit/', views.inventory_edit_view, name='inventory_edit'),
    path('<int:pk>/delete/', views.inventory_delete_view, name='inventory_delete'),
]
