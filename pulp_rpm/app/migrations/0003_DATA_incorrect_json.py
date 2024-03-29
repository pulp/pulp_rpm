# Generated by Django 2.2.10 on 2020-02-19 14:43


import json
import yaml

from django.db import migrations, transaction
import django.contrib.postgres.fields.jsonb


def unflatten_json(apps, schema_editor):
    # re: https://pulp.plan.io/issues/6191
    with transaction.atomic():
        Modulemd = apps.get_model("rpm", "Modulemd")
        for module in Modulemd.objects.all().only("artifacts", "dependencies", "_artifacts"):
            a = module._artifacts.first()
            snippet = a.file.read().decode()
            module_dict = yaml.safe_load(snippet)
            a.file.close()
            module.artifacts = json.loads(module.artifacts)
            module.dependencies = module_dict["data"]["dependencies"]
            module.save()

        ModulemdDefaults = apps.get_model("rpm", "ModulemdDefaults")
        for mod_defs in ModulemdDefaults.objects.all().only("profiles"):
            mod_defs.profiles = json.loads(mod_defs.profiles)
            mod_defs.save()


def replace_emptystring_with_null(apps, schema_editor):
    # An empty string can't be converted to JSON, so use a null instead
    with transaction.atomic():
        UpdateCollection = apps.get_model("rpm", "UpdateCollection")
        for coll in UpdateCollection.objects.all().only("module"):
            if coll.module == "":
                coll.module = "null"  # de-serializes to None,
                coll.save()


class Migration(migrations.Migration):

    dependencies = [
        ("rpm", "0002_updaterecord_reboot_suggested"),
    ]

    operations = [
        # Bugfixes
        migrations.RunPython(unflatten_json),
        # In-place migrate JSON stored in text field to a JSONField
        migrations.RunPython(replace_emptystring_with_null),
        migrations.AlterField(
            model_name="updatecollection",
            name="module",
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
    ]
