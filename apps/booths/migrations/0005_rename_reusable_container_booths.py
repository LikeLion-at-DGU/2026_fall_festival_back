from django.db import migrations


def rename_reusable_container_booths(apps, schema_editor):
    Booth = apps.get_model("booths", "Booth")

    Booth.objects.filter(
        name="다회용기 부스",
        zone="혜화관",
        deleted_at__isnull=True,
    ).update(name="다회용기 부스 (혜화관)")

    Booth.objects.filter(
        name="다회용기 부스",
        zone="팔정도",
        deleted_at__isnull=True,
    ).update(name="다회용기 부스 (팔정도)")


def restore_reusable_container_booth_names(apps, schema_editor):
    Booth = apps.get_model("booths", "Booth")

    Booth.objects.filter(
        name="다회용기 부스 (혜화관)",
        zone="혜화관",
        deleted_at__isnull=True,
    ).update(name="다회용기 부스")

    Booth.objects.filter(
        name="다회용기 부스 (팔정도)",
        zone="팔정도",
        deleted_at__isnull=True,
    ).update(name="다회용기 부스")


class Migration(migrations.Migration):
    dependencies = [
        ("booths", "0004_booth_restroom_type"),
    ]

    operations = [
        migrations.RunPython(
            rename_reusable_container_booths,
            restore_reusable_container_booth_names,
        ),
    ]