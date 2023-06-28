from django.db import migrations
import yaml


def fixup_modulemd_artifacts_dependencies(apps, schema_editor):
    """ Set "artifacts" and "dependencies" for any saved post-3.19 back to the 3.18 format.
    """
    Modulemd = apps.get_model("rpm", "Modulemd")

    modules_to_update = []

    for mmd in Modulemd.objects.all().iterator():
        modulemd = yaml.safe_load(mmd.snippet)
        if modulemd:
            mmd.artifacts = modulemd["data"].get("artifacts", {}).get("rpms", [])
            mmd.dependencies = modulemd["data"].get("dependencies", [])
            modules_to_update.append(mmd)
            if len(modules_to_update) >= 100:
                Modulemd.objects.bulk_update(modules_to_update, ["artifacts", "dependencies"])
                modules_to_update.clear()

    Modulemd.objects.bulk_update(modules_to_update, ["artifacts", "dependencies"])


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0047_modulemd_datefield'),
    ]

    operations = [
        migrations.RunPython(fixup_modulemd_artifacts_dependencies),
    ]
