from urllib.parse import urljoin

from aiohttp import ClientResponseError
from django.utils.timezone import now

from productmd.common import SortedConfigParser
from productmd.treeinfo import TreeInfo


def get_kickstart_data(remote):
    """
    Get Kickstart data from remote.

    """
    kickstart = {}
    namespaces = [".treeinfo", "treeinfo"]
    for namespace in namespaces:
        downloader = remote.get_downloader(url=urljoin(remote.url, namespace))

        try:
            result = downloader.fetch()
        except ClientResponseError as exc:
            if 404 == exc.status:
                continue
            raise

        kickstart = TreeInfo()
        kickstart.load(f=result.path)
        parser = SortedConfigParser()
        kickstart.serialize(parser)
        kickstart_parsed = parser._sections
        sha256 = result.artifact_attributes["sha256"]
        kickstart = KickstartData(kickstart_parsed).to_dict(hash=sha256)
        break

    return kickstart


def repodata_exists(remote, url):
    """
    Check if repodata exists.

    """
    downloader = remote.get_downloader(url=urljoin(url, "repodata/repomd.xml"))

    try:
        downloader.fetch()
    except ClientResponseError as exc:
        if 404 == exc.status:
            return False

    return True


class KickstartData:
    """
    Treat parsed kickstart data.

    """

    def __init__(self, data):
        """
        Setting Kickstart data.

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
        distribution_tree = {
            "header_version": self._data["header"]["version"],
            "release_name": self._data["release"]["name"],
            "release_short": self._data["release"]["short"],
            "release_version": self._data["release"]["version"],
            "release_is_layered": self._data["release"].get("is_layered", False),
            "arch": self._data["tree"]["arch"],
            "build_timestamp": self._data["tree"]["build_timestamp"],
        }

        if self._data.get("base_product"):
            distribution_tree.update({
                "base_product_name": self._data["base_product"]["name"],
                "base_product_short": self._data["base_product"]["short"],
                "base_product_version": self._data["base_product"]["version"],
            })

        if self._data.get("stage2"):
            stage2 = {key: value for key, value in self._data.get("stage2").items()}
            distribution_tree.update(stage2)

        if self._data.get("media"):
            media = {key: value for key, value in self._data.get("media").items()}
            distribution_tree.update(media)

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
        platforms = self._data["tree"]["platforms"].split(",")
        images = []
        self._image_paths = {}

        temp = {}
        for platform in platforms:
            image_key = "images-" + platform
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
        variant_uids = self._data["tree"]["variants"].split(",")
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
        Kickstart data.

        Returns:
            dict: All kickstart data.

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
