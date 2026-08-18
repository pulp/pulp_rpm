from collections import defaultdict
from collections.abc import Iterable

from django.db.models import Case, F, Field, Func, IntegerField, Q, When
from django.db.models.lookups import Lookup

from pulpcore.plugin.models import Content, RepositoryVersion
from pulpcore.plugin.util import get_domain_pk

from pulp_rpm.app.rpm_version import RpmVersion


class _AnyArray(Lookup):
    """PostgreSQL ``= ANY(%s)`` lookup. Passes the list as one array parameter."""

    lookup_name = "any_array"

    def get_prep_lookup(self):
        return [self.lhs.output_field.get_prep_value(v) for v in self.rhs]

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        return f"{lhs} = ANY(%s)", lhs_params + [list(self.rhs)]


Field.register_lookup(_AnyArray)


def safe_in(field_name: str, values: Iterable) -> Q:
    """WHERE x = ANY(%s)  -- passes the list as one array parameter.

    Doesn't work on "pk" for casted Content subclasses (e.g. PackageGroup, Package): there,
    pk is a foreign key (content_ptr), not a plain UUID field, and any_array isn't supported.
    """
    if not isinstance(values, (list, set, tuple, frozenset)):
        return Q(**{f"{field_name}__in": values})
    return Q(**{f"{field_name}__any_array": list(values)})


def get_content_in_repoversion(repo_version, content_qs=None, pulp_type=None, cast=False):
    """Get content present in repo_version.

    Args:
        repo_version: RepositoryVersion to restrict to.
        content_qs: Base queryset to restrict, defaults to Content.objects.
        pulp_type: Restrict to this pulp_type.
        cast: If True, query the specific Content subclass for pulp_type instead of base
            Content rows, so its own fields (not just pk) are accessible on the results.
            Requires pulp_type.
    """
    # TODO: remove once RepositoryVersion.get_content() applies its own unnest() workaround
    # unconditionally instead of only when content_ids has >= 65535 items.
    #
    # The reason behind this to enable testing membership against a large set (repo content)
    # with few query params, which the use of the pg array solves. Besides that, the query
    # leverages the fact that the table already contains the content_ids field, so it can
    # select the content in the repository version directly on the db side (without requiring
    # the app to ever re-send the whole set).
    repo_content_ids = (
        RepositoryVersion.objects.filter(pk=repo_version.pk)
        .annotate(cids=Func(F("content_ids"), function="unnest"))
        .values_list("cids", flat=True)
    )

    if cast:
        if pulp_type is None:
            raise ValueError("cast=True requires pulp_type")
        content_qs = Content.get_model_for_pulp_type(pulp_type).objects
        return content_qs.filter(pk__in=repo_content_ids, pulp_domain=get_domain_pk())

    content_qs = content_qs if content_qs is not None else Content.objects
    content_qs = content_qs.filter(pk__in=repo_content_ids, pulp_domain=get_domain_pk())
    if pulp_type is not None:
        content_qs = content_qs.filter(pulp_type=pulp_type)
    return content_qs


def annotate_with_age(qs):
    """Provide an "age" score for each Package object in the queryset.

    Annotate the Package objects with an "age". Age is calculated by partitioning the
    Packages by name and architecture and ordering the packages in each group by 'evr',
    which is the relative "age" within the group. The newest package gets age=1, second
    newest age=2, and so on.

    A second partition by architecture is important because there can be packages with
    the same name and version numbers but they are not interchangeable because they have
    differing arch, such as 'x86_64' and 'i686', or 'src' (SRPM) and any other arch.
    """
    # Get packages in current queryset with their basic info
    packages = list(qs.values("pk", "name", "arch", "epoch", "version", "release"))

    # Group packages by name and arch
    groups = defaultdict(list)
    for pkg in packages:
        key = (pkg["name"], pkg["arch"])
        groups[key].append(pkg)

    # Calculate age for each group
    age_mapping = {}
    for group_packages in groups.values():
        # Sort by EVR (newest first)
        group_packages.sort(
            key=lambda p: RpmVersion(p["epoch"], p["version"], p["release"]), reverse=True
        )

        # Assign ages (1 = newest, 2 = second newest, etc.)
        for age, pkg in enumerate(group_packages, 1):
            age_mapping[pkg["pk"]] = age

    # Create a queryset with age annotation
    # We'll use a CASE statement to map PKs to ages
    when_clauses = [When(pk=pk, then=age) for pk, age in age_mapping.items()]

    return qs.annotate(age=Case(*when_clauses, output_field=IntegerField()))
