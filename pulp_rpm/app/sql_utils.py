from collections import defaultdict
from collections.abc import Iterable

from django.db.models import Expression, F, Field, Func, IntegerField, Q
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
    """Passes a non-query-set iterable of values a single array parameter.

    This ensures selections such as `pk__in=(1,2, ..., n)` doesn't generate a SQL with
    n query params (e.g, `WHERE pk in (%s, %s, ..., %s)`), but a single %s which is a
    postgres array of values. This prevent hitting the 65535 query param limit on the
    extended query protocol:

    <https://www.postgresql.org/docs/current/protocol-flow.html#PROTOCOL-FLOW-EXT-QUERY>

    Use this if you need to pass a potentially large list of materialized values into
    a `{field}__in` filter. If the values are purely from queryset, this is not required.

    Notes:
        * Doesn't work on "pk" for casted Content subclasses (e.g. PackageGroup, Package): there,
          pk is a foreign key (content_ptr), not a plain UUID field, and any_array isn't supported.
    """
    if not isinstance(values, (list, set, tuple, frozenset)):
        values_type = type(values)
        raise TypeError(
            f"This is designed to be used with in-memory iterable of values. Got: {values_type}"
        )
    return Q(**{f"{field_name}__any_array": list(values)})


class UnnestMapping(Expression):
    """Maps a model field to values using PostgreSQL unnest() with parallel arrays.

    Resolves `field_name` through Django's own compiler (rather than a hardcoded table
    name), so it works correctly regardless of the alias Django assigns the field's table -
    including when the annotated queryset is embedded in a Subquery().
    """

    def __init__(
        self, field_name, keys, values, key_type="uuid", value_type="int", output_field=None
    ):
        super().__init__(output_field=output_field or IntegerField())
        self.field_expr = F(field_name) if isinstance(field_name, str) else field_name
        self.keys = list(keys)
        self.values = list(values)
        self.key_type = key_type
        self.value_type = value_type

    def get_source_expressions(self):
        return [self.field_expr]

    def set_source_expressions(self, exprs):
        (self.field_expr,) = exprs

    def as_sql(self, compiler, connection):
        field_sql, field_params = compiler.compile(self.field_expr)
        sql = (
            f"(SELECT map.val FROM unnest(%s::{self.key_type}[], %s::{self.value_type}[]) "
            f"AS map(key, val) WHERE map.key = {field_sql})"
        )
        params = [self.keys, self.values] + list(field_params)
        return sql, params


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

    # Map pk -> age via a single unnest()-zipped array (2 params total, regardless of
    # how many packages are involved).
    pks, ages = zip(*age_mapping.items()) if age_mapping else ((), ())
    return qs.annotate(age=UnnestMapping("pk", pks, ages))
