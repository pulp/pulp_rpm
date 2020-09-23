from django.db import migrations

def delete_orphan_subrepos(apps, schema):
    """
    Remove subrepos which don't belong to any variant or addon.
    """
    RpmRepository = apps.get_model("rpm", "RpmRepository")
    RpmRepository.objects.filter(addons=None,variants=None,sub_repo=True).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0024_change_subrepo_relation_properties'),
    ]

    operations = [
        migrations.RunPython(delete_orphan_subrepos)
    ]
