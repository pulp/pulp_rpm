# Generated by Django 3.2.13 on 2022-07-15 08:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0040_rpmalternatecontentsource'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModulemdObsolete',
            fields=[
                ('content_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='rpm_modulemdobsolete', serialize=False, to='core.content')),
                ('modified', models.DateTimeField()),
                ('module_name', models.TextField()),
                ('module_stream', models.TextField()),
                ('message', models.TextField()),
                ('override_previous', models.BooleanField(null=True)),
                ('module_context', models.TextField(null=True)),
                ('eol_date', models.DateTimeField(null=True)),
                ('obsoleted_by_module_name', models.TextField(null=True)),
                ('obsoleted_by_module_stream', models.TextField(null=True)),
                ('snippet', models.TextField()),
            ],
            options={
                'default_related_name': '%(app_label)s_%(model_name)s',
                'unique_together': {('modified', 'module_name', 'module_stream')},
            },
            bases=('core.content',),
        ),
    ]
