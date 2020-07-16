from django.db import migrations, models
import django.db.models.deletion


def make_distribution_tree_unique_per_repo(apps, schema_editor):
    """
    Ensure there is only one distribution tree per repo and set a repository_id of a repo it
    belongs to.
        - if a distribution tree belongs to one repo, just set repository_id
        - if a distribution tree belongs to multiple repos:
            - set repository_id for one repo
            - create a copy of distribution tree, assign it to the next repo, copy all RPMs to
              the next repo as well
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0015_repo_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='distributiontree',
            name='repository_id',
            field=models.UUIDField(default=None),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='addon',
            name='repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='addons', to='rpm.RpmRepository'),
        ),
        migrations.AlterField(
            model_name='variant',
            name='repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='rpm.RpmRepository'),
        ),
        migrations.RunPython(make_distribution_tree_unique_per_repo), 
        migrations.AlterUniqueTogether(
            name='distributiontree',
            unique_together={('repository_id', 'header_version', 'release_name', 'release_short', 'release_version', 'arch', 'build_timestamp')},
        ),
    ]
