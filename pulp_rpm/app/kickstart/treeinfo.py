from gettext import gettext as _
from configparser import MissingSectionHeaderError
from urllib.parse import urljoin

from django.utils.timezone import now

from productmd.common import SortedConfigParser
from productmd.treeinfo import TreeInfo

from pulp_rpm.app.constants import (
    DIST_TREE_MAIN_REPO_PATH,
    PACKAGES_DIRECTORY
)


def get_treeinfo_data(remote, remote_url):
    """
    Get Treeinfo data from remote.

    """
    treeinfo_serialized = {}
    namespaces = [".treeinfo", "treeinfo"]
    for namespace in namespaces:
        downloader = remote.get_downloader(
            url=urljoin(remote_url, namespace), silence_errors_for_response_status_codes={404}
        )

        try:
            result = downloader.fetch()
        except FileNotFoundError:
            continue

        treeinfo = PulpTreeInfo()
        treeinfo.load(f=result.path)
        treeinfo_parsed = treeinfo.parsed_sections()
        sha256 = result.artifact_attributes["sha256"]
        treeinfo_serialized = TreeinfoData(treeinfo_parsed).to_dict(hash=sha256, filename=namespace)
        break

    return treeinfo_serialized


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

            # ProductMD follows a specific order to deserialize:
            # https://github.com/release-engineering/productmd/blob/master/productmd/treeinfo.py#L120
            deserialize_order = "header release tree variants checksums images stage2 media".split()

            for section in deserialize_order:
                if section not in sections:
                    continue
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

        general = self.original_parser._sections.get("general")
        build_timestamp = ""

        if general:
            if "general" not in parser._sections:
                parser._sections["general"] = general

            if "." in str(general.get("timestamp")):
                build_timestamp = float(general["timestamp"])

        tree = self.original_parser._sections.get("tree", {})

        if "." in str(tree.get("build_timestamp")):
            build_timestamp = float(tree.get["build_timestamp"])

        if build_timestamp and parser._sections.get("general", {}).get("timestamp"):
            parser._sections["general"]["timestamp"] = build_timestamp

        if build_timestamp and parser._sections.get("tree", {}).get("build_timestamp"):
            parser._sections["tree"]["build_timestamp"] = build_timestamp

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
        self._repository_map = {}

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
            dict: Dictionary where each key is the id and value is a dictionary of variant data

        """
        variant_uids = self._data.get("tree", {}).get("variants")
        variant_uids = variant_uids.split(",") if variant_uids else []
        variants = {}

        self._addon_uids = []

        for variant_uid in variant_uids:
            variant_key = "variant-" + variant_uid
            is_main_repo = self._data[variant_key]["repository"] == DIST_TREE_MAIN_REPO_PATH
            if is_main_repo:
                repository = DIST_TREE_MAIN_REPO_PATH
                packages = PACKAGES_DIRECTORY
            else:
                repository = self._data[variant_key]["id"]
                packages = "{}/{}".format(repository, PACKAGES_DIRECTORY)

            variant = {
                "variant_id": self._data[variant_key]["id"],
                "uid": self._data[variant_key]["uid"],
                "name": self._data[variant_key]["name"],
                "type": self._data[variant_key]["type"],
                "packages": packages,
                "repository": repository,
            }
            keys = [
                "source_packages",
                "source_repository",
                "debug_packages",
                "debug_repository",
                "identity"
            ]

            self._repodata_paths.append(self._data[variant_key]["repository"])
            self._repository_map[self._data[variant_key]["repository"]] = repository

            for key in keys:
                if key in self._data[variant_key].keys():
                    variant.update({key: self._data[variant_key][key]})

            addons = self._data[variant_key].get("addons")
            if addons:
                self._addon_uids.extend(addons.split(","))
            variants[variant["variant_id"]] = variant

        return variants

    @property
    def addons(self):
        """
        Addon data.

        Returns:
            dict: Dictionary where each key is the id and value is a dictionary of addon data

        """
        addons = {}

        if not self._addon_uids:
            self.variants

        for addon_uid in self._addon_uids:
            addon_key = "addon-" + addon_uid
            repository = self._data[addon_key]["id"]
            packages = "{}/{}".format(repository, PACKAGES_DIRECTORY)

            addon = {
                "addon_id": self._data[addon_key]["id"],
                "uid": self._data[addon_key]["uid"],
                "name": self._data[addon_key]["name"],
                "type": self._data[addon_key]["type"],
                "packages": packages,
                "repository": repository,
            }

            self._repodata_paths.append(self._data[addon_key]["repository"])
            self._repository_map[self._data[addon_key]["repository"]] = repository

            addons[addon["addon_id"]] = addon

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
        data["repo_map"] = self._repository_map

        return data
