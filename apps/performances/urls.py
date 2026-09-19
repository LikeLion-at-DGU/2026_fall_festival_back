"""공연 API 라우팅."""

from django.urls import path

from .views import PerformanceDetailView, PerformanceListView, PerformanceNowView

app_name = "performances"

urlpatterns = [
    path("", PerformanceListView.as_view(), name="list"),
    path("now/", PerformanceNowView.as_view(), name="now"),
    path("<int:performance_id>/", PerformanceDetailView.as_view(), name="detail"),
]