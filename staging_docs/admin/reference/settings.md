# Settings

pulp_rpm adds configuration options to the those offered by pulpcore.

## KEEP_CHANGELOG_LIMIT

This setting controls how many changelog entries (from the most recent ones) should
be kept for each RPM package synced or uploaded into Pulp. The limit is enacted to
avoid metadata bloat, as it can \_significantly\_ reduce the amount of space needed
to store metadata, the amount of bandwidth needed to download it, and the amount of
time needed to create it.

The changelog metadata is used for the `dnf changelog` command, which can display the
changelogs of a package even if it is not installed on the system. This setting
therefore controls the maximum number of changelogs that can be viewed on clients
using Pulp-hosted repositories using this command. Note, however, that for installed
packages the `rpm -qa --changelog` command can show all available changelogs for that
package without limitation.

10 was selected as the default because it is a good compromise between utility and
efficiency - and because it is the value used by Fedora, CentOS, OpenSUSE, and others.

## ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION

This setting controls whether or not pulp_rpm will block advisory sync or
upload if it appears an 'incoming' advisory is incompatible with an existing
advisory with the same name.

This defaults to False, and advisory-merge will raise an `AdvisoryConflict`
exception in two scenarios:

- Situation 1
  
    Updated date and version are the same but pkglists differ (and one is not a subset
    or superset of the other).  E.g. It's likely a mistake in one of the pkglists.

- Situation 2

    Updated dates are different but pkglists have no intersection at all. E.g. It's
    either an attempt to combine content from incompatible repos (RHEL6-main and RHEL7
    debuginfo), or someone created a completely different advisory with already used id.

If this setting is True, Pulp will merge the advisories in Situation 1, and simply
accept the new advisory in Situation 2.

If the setting is False, then the merge is rejected until the user has examined the
conflicting advisories and addressed the problem.

Addressing the problem manually could take a number of forms. Examples include
(but are not limited to):

- remove the existing advisory from the destination repository
- choose not to sync from the offending remote
- evaluate the command and choose not to combine conflicting repositories (e.g. RHEL6-main and RHEL7-debuginfo)

!!! note
    This approach to conflict-resolution is done **AT YOUR OWN RISK**.
    Pulp cannot guarantee the usability/usefulness of the resulting advisory.


## RPM_METADATA_USE_REPO_PACKAGE_TIME

When publishing RPM metadata, if this is true, Pulp will use the timestamp that the package was
added to the repo rather than the timestamp that the package first appeared in Pulp. This timestamp
appears in the "file" field of the time element for each package in primary.xml. Defaults to
`False`.
