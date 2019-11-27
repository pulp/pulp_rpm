from gettext import gettext as _
from configparser import MissingSectionHeaderError
from urllib.parse import urljoin

from aiohttp import ClientResponseError
from django.utils.timezone import now

from productmd.common import SortedConfigParser
from productmd.treeinfo import TreeInfo


def get_treeinfo_data(remote):
    """
    Get Treeinfo data from remote.

    """
    treeinfo_serialized = {}
    remote_url = remote.url if remote.url[-1] == "/" else f"{remote.url}/"
    namespaces = [".treeinfo", "treeinfo"]
    for namespace in namespaces:
        downloader = remote.get_downloader(url=urljoin(remote_url, namespace))

        try:
            result = downloader.fetch()
        except ClientResponseError as exc:
            if 404 == exc.status:
                continue
            raise
        except FileNotFoundError:
            continue

        treeinfo = PulpTreeInfo()
        treeinfo.load(f=result.path)
        treeinfo_parsed = treeinfo.parsed_sections()
        sha256 = result.artifact_attributes["sha256"]
        treeinfo_serialized = TreeinfoData(treeinfo_parsed).to_dict(hash=sha256)
        break

    return treeinfo_serialized


def create_treeinfo(distribution_tree):
    """
    Create treeinfo file.

    Args:
        distirbution_tree(app.models.DistributionTree): a distirbution_tree object

    Returns:
        f(File): treeinfo file.

    """
    parser = SortedConfigParser()
    treeinfo = {}

    treeinfo["header"] = {
        "type": "productmd.treeinfo",
        "version": distribution_tree.header_version,
    }

    treeinfo["release"] = {
        "name": distribution_tree.release_name,
        "short": distribution_tree.release_short,
        "version": distribution_tree.release_version,
        "is_layered": distribution_tree.release_is_layered,
    }

    if distribution_tree.base_product_name:
        treeinfo["base_product"] = {
            "name": distribution_tree.base_product_name,
            "short": distribution_tree.base_product_short,
            "version": distribution_tree.base_product_version,
        }

    treeinfo["tree"] = {
        "arch": distribution_tree.arch,
        "build_timestamp": distribution_tree.build_timestamp,
    }

    stage2 = {}
    media = {}

    if distribution_tree.instimage:
        stage2.update({"instimage": distribution_tree.instimage})

    if distribution_tree.mainimage:
        stage2.update({"mainimage": distribution_tree.mainimage})

    if stage2:
        treeinfo["stage2"] = stage2

    if distribution_tree.discnum:
        media.update({"discnum": distribution_tree.discnum})

    if distribution_tree.totaldiscs:
        media.update({"totaldiscs": distribution_tree.totaldiscs})

    if media:
        treeinfo["media"] = media

    checksums = {}
    for checksum in distribution_tree.checksums.all():
        checksums.update({checksum.path: checksum.checksum})

    if checksums:
        treeinfo["checksums"] = checksums

    tree_platforms = set()
    for image in distribution_tree.images.all():
        platforms = image.platforms.split(",")
        tree_platforms.update(platforms)

        for platform in platforms:
            current = treeinfo.get(f"images-{platform}", {})
            current.update({image.name: image.path})
            treeinfo[f"images-{platform}"] = current

    treeinfo["tree"].update({"platforms": ",".join(tree_platforms)})

    for addon in distribution_tree.addons.all():
        treeinfo[f"addon-{addon.uid}"] = {
            "id": addon.addon_id,
            "uid": addon.uid,
            "name": addon.name,
            "type": addon.type,
            "packages": addon.packages,
            "repository": addon.addon_id,
        }
    variants = []
    nullables = [
        "source_packages", "source_repository", "debug_packages", "debug_repository", "identity"
    ]
    for variant in distribution_tree.variants.all():
        variants.append(variant.uid)
        treeinfo[f"variant-{variant.uid}"] = {
            "id": variant.variant_id,
            "uid": variant.uid,
            "name": variant.name,
            "type": variant.type,
            "packages": variant.packages,
            "repository": variant.variant_id,
        }

        for nullable in nullables:
            if getattr(variant, nullable):
                treeinfo[f"variant-{variant.uid}"].update({nullable: getattr(variant, nullable)})

    treeinfo["tree"].update({"variants": ", ".join(variants)})

    variants = sorted(variants)
    first_variant = treeinfo[f"variant-{variants[0]}"] if variants else {"packages": ".", "uid": ""}
    first_variant["repository"] = "."
    treeinfo["general"] = {
        "family": treeinfo["release"]["name"],
        "version": treeinfo["release"]["version"],
        "name": f"{treeinfo['release']['name']} {treeinfo['release']['version']}",
        "arch": treeinfo["tree"]["arch"],
        "platforms": treeinfo["tree"]["platforms"],
        "packagedir": first_variant["packages"],
        "repository": first_variant["repository"],
        "timestamp": treeinfo["tree"]["build_timestamp"],
        "variant": first_variant["uid"],
    }

    parser.read_dict(treeinfo)

    with open(".treeinfo", "w") as f:
        parser.write(f)

    return f


class PulpTreeInfo(TreeInfo):
    """
    Extend TreeInfo for handling errors.

    """

    def load(self, f):
        """
        Load data from a file.

        """
        try:
            super().load(f)
        except MissingSectionHeaderError:
            raise TypeError(_("Treeinfo file should have INI format"))

    def deserialize(self, parser):
        """
        Handle errors on deserialize TreeInfo.

        """
        try:
            super().deserialize(parser)
        except Exception:
            sections = parser._sections.keys()

            for section in sections:
                if section.startswith("image"):
                    section = "images"
                if section.startswith("variant"):
                    section = "variants"
                current = getattr(self, section, None)

                if current:
                    current.deserialize(parser)

                    if section == "release" and current.is_layered:
                        self.base_product.deserialize(parser)

            self.validate()
            self.header.set_current_version()

        self.original_parser = parser

    def serialize(self, parser):
        """
        Handle errors on serialize TreeInfo.

        """
        try:
            super().serialize(parser)
        except Exception:
            sections = set(self.original_parser._sections.keys()) - set(parser._sections.keys())
            self.validate()

            for section in sections:
                if section.startswith("image"):
                    section = "images"
                if section.startswith("variant"):
                    section = "variants"
                current = getattr(self, section, None)

                if current:
                    current.serialize(parser)

                    if section == "release" and current.is_layered:
                        self.base_product.serialize(parser)

    def parsed_sections(self):
        """
        Treeinfo parsed data.

        """
        parser = SortedConfigParser()
        self.serialize(parser)

        if "general" in self.original_parser._sections:
            if "general" not in parser._sections:
                parser._sections["general"] = self.original_parser._sections["general"]

        return parser._sections


class TreeinfoData:
    """
    Treat parsed treeinfo data.

    """

    def __init__(self, data):
        """
        Setting Treeinfo data.

        """
        self._data = data
        self._addon_uids = []
        self._repodata_paths = []

    @property
    def distribution_tree(self):
        """
        Distribution tree data.

        Returns:
            dict: distribution tree data

        """
        distribution_tree = {}

        if self._data.get("general"):
            distribution_tree.update({
                "release_name": self._data["general"]["family"],
                "release_short": self._data["general"]["family"],
                "release_version": self._data["general"]["version"],
                "arch": self._data["general"]["arch"],
                "build_timestamp": self._data["general"]["timestamp"],
            })

        distribution_tree.update(
            {"header_version": self._data.get("header", {}).get("version", "1.2")}
        )

        if self._data.get("release"):
            distribution_tree.update({
                "release_name": self._data["release"]["name"],
                "release_short": self._data["release"]["short"],
                "release_version": self._data["release"]["version"],
                "release_is_layered": self._data["release"].get("is_layered", False),
            })

        if self._data.get("tree"):
            distribution_tree.update({
                "arch": self._data["tree"]["arch"],
                "build_timestamp": self._data["tree"]["build_timestamp"],
            })

        if self._data.get("base_product"):
            distribution_tree.update({
                "base_product_name": self._data["base_product"]["name"],
                "base_product_short": self._data["base_product"]["short"],
                "base_product_version": self._data["base_product"]["version"],
            })

        if self._data.get("stage2"):
            distribution_tree.update(self._data.get("stage2"))

        if self._data.get("media"):
            distribution_tree.update(self._data.get("media"))

        return distribution_tree

    @property
    def checksums(self):
        """
        Checksum data.

        Returns:
            list: List of checksum data

        """
        self._repodatas = []
        self._images = {}
        checksums = []

        for key, value in self._data.get("checksums", {}).items():
            checksum = {}
            checksum["path"] = key
            checksum["checksum"] = value

            _key, _value = value.split(":")

            if "repodata" in key:
                self._repodatas.append(key)
            else:
                self._images.update({key: {_key: _value}})

            checksums.append(checksum)

        return checksums

    @property
    def images(self):
        """
        Image data.

        Returns:
            list: List of image data

        """
        images = []
        self._image_paths = {}

        temp = {}
        for key in self._data.keys():
            if key.startswith("images"):
                image_key = key
                platform = image_key.split("-")[1]
                for key, value in self._data.get(image_key, {}).items():
                    temp.update({key: value})

                    _platform = platform
                    if value in self._image_paths.keys():
                        _platform = f"{self._image_paths[value]}, {platform}"

                    self._image_paths.update({value: _platform})

        for key, value in temp.items():
            image = {}
            image["name"] = key
            image["path"] = value
            image["platforms"] = self._image_paths[value]

            self._image_paths[value] = {}

            images.append(image)

        extra_images = ["mainimage", "instimage"]
        for extra in extra_images:
            value = self._data.get("stage2", {}).get(extra)
            if value:
                self._image_paths[value] = {}

        return images

    @property
    def variants(self):
        """
        Variant data.

        Returns:
            list: List of variant data

        """
        variant_uids = self._data.get("tree", {}).get("variants")
        variant_uids = variant_uids.split(",") if variant_uids else []
        variants = []

        self._addon_uids = []

        for variant_uid in variant_uids:
            variant_key = "variant-" + variant_uid
            variant = {
                "variant_id": self._data[variant_key]["id"],
                "uid": self._data[variant_key]["uid"],
                "name": self._data[variant_key]["name"],
                "type": self._data[variant_key]["type"],
                "packages": self._data[variant_key]["packages"],
                "repository": self._data[variant_key]["repository"],
            }
            keys = [
                "source_packages",
                "source_repository",
                "debug_packages",
                "debug_repository",
                "identity"
            ]

            self._repodata_paths.append(self._data[variant_key]["repository"])

            for key in keys:
                if key in self._data[variant_key].keys():
                    variant.update({key: self._data[variant_key][key]})

            addons = self._data[variant_key].get("addons")
            if addons:
                self._addon_uids.extend(addons.split(","))
            variants.append(variant)

        return variants

    @property
    def addons(self):
        """
        Addon data.

        Returns:
            list: List of addon data

        """
        addons = []

        if not self._addon_uids:
            self.variants

        for addon_uid in self._addon_uids:
            addon_key = "addon-" + addon_uid
            addon = {
                "addon_id": self._data[addon_key]["id"],
                "uid": self._data[addon_key]["uid"],
                "name": self._data[addon_key]["name"],
                "type": self._data[addon_key]["type"],
                "packages": self._data[addon_key]["packages"],
                "repository": self._data[addon_key]["repository"],
            }

            self._repodata_paths.append(self._data[addon_key]["repository"])

            addons.append(addon)

        return addons

    def to_dict(self, **kwargs):
        """
        Treeinfo data.

        Returns:
            dict: All treeinfo data.

        """
        data = dict(
            created=now(),
            **kwargs,
            distribution_tree=self.distribution_tree,
            checksums=self.checksums,
            images=self.images,
            variants=self.variants,
            addons=self.addons,
        )

        self._image_paths.update(self._images)
        data["download"] = dict(repodatas=self._repodata_paths, images=self._image_paths)

        return data
