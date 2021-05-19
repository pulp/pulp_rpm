from django.db import migrations, transaction
from django.core.exceptions import ObjectDoesNotExist

def remove_publications_from_auto_distributed(apps, schema_editor):
    with transaction.atomic():
        RpmDistribution = apps.get_model("rpm", "RpmDistribution")
        distributions = RpmDistribution.objects.filter(repository__isnull=False, publication__isnull=False)
        distributions.update(publication=None)

def add_publications_to_auto_distributed(apps, schema_editor):
    with transaction.atomic():
        RpmDistribution = apps.get_model("rpm", "RpmDistribution")
        distributions = list(RpmDistribution.objects.filter(repository__isnull=False).select_related("repository"))
        for distribution in distributions:
            repo_version = distribution.repository.latest_version()
            try:
                publication = repo_version.publication_set.earliest("pulp_created")
            except ObjectDoesNotExist:
                publication = None
            distribution.publication = publication
        RpmDistribution.objects.bulk_update(distributions, ['publication'])


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0034_auto_publish'),
    ]

    operations = [
        migrations.RunPython(
            remove_publications_from_auto_distributed,
            reverse_code=add_publications_to_auto_distributed
        )
    ]
