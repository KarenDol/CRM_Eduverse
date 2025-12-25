from django.urls import path, re_path
from . import views

urlpatterns = [
    #System pages
    path('', views.home, name='home'),
    path("login/<prev_page>", views.login_user, name='login_user'),
    path("logout/<prev_page>", views.logout_user, name='logout_user'),
    path('user_settings/', views.user_settings, name='user_settings'),
    path('404/<prev_page>/<error_code>/', views.error, name='error'),

    #API
    path('api/user-info/', views.get_user_info, name='get_user_info'),
    re_path(r'^api/serve_static/(?P<filename>.+)$', views.serve_static, name='serve_static'),

    #WhatsApp
    path("wa_exists/<phone>/", views.wa_exists, name='wa_exists'),
    path("whatsapp/", views.whatsapp, name="whatsapp"),
]