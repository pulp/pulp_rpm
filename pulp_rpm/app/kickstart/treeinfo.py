import json
from collections import defaultdict
from gettext import gettext as _
from configparser import MissingSectionHeaderError

from django.utils.timezone import now

from productmd.common import SortedConfigParser
from productmd.treeinfo import TreeInfo

from pulp_rpm.app.constants import DIST_TREE_MAIN_REPO_PATH, PACKAGES_DIRECTORY


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

    def serialize(self, parser, main_variant=None):
        """
        Handle errors on serialize TreeInfo.

        """
        try:
            super().serialize(parser, main_variant=main_variant)
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

            if general.get("timestamp"):
                build_timestamp = float(general["timestamp"])

        tree = self.original_parser._sections.get("tree", {})

        if tree.get("build_timestamp"):
            build_timestamp = float(tree.get("build_timestamp"))

        if build_timestamp and parser._sections.get("general", {}).get("timestamp"):
            parser._sections["general"]["timestamp"] = build_timestamp

        if build_timestamp and parser._sections.get("tree", {}).get("build_timestamp"):
            parser._sections["tree"]["build_timestamp"] = build_timestamp

        release = self.original_parser._sections.get("release", {})

        if "is_layered" in release:
            parser._sections["release"]["is_layered"] = json.loads(release["is_layered"])

        return parser._sections

    def rewrite_subrepo_paths(self, treeinfo_data):
        """Rewrite the variant/addon repository paths to be local.

        Ensure that the sub-repo path is in a sub-directory.

        Variants that Pulp supports can be of type "variant" or "addon". A "variant" type is a
        parent variant, while an "addon" is a child variant. So we need to request variants
        recursively to fix all the paths.
        """
        for variant in self.variants.get_variants(recursive=True):
            if variant.type == "variant":
                variant.paths.repository = treeinfo_data.variants[variant.id]["repository"]
                variant.paths.packages = treeinfo_data.variants[variant.id]["packages"]
            elif variant.type == "addon":
                variant.paths.repository = treeinfo_data.addons[variant.id]["repository"]
                variant.paths.packages = treeinfo_data.addons[variant.id]["packages"]
            else:
                # unsupported type, e.g. "optional"
                pass


class TreeinfoData:
    """
    Treat parsed treeinfo data.

    """

    def __init__(self, data):
        """
        Setting Treeinfo data.

        """
        self._data = data

        self._addon_uids = set()
        self._addons = {}
        self._checksums = []
        self._distribution_tree = {}
        self._images = []
        self._image_paths = {}
        self._image_checksum_map = {}
        self._repodata_paths = set()
        self._repomd_xmls = set()
        self._repository_map = {}
        self._variants = {}

    @property
    def distribution_tree(self):
        """
        Distribution tree data.

        Returns:
            dict: distribution tree data

        """
        if self._distribution_tree:
            return self._distribution_tree

        distribution_tree = {}

        if self._data.get("general"):
            distribution_tree.update(
                {
                    "release_name": self._data["general"]["family"],
                    "release_short": self._data["general"]["family"],
                    "release_version": self._data["general"]["version"],
                    "arch": self._data["general"]["arch"],
                    "build_timestamp": self._data["general"]["timestamp"],
                }
            )

        distribution_tree.update(
            {"header_version": self._data.get("header", {}).get("version", "1.2")}
        )

        if self._data.get("release"):
            is_layered = self._data["release"].get("is_layered", False)

            # If we get is_layered, but it's a string - let json turn it into a boolean
            if is_layered and isinstance(is_layered, str):
                is_layered = json.loads(is_layered)

            distribution_tree.update(
                {
                    "release_name": self._data["release"]["name"],
                    "release_short": self._data["release"]["short"],
                    "release_version": self._data["release"]["version"],
                    "release_is_layered": is_layered,
                }
            )

        if self._data.get("tree"):
            distribution_tree.update(
                {
                    "arch": self._data["tree"]["arch"],
                    "build_timestamp": self._data["tree"]["build_timestamp"],
                }
            )

        if self._data.get("base_product"):
            distribution_tree.update(
                {
                    "base_product_name": self._data["base_product"]["name"],
                    "base_product_short": self._data["base_product"]["short"],
                    "base_product_version": self._data["base_product"]["version"],
                }
            )

        if self._data.get("stage2"):
            distribution_tree.update(self._data.get("stage2"))

        if self._data.get("media"):
            distribution_tree.update(self._data.get("media"))

        self._distribution_tree = distribution_tree
        return self._distribution_tree

    @property
    def checksums(self):
        """
        Checksum data.

        Returns:
            list: List of checksum data

        """
        if self._checksums:
            return self._checksums

        checksums = []

        for key, value in self._data.get("checksums", {}).items():
            checksum = {}
            checksum["path"] = key
            checksum["checksum"] = value

            _key, _value = value.split(":")

            if "repodata/repomd.xml" in key:
                self._repomd_xmls.add(key)
            else:
                self._image_checksum_map.update({key: {_key: _value}})

            checksums.append(checksum)

        self._checksums = checksums
        return self._checksums

    @property
    def images(self):
        """
        Image data.

        Returns:
            list: List of image data
        """
        if self._images:
            return self._images

        # self._image_paths is {path: [platform-list]
        images = []  # list-of {name: str, path: str, platforms: [platform-list]}
        temp = defaultdict(set)  # {stanza: set(paths)}

        for key in self._data.keys():
            if key.startswith("images"):  # e.g. images-xen or images-x86_64
                platform = key.split("-")[1]  # e.g. xen or x86_64
                for stanza, path in self._data.get(key).items():
                    # A given stanza can have multiple paths - add to set here
                    temp[stanza].add(path)

                    # A path can be associated with multiple platforms - add to list here
                    if path in self._image_paths:
                        _platform = f"{self._image_paths[path]}, {platform}"
                    else:
                        _platform = platform
                    self._image_paths.update({path: _platform})

        for stanza, paths in temp.items():
            for path in paths:
                image = {"name": stanza, "path": path, "platforms": self._image_paths[path]}
                self._image_paths[path] = {}
                images.append(image)

        extra_images = ["mainimage", "instimage"]
        for extra in extra_images:
            stage2_path = self._data.get("stage2", {}).get(extra)
            if stage2_path:
                self._image_paths[stage2_path] = {}

        self._images = images
        return self._images

    @property
    def variants(self):
        """
        Variant data.

        Returns:
            dict: Dictionary where each key is the id and value is a dictionary of variant data

        """
        if self._variants:
            return self._variants

        variant_uids = self._data.get("tree", {}).get("variants")
        variant_uids = variant_uids.split(",") if variant_uids else []
        variants = {}

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
            optional_variant_data_keys = [
                "source_packages",
                "source_repository",
                "debug_packages",
                "debug_repository",
                "identity",
            ]

            self._repodata_paths.add(self._data[variant_key]["repository"])
            self._repository_map[self._data[variant_key]["repository"]] = repository

            for optional_key in optional_variant_data_keys:
                if optional_key in self._data[variant_key]:
                    variant[optional_key] = self._data[variant_key][optional_key]

            addons = self._data[variant_key].get("addons")
            if addons:
                self._addon_uids |= set(addons.split(","))
            variants[variant["variant_id"]] = variant

        self._variants = variants
        return self._variants

    @property
    def addons(self):
        """
        Addon data.

        Returns:
            dict: Dictionary where each key is the id and value is a dictionary of addon data

        """
        if self._addons:
            return self._addons

        addons = {}

        # Make sure variants are processed before addons, since addons are being discovered
        # through the variants.
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

            self._repodata_paths.add(self._data[addon_key]["repository"])
            self._repository_map[self._data[addon_key]["repository"]] = repository

            addons[addon["addon_id"]] = addon

        self._addons = addons
        return self._addons

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

        self._image_paths.update(self._image_checksum_map)
        data["download"] = dict(repodatas=list(self._repodata_paths), images=self._image_paths)
        data["repo_map"] = self._repository_map

        return data
