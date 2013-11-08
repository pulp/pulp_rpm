FAQ
===

Why is a checksum used to calculate uniqueness of RPMs?
-------------------------------------------------------

Pulp only stores one copy of each unique unit, no matter how many repositories
that unit is associated with. Name-epoch-version-release-arch is not enough for
us to guarantee that two RPMs are in fact the same. For example, they may be
signed with different keys. Using the checksum to verify uniqueness is the best
way for Pulp to accomplish this.

It may not make sense to have two RPMs with the same NEVRA in the same
repository, but there might be a use case. As a rule, Pulp intentionally does
very little to enforce what makes a repository "valid". Pulp gives you the
tools to manage collections of content, and you get to decide what constitutes
a valid collection for your use case.
