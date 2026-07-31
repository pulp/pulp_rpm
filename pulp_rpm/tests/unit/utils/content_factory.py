import uuid

from pulpcore.plugin.models import Content

from pulp_rpm.app.models import (
    Modulemd,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    RpmRepository,
    UpdateCollection,
    UpdateCollectionPackage,
    UpdateRecord,
)


class RepoContentFactory:
    """Accumulates content added inside a `with` block into one RepositoryVersion on exit.

    Each `add_*` method creates a single content unit, adds it to this factory's pending set,
    and returns whatever identifies it (pk, or (nsvca, pk) for modules). Callers loop over
    `add_*` themselves for "many" - this class only tracks what to put in the repo version.
    """

    def __init__(self, repo_name=None):
        self._repo_name = repo_name or str(uuid.uuid4())
        self._content_pks = []
        self._repo = None
        self.version = None

    def __enter__(self):
        self._repo, _ = RpmRepository.objects.get_or_create(name=self._repo_name)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            with self._repo.new_version() as version:
                version.add_content(Content.objects.filter(pk__in=self._content_pks))
            self.version = self._repo.latest_version()

    def get_repository(self):
        return self._repo

    def add_packages(self, names: list[str]) -> list:
        """Create one Package per name. Returns their pks, in the same order as `names`."""
        pks = []
        for name in names:
            pk = Package.objects.create(
                name=name,
                epoch="0",
                version="1.0",
                release="1",
                arch="noarch",
                pkgId=f"fakedigest-{name}",
                checksum_type="sha256",
            ).pk
            pks.append(pk)
        self._content_pks.extend(pks)
        return pks

    def add_package_group(self, name, *, packages=()):
        group, _ = PackageGroup.objects.get_or_create(
            id=name,
            defaults={
                "name": name,
                "digest": uuid.uuid4().hex,
                "packages": [{"name": n} for n in packages],
            },
        )
        self._content_pks.append(group.pk)
        return group.pk

    def add_package_category(self, name, *, group_names):
        category, _ = PackageCategory.objects.get_or_create(
            id=name,
            defaults={
                "name": name,
                "digest": uuid.uuid4().hex,
                "group_ids": [{"name": group_name, "default": True} for group_name in group_names],
            },
        )
        self._content_pks.append(category.pk)
        return category.pk

    def add_package_environment(self, name, *, group_names, option_names=()):
        environment, _ = PackageEnvironment.objects.get_or_create(
            id=name,
            defaults={
                "name": name,
                "digest": uuid.uuid4().hex,
                "group_ids": [{"name": group_name, "default": True} for group_name in group_names],
                "option_ids": [{"name": g, "default": True} for g in option_names],
            },
        )
        self._content_pks.append(environment.pk)
        return environment.pk

    def add_modulemds(self, names: list[str]) -> tuple[list, list]:
        """Create one Modulemd per name. Returns (nsvcas, pks), both in `names` order."""
        nsvcas = []
        pks = []
        for name in names:
            nsvca = (name, "stream0", "1", uuid.uuid4().hex[:8], "noarch")
            pk = Modulemd.objects.create(
                name=nsvca[0],
                stream=nsvca[1],
                version=nsvca[2],
                context=nsvca[3],
                arch=nsvca[4],
                description="",
                digest=uuid.uuid4().hex,
                snippet="",
            ).pk
            nsvcas.append(nsvca)
            pks.append(pk)
        self._content_pks.extend(pks)
        return nsvcas, pks

    def add_advisory(self, advisory_id, *, package_names=None, module_nsvcas=None):
        """UpdateRecord referencing the given package names and/or module NSVCAs.

        Packages all go in one UpdateCollection. Modules each need their own UpdateCollection,
        since a collection carries at most one module NSVCA (UpdateCollection.module).
        """
        advisory, _ = UpdateRecord.objects.get_or_create(
            id=advisory_id,
            defaults={
                "updated_date": "",
                "description": "",
                "issued_date": "",
                "fromstr": "",
                "status": "",
                "title": "",
                "summary": "",
                "version": "",
                "type": "",
                "severity": "",
                "solution": "",
                "release": "",
                "rights": "",
                "pushcount": "",
                "digest": uuid.uuid4().hex,
            },
        )
        if package_names:
            collection, _ = UpdateCollection.objects.get_or_create(
                update_record=advisory, name="collection"
            )
            UpdateCollectionPackage.objects.bulk_create(
                [
                    UpdateCollectionPackage(
                        update_collection=collection,
                        name=name,
                        epoch="0",
                        version="1.0",
                        release="1",
                        arch="noarch",
                        filename=f"{name}.rpm",
                        src="",
                        sum="",
                    )
                    for name in package_names
                ]
            )
        if module_nsvcas:
            for i, (name, stream, version, context, arch) in enumerate(module_nsvcas):
                UpdateCollection.objects.get_or_create(
                    update_record=advisory,
                    name=f"collection-{i}",
                    defaults={
                        "module": {
                            "name": name,
                            "stream": stream,
                            "version": version,
                            "context": context,
                            "arch": arch,
                        },
                    },
                )
        self._content_pks.append(advisory.pk)
        return advisory.pk
