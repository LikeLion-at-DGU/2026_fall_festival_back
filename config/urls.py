"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
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
    path("api/admin/notices/", include("apps.notices.urls")),
    path("api/booths/", include("apps.booths.urls")),
    path("api/lanterns/", include("apps.lanterns.urls")),
]

# 개발 환경에서 업로드된 미디어 파일 제공
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
