"""분실물 관리자 API 라우팅."""

from django.urls import path

from .views import (
    AdminLostItemDetailView,
    AdminLostItemImageUploadView,
    AdminLostItemListView,
)


app_name = "admin_lost_items"

urlpatterns = [
    path("images/", AdminLostItemImageUploadView.as_view(), name="image-upload"),
    path("", AdminLostItemListView.as_view(), name="list"),
    path("<int:lost_item_id>/", AdminLostItemDetailView.as_view(), name="detail"),
]