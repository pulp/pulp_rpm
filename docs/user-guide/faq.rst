FAQ
===

Why is a checksum used to calculate uniqueness of RPMs?
-------------------------------------------------------

Pulp only stores one copy of each unique unit, no matter how many repositories
that unit is associated with. NEVRA is not enough for us to guarantee that two
RPMs are in fact the same, because for example, they may be signed with
different keys. Using the checksum to verify uniqueness is the best way for us
to accomplish this.

It may not make sense to have two RPMs with the same NEVRA in the same
repository, but there might be a use case. As a rule, pulp intentionally does
very little to enforce what makes a repository "valid". We give you the tools
to manage collections of content, and you get to decide what constitutes a
valid collection for your use case.
