from django.db import migrations


def change_subrepo_names(apps, schema_editor):
    RpmRepository = apps.get_model('rpm', 'RpmRepository')

    repos = list()
    for repo in RpmRepository.objects.filter(user_hidden=True).only("name").iterator():
        if repo.name.count("-") == 1:
            repo.name = "-".join(repo.name, str(repo.pk))
            repos.append(repo)

    RpmRepository.objects.bulk_update(repos, ["name"])


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0039_rpmalternatecontentsource'),
    ]

    operations = [
        migrations.RunPython(change_subrepo_names),
    ]
