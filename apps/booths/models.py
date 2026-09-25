"""Booths database models."""

from django.db import models


class Booth(models.Model):
    class PlaceType(models.TextChoices):
        BOOTH = "BOOTH", "부스"
        FACILITY = "FACILITY", "시설"

    class Category(models.TextChoices):
        TOILET = "TOILET", "화장실"
        ALCOHOL = "ALCOHOL", "주점"
        COLLAB = "COLLAB", "협업"
        ECO = "ECO", "동빛에코"
        ETC = "ETC", "부스"

    class BoothSize(models.TextChoices):
        SMALL = "SMALL", "작은 천막"
        BIG = "BIG", "큰 천막"

    class RestroomType(models.TextChoices):
        MALE = "MALE", "남자 화장실"
        FEMALE = "FEMALE", "여자 화장실"
        BOTH = "BOTH", "남녀 화장실"

    name = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=100, null=True, blank=True)
    place_type = models.CharField(max_length=20, choices=PlaceType.choices)
    category = models.CharField(max_length=20, choices=Category.choices)
    restroom_type = models.CharField(
        max_length=10,
        choices=RestroomType.choices,
        null=True,
        blank=True,
    )
    booth_size = models.CharField(
        max_length=10,
        choices=BoothSize.choices,
        null=True,
        blank=True,
    )
    description = models.TextField(null=True, blank=True)
    zone = models.CharField(max_length=30, null=True, blank=True)
    location_detail = models.CharField(max_length=100, null=True, blank=True)

    # 3D 지도 배치 좌표
    map_x = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    map_y = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # 표고(m)
    map_elevation = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # 회전각(도)
    rotation = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # 카드/검색용 썸네일
    thumbnail_url = models.CharField(max_length=500, null=True, blank=True)
    # 상세 '이미지' 탭용
    image_url = models.CharField(max_length=500, null=True, blank=True)
    entrance_fee = models.PositiveIntegerField(null=True, blank=True)
    event_description = models.TextField(null=True, blank=True)
    instagram_id = models.CharField(max_length=50, null=True, blank=True)
    has_reusable_container = models.BooleanField(default=True)
    # 상세 '가는 길' 안내 문구
    directions = models.TextField(null=True, blank=True)

    # 표시용 캐시 컬럼. 증감은 등불 도메인이 같은 트랜잭션에서 처리 (여기서는 읽기만)
    lantern_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class BoothOperation(models.Model):
    class TimeSlot(models.TextChoices):
        DAY = "DAY", "주간"
        NIGHT = "NIGHT", "야간"

    booth = models.ForeignKey(Booth, on_delete=models.CASCADE, related_name="operations")
    festival_date = models.DateField()
    time_slot = models.CharField(max_length=10, choices=TimeSlot.choices)
    open_at = models.TimeField()
    close_at = models.TimeField()
    placements = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booth", "festival_date", "time_slot"],
                name="unique_booth_operation_slot",
            )
        ]

    def __str__(self):
        return f"{self.booth_id} {self.festival_date} {self.time_slot}"


class BoothMenu(models.Model):
    booth = models.ForeignKey(Booth, on_delete=models.CASCADE, related_name="menus")
    name = models.CharField(max_length=50)
    price = models.PositiveIntegerField()
    sort_order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.booth_id} {self.name}"
