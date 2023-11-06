# Generated by Django 4.2.5 on 2023-11-07 03:51

from django.db import migrations, models
from django.db.models import F


def set_publication_checksum(apps, schema_editor):
    RpmPublication = apps.get_model("rpm", "RpmPublication")
    RpmPublication.objects.update(checksum_type=F("metadata_checksum_type"))


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0056_remove_rpmpublication_sqlite_metadata_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rpmpublication',
            name='checksum_type',
            field=models.TextField(choices=[('unknown', 'unknown'), ('md5', 'md5'), ('sha1', 'sha1'), ('sha1', 'sha1'), ('sha224', 'sha224'), ('sha256', 'sha256'), ('sha384', 'sha384'), ('sha512', 'sha512')], null=True),
        ),
        migrations.RunPython(set_publication_checksum),
        migrations.AlterField(
            model_name='rpmpublication',
            name='checksum_type',
            field=models.TextField(choices=[('unknown', 'unknown'), ('md5', 'md5'), ('sha1', 'sha1'), ('sha1', 'sha1'), ('sha224', 'sha224'), ('sha256', 'sha256'), ('sha384', 'sha384'), ('sha512', 'sha512')]),
        ),
        migrations.AddField(
            model_name='rpmrepository',
            name='checksum_type',
            field=models.TextField(choices=[('unknown', 'unknown'), ('md5', 'md5'), ('sha1', 'sha1'), ('sha1', 'sha1'), ('sha224', 'sha224'), ('sha256', 'sha256'), ('sha384', 'sha384'), ('sha512', 'sha512')], null=True),
        ),
    ]
