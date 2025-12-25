from django.urls import path, re_path
from . import views

urlpatterns = [
    #System pages
    path('', views.home, name='home'),
    path("login/", views.login_user, name='login_user'),
    path("logout/", views.logout_user, name='logout_user'),
    path('user_settings/', views.user_settings, name='user_settings'),
    path('404/<error_code>/', views.error, name='error'),

    #API
    path('api/user-info/', views.get_user_info, name='get_user_info'),
    re_path(r'^api/serve_static/(?P<filename>.+)$', views.serve_static, name='serve_static'),

    #WhatsApp
    path("wa_exists_one/", views.wa_exists, name="wa_exists_one"),
    path("whatsapp/", views.whatsapp, name="whatsapp"),
    path("/whatsapp/send_one/", views.send_one_whatsapp, name="send_one_whatsapp"),
]