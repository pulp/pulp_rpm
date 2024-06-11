from gettext import gettext as _

from rest_framework import fields, serializers

from pulp_rpm.app.models import RpmRepository

from pulpcore.plugin.serializers import ValidateFieldsMixin
from pulpcore.plugin.util import get_domain


class PrunePackagesSerializer(serializers.Serializer, ValidateFieldsMixin):
    """
    Serializer for prune-old-Packages operation.
    """

    repo_hrefs = fields.ListField(
        required=True,
        help_text=_(
            "Will prune old packages from the specified list of repos. "
            "Use ['*'] to specify all repos. "
            "Will prune based on the specified repositories' latest_versions."
        ),
        child=serializers.CharField(),
    )

    keep_days = serializers.IntegerField(
        help_text=_(
            "Prune packages introduced *prior-to* this many days ago. "
            "Default is 14. A value of 0 implies 'keep latest package only.'"
        ),
        required=False,
        min_value=0,
        default=14,
    )

    dry_run = serializers.BooleanField(
        help_text=_(
            "Determine what would-be-pruned and log the list of packages. "
            "Intended as a debugging aid."
        ),
        default=False,
        required=False,
    )

    def validate_repo_hrefs(self, value):
        """
        Insure repo_hrefs is not empty and contains either valid RPM Repository hrefs or "*".
        Args:
            value (list): The list supplied by the user
        Returns:
            The list of RpmRepositories after validation
        Raises:
            ValidationError: If the list is empty or contains invalid hrefs.
        """
        if len(value) == 0:
            raise serializers.ValidationError("Must not be [].")

        # prune-all-repos is "*" - find all RPM repos in this domain
        if "*" in value:
            if len(value) != 1:
                raise serializers.ValidationError("Can't specify specific HREFs when using '*'")
            return RpmRepository.objects.filter(pulp_domain=get_domain())

        from pulpcore.plugin.viewsets import NamedModelViewSet

        # We're pruning a specific list of RPM repositories.
        # Validate that they are for RpmRepositories.
        hrefs_to_return = []
        for href in value:
            hrefs_to_return.append(NamedModelViewSet.get_resource(href, RpmRepository))

        return hrefs_to_return
