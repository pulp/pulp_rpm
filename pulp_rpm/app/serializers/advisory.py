import copy
from gettext import gettext as _
import json

import createrepo_c
from django.db import IntegrityError
from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ModelSerializer,
    NoArtifactContentUploadSerializer,
)

from pulp_rpm.app.advisory import hash_update_record
from pulp_rpm.app.fields import (
    UpdateCollectionPackagesField,
    UpdateReferenceField,
)

from pulp_rpm.app.constants import (
    CR_UPDATE_REFERENCE_ATTRS,
    PULP_UPDATE_COLLECTION_ATTRS,
    PULP_UPDATE_RECORD_ATTRS,
    PULP_UPDATE_REFERENCE_ATTRS,
)

from pulp_rpm.app.models import (
    UpdateCollection,
    UpdateCollectionPackage,
    UpdateRecord,
    UpdateReference,
)


class UpdateCollectionSerializer(ModelSerializer):
    """
    A Serializer for UpdateCollection.
    """

    name = serializers.CharField(
        help_text=_("Collection name."), allow_blank=True, allow_null=True
    )

    shortname = serializers.CharField(
        help_text=_("Collection short name."), allow_blank=True, allow_null=True
    )

    module = serializers.JSONField(
        help_text=_("Collection modular NSVCA."), allow_null=True
    )

    packages = UpdateCollectionPackagesField(
        source="*", read_only=True, help_text=_("List of packages")
    )

    class Meta:
        fields = ("name", "shortname", "module", "packages")
        model = UpdateCollection


class UpdateRecordSerializer(NoArtifactContentUploadSerializer):
    """
    A Serializer for UpdateRecord.
    """

    id = serializers.CharField(
        help_text=_("Update id (short update name, e.g. RHEA-2013:1777)"),
        read_only=True,
    )
    updated_date = serializers.CharField(
        help_text=_("Date when the update was updated (e.g. '2013-12-02 00:00:00')"),
        read_only=True,
    )

    description = serializers.CharField(
        help_text=_("Update description"), allow_blank=True, read_only=True
    )
    issued_date = serializers.CharField(
        help_text=_("Date when the update was issued (e.g. '2013-12-02 00:00:00')"),
        read_only=True,
    )
    fromstr = serializers.CharField(
        help_text=_("Source of the update (e.g. security@redhat.com)"),
        allow_blank=True,
        read_only=True,
    )
    status = serializers.CharField(
        help_text=_("Update status ('final', ...)"), allow_blank=True, read_only=True
    )
    title = serializers.CharField(
        help_text=_("Update name"), allow_blank=True, read_only=True
    )
    summary = serializers.CharField(
        help_text=_("Short summary"), allow_blank=True, read_only=True
    )
    version = serializers.CharField(
        help_text=_("Update version (probably always an integer number)"),
        allow_blank=True,
        read_only=True,
    )

    type = serializers.CharField(
        help_text=_("Update type ('enhancement', 'bugfix', ...)"),
        allow_blank=True,
        read_only=True,
    )
    severity = serializers.CharField(
        help_text=_("Severity"), allow_blank=True, read_only=True
    )
    solution = serializers.CharField(
        help_text=_("Solution"), allow_blank=True, read_only=True
    )
    release = serializers.CharField(
        help_text=_("Update release"), allow_blank=True, read_only=True
    )
    rights = serializers.CharField(
        help_text=_("Copyrights"), allow_blank=True, read_only=True
    )
    pushcount = serializers.CharField(
        help_text=_("Push count"), allow_blank=True, read_only=True
    )
    reboot_suggested = serializers.BooleanField(
        help_text=_("Reboot suggested"), read_only=True
    )
    pkglist = UpdateCollectionSerializer(
        source="collections", read_only=True, many=True, help_text=_("List of packages")
    )
    references = UpdateReferenceField(
        source="pk", read_only=True, help_text=_("List of references")
    )

    def create(self, validated_data):
        """
        Create UpdateRecord and its subclasses from JSON file.

        Returns:
            UpdateRecord instance

        """
        references = validated_data.pop("references", [])
        pkglist = validated_data.pop("pkglist", [])
        update_collection_packages_to_save = list()
        update_references_to_save = list()
        try:
            update_record = super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError("Advisory already exists in Pulp.")

        for collection in pkglist:
            new_coll = copy.deepcopy(collection)
            packages = new_coll.pop("packages", [])
            new_coll[PULP_UPDATE_COLLECTION_ATTRS.SHORTNAME] = new_coll.pop("short", "")
            coll = UpdateCollection(**new_coll)
            coll.save()
            coll.update_record.add(update_record)
            for package in packages:
                pkg = UpdateCollectionPackage(**package)
                try:
                    pkg.sum_type = createrepo_c.checksum_type(pkg.sum_type)
                except TypeError:
                    raise TypeError(f'"{pkg.sum_type}" is not supported.')
                pkg.update_collection = coll
                update_collection_packages_to_save.append(pkg)
        for reference in references:
            new_ref = dict()
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.HREF] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.HREF, ""
            )
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.ID] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.ID, ""
            )
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.TITLE] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.TITLE, ""
            )
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.TYPE] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.TYPE, ""
            )
            ref = UpdateReference(**new_ref)
            ref.update_record = update_record
            update_references_to_save.append(ref)

        if update_collection_packages_to_save:
            UpdateCollectionPackage.objects.bulk_create(
                update_collection_packages_to_save
            )
        if update_references_to_save:
            UpdateReference.objects.bulk_create(update_references_to_save)

        cr_update_record = update_record.to_createrepo_c()
        update_record.digest = hash_update_record(cr_update_record)
        update_record.save()

        return update_record

    def validate(self, data):
        """
        Read a file for a JSON data and validate a UpdateRecord data.

        Also change few fields to match Pulp internals if exists as this is usually handle by
        createrepo_c which is not used here.
        """
        update_record_data = dict()
        if "file" in data:
            update_record_data.update(json.loads(data["file"].read()))
            update_record_data.update(data)
        else:
            raise serializers.ValidationError(
                "Only creation with file or artifact is allowed."
            )

        update_record_data[PULP_UPDATE_RECORD_ATTRS.FROMSTR] = update_record_data.pop(
            "from", update_record_data.get(PULP_UPDATE_RECORD_ATTRS.FROMSTR, "")
        )
        update_record_data[
            PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE
        ] = update_record_data.pop(
            "issued", update_record_data.get(PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE, "")
        )
        update_record_data[
            PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE
        ] = update_record_data.pop(
            "updated", update_record_data.get(PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE, "")
        )

        if (
            not update_record_data.get(PULP_UPDATE_RECORD_ATTRS.ID)
            or not update_record_data.get(PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE)
            or not update_record_data.get(PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE)
        ):
            raise serializers.ValidationError(
                "All '{}', '{}' and '{}' must be specified.".format(
                    PULP_UPDATE_RECORD_ATTRS.ID,
                    PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE,
                    PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE,
                )
            )

        validated_data = super().validate(update_record_data)
        return validated_data

    class Meta:
        fields = NoArtifactContentUploadSerializer.Meta.fields + (
            "id",
            "updated_date",
            "description",
            "issued_date",
            "fromstr",
            "status",
            "title",
            "summary",
            "version",
            "type",
            "severity",
            "solution",
            "release",
            "rights",
            "pushcount",
            "pkglist",
            "references",
            "reboot_suggested",
        )
        model = UpdateRecord


class MinimalUpdateRecordSerializer(UpdateRecordSerializer):
    """
    A minimal serializer for RPM update records.
    """

    class Meta:
        fields = NoArtifactContentUploadSerializer.Meta.fields + (
            "id",
            "title",
            "severity",
            "type",
        )
        model = UpdateRecord
