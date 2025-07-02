from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cmd/<str:client_id>/', views.cmd_page, name='cmd_page'),
    path('generate-exe/', views.generate_exe, name='generate_exe'),
    path('download-device/', views.download_device, name='download_device'),
    path('', views.index, name='index'),
    path('cmd/<str:client_id>/', views.cmd_page, name='cmd_page'),
    path('generate-exe/', views.generate_exe, name='generate_exe'),
    path('download-device/', views.download_device, name='download_device'),  # تغییر نام به download_device
    path('api/register/', views.ClientRegisterView.as_view(), name='client_register'),
    path('api/command/<str:client_id>/', views.ClientCommandView.as_view(), name='client_command'),
    path('api/poll/<str:client_id>/', views.ClientPollView.as_view(), name='client_poll'),
    path('api/stream/<str:client_id>/<str:stream_type>/', views.StreamView.as_view(), name='stream'),
]