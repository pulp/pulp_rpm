Contributing
============

To contribute to the ``pulp_rpm`` package follow this process:

1. Clone the GitHub repo
2. Make a change
3. Add a functional test when you fix a bug or introduce a feature
4. Make sure all tests passed
5. Add a file into CHANGES folder (Changelog update).
6. If your PR introduces a new feature or updates the existing one, update coverage.md
7. Commit changes to your own ``pulp_rpm`` clone
8. Make pull request from github page for your clone against master branch


.. _changelog-update:

Changelog update
****************

The CHANGES.rst file is managed using the `towncrier tool <https://github.com/hawkowl/towncrier>`_
and all non trivial changes must be accompanied by a news entry.

To add an entry to the news file, you first need an issue on github describing the change you
want to make. Once you have an issue, take its number and create a file inside of the ``CHANGES/``
directory named after that issue number with an extension of .feature, .bugfix, .doc, .removal, or
.misc. So if your issue is 3543 and it fixes a bug, you would create the file
``CHANGES/3543.bugfix``.

PRs can span multiple categories by creating multiple files (for instance, if you added a feature
and deprecated an old feature at the same time, you would create CHANGES/NNNN.feature and
CHANGES/NNNN.removal). Likewise if a PR touches multiple issues/PRs you may create a file for each
of them with the exact same contents and Towncrier will deduplicate them.

The contents of this file are reStructuredText formatted text that will be used as the content of
the news file entry. You do not need to reference the issue or PR numbers here as towncrier will
automatically add a reference to all of the affected issues when rendering the news file.


.. _coverage-update:

Coverage update
***************

The coverage.md file contains a table that keeps track of how well features are backed by functional
tests. If you are adding a new feature or updating an existing one, specify in this table whether
it has any coverage, partial of full coverage.
Every update to this table should be accompanied with a functional test.
