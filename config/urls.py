"""Root URL configuration."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/coupons/", include("apps.coupons.urls")),
    path("api/lost-items/", include("apps.lost_items.public_urls")),
    path("api/admin/lost-items/", include("apps.lost_items.urls")),
    path("api/notices/", include("apps.notices.urls")),
    path("api/booths/", include("apps.booths.urls")),
    path("api/lanterns/", include("apps.lanterns.urls")),
    path("api/performances/", include("apps.performances.urls")),
    path("api/admin/lanterns/", include("apps.lanterns.admin_urls")),
]
