# Generated by Django 2.2.16 on 2020-10-09 15:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0025_remove_orphaned_subrepos'),
    ]

    operations = [
        migrations.AddField(
            model_name='rpmpublication',
            name='gpgcheck',
            field=models.IntegerField(choices=[(0, 0), (1, 1)], default=0),
        ),
        migrations.AddField(
            model_name='rpmpublication',
            name='repo_gpgcheck',
            field=models.IntegerField(choices=[(0, 0), (1, 1)], default=0),
        ),
    ]
