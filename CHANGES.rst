=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/en/3.0/nightly/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

3.0.0b4 (2019-07-03)
====================


Features
--------

- Add total counts to the sync progress report.
  `#4503 <https://pulp.plan.io/issues/4503>`_
- Greatly speed up publishing of a repository.
  `#4591 <https://pulp.plan.io/issues/4591>`_
- Add ability to copy content between repositories, content type(s) can be specified.
  `#4716 <https://pulp.plan.io/issues/4716>`_
- Renamed Errata/Update content to Advisory to better match the terminology of the RPM/DNF ecosystem.
  `#4902 <https://pulp.plan.io/issues/4902>`_
- Python bindings are now published nightly and with each release as
  `pulp-rpm-client <https://pypi.org/project/pulp-rpm-client/>`_. Also Ruby bindings are published
  similarly to rubygems.org as `pulp_rpm_client <https://rubygems.org/gems/pulp_rpm_client>`_.
  `#4960 <https://pulp.plan.io/issues/4960>`_
- Override the Remote's serializer to allow policy='on_demand' and policy='streamed'.
  `#5065 <https://pulp.plan.io/issues/5065>`_


Bugfixes
--------

- Require relative_path at the content unit creation time.
  `#4835 <https://pulp.plan.io/issues/4835>`_
- Fix migraitons failure by making models compatible with MariaDB.
  `#4909 <https://pulp.plan.io/issues/4909>`_
- Fix unique index length issue for MariaDB.
  `#4916 <https://pulp.plan.io/issues/4916>`_


Improved Documentation
----------------------

- Switch to using `towncrier <https://github.com/hawkowl/towncrier>`_ for better release notes.
  `#4875 <https://pulp.plan.io/issues/4875>`_
- Add a docs page about the Python and Ruby bindings.
  `#4960 <https://pulp.plan.io/issues/4960>`_


Misc
----

- `#4117 <https://pulp.plan.io/issues/4117>`_, `#4567 <https://pulp.plan.io/issues/4567>`_, `#4574 <https://pulp.plan.io/issues/4574>`_, `#5064 <https://pulp.plan.io/issues/5064>`_


----


