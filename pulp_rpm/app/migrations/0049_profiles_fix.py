from django.db import migrations
import yaml


def fixup_modulemd_profiles(apps, schema_editor):
    """ Set "profiles" for any saved post-3.19 back to the 3.18 format.
    """
    Modulemd = apps.get_model("rpm", "Modulemd")

    modules_to_update = []

    for mmd in Modulemd.objects.all().iterator():
        modulemd = yaml.safe_load(mmd.snippet)
        if modulemd:
            unprocessed_profiles = modulemd["data"].get("profiles", {})
            profiles = {}
            if unprocessed_profiles:
                for name, data in unprocessed_profiles.items():
                    rpms = data.get("rpms")
                    if rpms:
                        profiles[name] = rpms
                mmd.profiles = profiles
                modules_to_update.append(mmd)

            if len(modules_to_update) >= 100:
                Modulemd.objects.bulk_update(modules_to_update, ["profiles"])
                modules_to_update.clear()

    Modulemd.objects.bulk_update(modules_to_update, ["profiles"])


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0048_artifacts_dependencies_fix'),
    ]

    operations = [
        migrations.RunPython(fixup_modulemd_profiles),
    ]
