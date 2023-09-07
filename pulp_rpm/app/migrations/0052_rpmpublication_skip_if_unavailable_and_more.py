# Generated by Django 4.2.4 on 2023-09-07 10:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rpm", "0051_alter_distributiontree_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="rpmpublication",
            name="skip_if_unavailable",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="rpmrepository",
            name="skip_if_unavailable",
            field=models.BooleanField(default=False),
        ),
    ]
