from django.db import migrations


def replace_empty_fingerprint_with_null(apps, schema_editor):
    RpmRepository = apps.get_model("rpm", "RpmRepository")
    RpmRepository.objects.filter(package_signing_fingerprint="").update(
        package_signing_fingerprint=None
    )


def replace_null_fingerprint_with_empty(apps, schema_editor):
    RpmRepository = apps.get_model("rpm", "RpmRepository")
    RpmRepository.objects.filter(package_signing_fingerprint=None).update(
        package_signing_fingerprint=""
    )


class Migration(migrations.Migration):

    dependencies = [
        ("rpm", "0068_alter_rpmpublication_compression_type_and_more"),
    ]

    operations = [
        migrations.RunPython(
            replace_empty_fingerprint_with_null,
            replace_null_fingerprint_with_empty,
        ),
    ]
