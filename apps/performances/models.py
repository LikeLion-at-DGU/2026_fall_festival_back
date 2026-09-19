"""Performances database models."""
"""공연 데이터베이스 모델."""

from django.db import models

from common.models import SoftDeleteModel


class Performance(SoftDeleteModel):
    """공연 한 건. STAGE 탭의 타임테이블 카드 하나에 대응한다."""

    performance_id = models.BigAutoField(primary_key=True)
    team_name = models.CharField(max_length=100)
    affiliation = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)

    # festival_date를 start_at에서 계산하지 않고 따로 두는 이유는, 자정을 넘겨
    # 끝나는 공연(23:30~00:30)도 "29일 공연"으로 묶여야 하기 때문이다.
    festival_date = models.DateField()
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    class Meta:
        db_table = "performance"
        ordering = ["start_at", "performance_id"]
        indexes = [
            # 조회는 항상 deleted_at IS NULL + 날짜 조건이 붙는다.
            models.Index(fields=["deleted_at", "festival_date", "start_at"]),
            models.Index(fields=["deleted_at", "start_at"]),
        ]

    def __str__(self):
        return f"[{self.performance_id}] {self.team_name}"


class Song(SoftDeleteModel):
    """셋리스트의 곡 한 줄. 공연 상세 화면에서 순서대로 나열된다."""

    song_id = models.BigAutoField(primary_key=True)
    performance = models.ForeignKey(Performance, on_delete=models.CASCADE, related_name="songs")
    title = models.CharField(max_length=200)
    # 아티스트는 없을 수 있다. 프론트는 null이면 곡 제목만 표시한다.
    artist = models.CharField(max_length=100, null=True, blank=True)
    sort_order = models.PositiveIntegerField()

    class Meta:
        db_table = "song"
        ordering = ["sort_order", "song_id"]
        indexes = [models.Index(fields=["performance", "deleted_at", "sort_order"])]

    def __str__(self):
        return self.title