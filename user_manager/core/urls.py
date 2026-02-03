from django.urls import path, re_path
from . import views, bestys_api

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

    #BESTYS API
    path('api/competitions/get/', bestys_api.get_competitions, name='get_competitions'),
    path('api/competitions/results/<int:competition_id>', bestys_api.get_results, name='get_results'),

    #WhatsApp
    path("wa_exists_one/", views.wa_exists, name="wa_exists"),
    path("whatsapp/", views.whatsapp, name="whatsapp"),
    path("whatsapp/send_one/", views.send_one_whatsapp, name="send_one_whatsapp"),

    #Products
    path("products", views.products, name="products"),
    path("products/select", views.select_product, name="select_product"),
    path("products/add", views.add_product, name="add_product"),
    path("products/search", views.search_products, name="search_products"),
    path("products/delete/<product_id>", views.delete_product, name="delete_product"),
    path("products/edit/<product_id>", views.edit_product, name="edit_product"),
    # path("product/clients/get/<product_id>"), views.get_clients, name="get_clients"),
    path("product/clients/add", views.add_clients, name="add_clients"),

    #Clients
    path("client/<client_id>", views.client_card, name="client_card"),
    path("clients/get_numbers", views.get_numbers, name="get_numbers"),
]