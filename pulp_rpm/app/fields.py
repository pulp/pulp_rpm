from rest_framework import serializers
from pulp_rpm.app.models import UpdateCollection, UpdateReference


class UpdateCollectionField(serializers.ListField):
    """
    A serializer field for the 'UpdateCollectionPackage' model.
    """

    def to_representation(self, value):
        """
        Get list of packages from UpdateCollections for UpdateRecord if any.

        Args:
            value ('pk' of `UpdateRecord` instance): UUID of UpdateRecord instance

        Returns:
            A list of dictionaries representing packages inside the collections of UpdateRecord

        """
        ret = []
        collections = UpdateCollection.objects.filter(update_record=value)
        for collection in collections:
            coll_base = {"name": collection.name, "shortname": collection.shortname, "packages": []}
            for pkg in collection.packages.values():
                coll_base["packages"].append(
                    {
                        "arch": pkg["arch"],
                        "epoch": pkg["epoch"],
                        "filename": pkg["filename"],
                        "name": pkg["name"],
                        "reboot_suggested": pkg["reboot_suggested"],
                        "release": pkg["release"],
                        "src": pkg["src"],
                        "sum": pkg["sum"],
                        "sum_type": pkg["sum_type"],
                        "version": pkg["version"],
                    }
                )
            ret.append(coll_base)
        return ret


class UpdateReferenceField(serializers.ListField):
    """
    A serializer field for the 'UpdateReference' model.
    """

    def to_representation(self, value):
        """
        Get list of references from UpdateReferences for UpdateRecord if any.

        Args:
            value ('pk' of `UpdateRecord` instance): UUID of UpdateRecord instance

        Returns:
            A list of dictionaries representing references inside the collections of UpdateRecord

        """
        ret = []
        references = UpdateReference.objects.filter(update_record=value)
        for reference in references:
            ret.append(
                {
                    "href": reference.href,
                    "id": reference.ref_id,
                    "title": reference.title,
                    "type": reference.ref_type,
                }
            )
        return ret
