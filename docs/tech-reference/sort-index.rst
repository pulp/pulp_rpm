============
Sort Indexes
============

Overview
========

Version numbers for RPMs and SRPMs aren't sortable by normal string comparisons. Take the following
example:

* 3.1
* 3.9
* 3.10 *(read: three point ten)*
* 3.11 *(read: three point eleven)*

The above versions are sorted from oldest to newest. However, when sorting according to string
sorting rules, the order is determined to be:

* 3.1
* 3.10
* 3.11
* 3.9

The rules become more complex when letters are added to the version string. More information
on sorting RPM versions can be found
`on the Fedora wiki <http://fedoraproject.org/wiki/Archive:Tools/RPM/VersionComparison>`_ and
the `rpmvercmp source <http://rpm.org/api/4.4.2.2/rpmvercmp_8c-source.html>`_.


Pulp
====

This behavior affects both sorting RPMs as well as querying for RPMs relative to a specific
version (i.e. "RPMs newer than version 3.9"). It applies to both the ``version`` and ``release``
attributes on an RPM.

To work around this issue, two extra attributes are added to the RPM's metadata that is stored
in Pulp's database: ``version_sort_index`` and ``release_sort_index``. When sorting or querying against
either an RPM's version or release, the query should be done against the sort index attributes
instead.


Calculation
-----------

In order to use simple string sorting in the database, the original values for version and
release are encoded for their sort index values. The encoding algorithm is as follows:

* Each version is split apart by periods. We'll refer to each piece as a segment.
* If a segment only consists of numbers, it's transformed into the format ``dd-num``, where:

  * **dd**  - number of digits in the value, including leading zeroes if necessary
  * **num** - value of the int being encoded

* If a segment contains one or more letters, it is:

 * Split into multiple segments of continuous letters or numbers. For example, 12a3bc becomes
   12.a.3.bc
 * All of these number-only subsegments is encoded according to the rules above.
 * All letter subsegments are prefixed with a dollar sign ($).
 * Any non-alphanumeric characters are discarded.

Examples:

* ``3.9    -> 01-3.01-9``
* ``3.10   -> 01-3.02-10``
* ``5.256  -> 01-5.03-256``
* ``1.1a   -> 01-1.01-1.$a``
* ``1.a+   -> 01-1.$a``
* ``12a3bc -> 02-12.$a.01-3.$bc``
* ``2xFg33.+f.5 -> 01-2.$xFg.02-33.$f.01-5``

