.. _settings:

Settings
========

pulp_rpm adds configuration options to the those offered by pulpcore.

ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   This setting controls whether or not pulp_rpm will block advisory sync or
   upload if it appears an 'incoming' advisory is incompatible with an existing
   advisory with the same name.

   This defaults to False, and advisory-merge will raise an ``AdvisoryConflict``
   exception in two scenarios:

   Situation 1
      Updated date and version are the same but pkglists differ (and one is not a subset
      or superset of the other).  E.g. It's likely a mistake in one of the pkglists.

   Situation 2
      Updated dates are different but pkglists have no intersection at all. E.g. It's
      either an attempt to combine content from incompatible repos (RHEL6-main and RHEL7
      debuginfo), or someone created a completely different advisory with already used id.


   If this setting is True, Pulp will merge the advisories in Situation 1, and simply
   accept the new advisory in Situation 2.

   If the setting is False, then the merge is rejected until the user has examined the
   conflicting advisories and addressed the problem.

   Addressing the problem manually could take a number of forms. Examples include
   (but are not limited to):

   * remove the existing advisory from the destination repository
   * choose not to sync from the offending remote
   * evaluate the command and choose not to combine conflicting repositories (e.g.
     RHEL6-main and RHEL7-debuginfo)

.. note::

    This approach to conflict-resolution is done **AT YOUR OWN RISK**.
    Pulp cannot guarantee the usability/usefulness of the resulting advisory.

