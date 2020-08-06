from django.db import (
    migrations,
    models,
)


def do_clone(apps, advisory, in_collection):
    # We're cloning collection - find its updatecollectionpackages
    uc_packages = in_collection.packages.all()
    # break the advisory/collection link
    in_collection.update_record.remove(advisory)
    # create a new copy of the collection and link it to the advisory
    new_collection = in_collection
    new_collection.pk = None
    new_collection.save()
    # need to have an id before we can build the m2m relation
    new_collection.update_record.add(advisory)
    new_collection.save()
    new_packages = []
    for a_package in uc_packages.iterator():
        # create copies of the package list and link to new collection
        a_package.pk = None
        a_package.update_collection = new_collection
        new_packages.append(a_package)
    UpdateCollectionPackage = apps.get_model("rpm", "UpdateCollectionPackage")
    UpdateCollectionPackage.objects.bulk_create(new_packages)


def clone_reused_update_collections(apps, schema):
    # Find UpdateCollections that point to multiple UpdateRecords
    # For all but the first one, create a clone
    UpdateCollection = apps.get_model("rpm", "UpdateCollection")
    collections = UpdateCollection.objects.annotate(
            num_advisories=models.Count('update_record')).filter(
                    num_advisories__gte=2).all().iterator()
    for collection in collections:
        # Look at all the advisories this collection is associated with
        advisories = collection.update_record.all()
        # Skip the first adviroy found; for any that remain, disconnect and clone
        for advisory in advisories[1:]:
            do_clone(apps, advisory, collection)

class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0016_dist_tree_nofk'),
    ]

    operations = [
        migrations.RunPython(clone_reused_update_collections),
    ]
