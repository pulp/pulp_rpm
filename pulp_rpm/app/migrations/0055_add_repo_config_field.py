# Generated by Django 4.2.4 on 2023-09-08 14:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rpm", "0054_remove_gpg_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="rpmpublication",
            name="repo_config",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="rpmrepository",
            name="repo_config",
            field=models.JSONField(default=dict),
        ),
    ]
