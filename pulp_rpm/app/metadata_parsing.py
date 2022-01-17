import bz2
import collections
import gzip
import logging
import lzma
import os
import re
from django.conf import settings

import createrepo_c as cr
from xml.etree.cElementTree import iterparse

log = logging.getLogger(__name__)

NS_STRIP_RE = re.compile("{.*?}")


def iterative_files_changelog_parser(file_extension, filelists_xml_path, other_xml_path):
    """
    Iteratively parse filelists.xml and other.xml, to avoid over-use of memory.

    createrepo_c parses everything in bulk, into memory. For large repositories such as
    RHEL 7 or OL 7, this can require more than 5gb of memory. That isn't acceptable, especially
    when many repositories are being synced at once. The main offenders are other.xml (changelogs)
    and filelists.xml (list of owned files). These also happen to be relatively easy to parse.

    This function, ported from Pulp 2, takes a path to filelists.xml and other.xml, creates
    a streaming parser for each, and then yields one package worth of data from each file.
    """
    # it's basically always gzip, but we'll cover our bases w/ all the possibilites
    if file_extension == "gz":
        open_func = gzip.open
    elif file_extension == "xz":
        open_func = lzma.open
    elif file_extension == "bz2":
        open_func = bz2.open
    elif file_extension == "xml":
        open_func = open
    else:
        raise TypeError("Unknown metadata compression type")
    # TODO: zstd

    with open_func(filelists_xml_path) as filelists_xml, open_func(other_xml_path) as other_xml:
        filelists_parser = iterparse(filelists_xml, events=("start", "end"))
        filelists_xml_iterator = iter(filelists_parser)

        other_parser = iterparse(other_xml, events=("start", "end"))
        other_xml_iterator = iter(other_parser)

        # get a hold of the root element so we can clear it
        # this prevents the entire parsed document from building up in memory
        try:
            filelists_root_element = next(filelists_xml_iterator)[1]
            other_root_element = next(other_xml_iterator)[1]
        # I know. This is a terrible misuse of SyntaxError. Don't blame the messenger.
        except SyntaxError:
            log.error("failed to parse XML metadata file")
            raise

        while True:
            for event, filelists_element in filelists_xml_iterator:
                # if we're not at a fully parsed package element, keep going
                if event != "end":
                    continue
                # make this work whether the file has namespace as part of the tag or not
                if not (
                    filelists_element.tag == "package"
                    or re.sub(NS_STRIP_RE, "", filelists_element.tag) == "package"
                ):
                    continue

                break

            for event, other_element in other_xml_iterator:
                # if we're not at a fully parsed package element, keep going
                if event != "end":
                    continue
                # make this work whether the file has namespace as part of the tag or not
                if not (
                    other_element.tag == "package"
                    or re.sub(NS_STRIP_RE, "", other_element.tag) == "package"
                ):
                    continue

                break

            (filelists_pkgid, files) = process_filelists_package_element(filelists_element)
            (other_pkgid, changelogs) = process_other_package_element(other_element)

            filelists_root_element.clear()  # clear all previously parsed ancestors of the root
            other_root_element.clear()

            assert (
                filelists_pkgid == other_pkgid
            ), "Package id for filelists.xml ({}) and other.xml ({}) do not match".format(
                filelists_pkgid, other_pkgid
            )

            yield filelists_pkgid, files, changelogs


def process_filelists_package_element(element):
    """Parse one package element from the filelists.xml."""
    pkgid = element.attrib["pkgid"]

    files = []
    for subelement in element:
        if subelement.tag == "file" or re.sub(NS_STRIP_RE, "", subelement.tag) == "file":
            basename, filename = os.path.split(subelement.text)
            basename = f"{basename}/"
            ftype = subelement.attrib.get("type")
            files.append((ftype, basename, filename))

    return pkgid, files


def process_other_package_element(element):
    """Parse package element from other.xml."""
    pkgid = element.attrib["pkgid"]
    changelogs = []

    for subelement in element:
        if subelement.tag == "changelog" or re.sub(NS_STRIP_RE, "", subelement.tag) == "changelog":
            author = subelement.attrib["author"]
            date = int(subelement.attrib["date"])
            text = subelement.text
            changelogs.append((author, date, text))

    if settings.KEEP_CHANGELOG_LIMIT is not None:
        # always keep at least one changelog, even if the limit is set to 0
        changelog_limit = settings.KEEP_CHANGELOG_LIMIT or 1
        # changelogs are listed in chronological order, grab the last N changelogs from the list
        changelogs = changelogs[-changelog_limit:]
    return pkgid, changelogs


def warningcb(warning_type, message):
    """Optional callback for warnings about wierd stuff and formatting in XML.

    Args:
        warning_type (int): One of the XML_WARNING_* constants.
        message (str): Message.
    """
    log.warn("PARSER WARNING: %s" % message)
    return True  # continue parsing


def parse_repodata(primary_xml_path, filelists_xml_path, other_xml_path, only_primary=False):
    """
    Parse repodata to extract package info.

    Args:
        primary_xml_path (str): a path to a downloaded primary.xml
        filelists_xml_path (str): a path to a downloaded filelists.xml
        other_xml_path (str): a path to a downloaded other.xml

    Kwargs:
        only_primary (bool): If true, only the metadata in primary.xml will be parsed.

    Returns:
        dict: createrepo_c package objects with the pkgId as a key

    """

    def pkgcb(pkg):
        """
        A callback which is used when a whole package entry in xml is parsed.

        Args:
            pkg(preaterepo_c.Package): a parsed metadata for a package

        """
        packages[pkg.pkgId] = pkg

    def newpkgcb(pkgId, name, arch):
        """
        A callback which is used when a new package entry is encountered.

        Only opening <package> element is parsed at that moment.
        This function has to return a package which parsed data will be added to
        or None if a package should be skipped.

        pkgId, name and arch of a package can be used to skip further parsing. Available
        only for filelists.xml and other.xml.

        Args:
            pkgId(str): pkgId of a package
            name(str): name of a package
            arch(str): arch of a package

        Returns:
            createrepo_c.Package: a package which parsed data should be added to.

            If None is returned, further parsing of a package will be skipped.

        """
        return packages.get(pkgId, None)

    packages = collections.OrderedDict()

    cr.xml_parse_primary(primary_xml_path, pkgcb=pkgcb, warningcb=warningcb, do_files=False)
    if not only_primary:
        cr.xml_parse_filelists(filelists_xml_path, newpkgcb=newpkgcb, warningcb=warningcb)
        cr.xml_parse_other(other_xml_path, newpkgcb=newpkgcb, warningcb=warningcb)
    return packages


class MetadataParser:
    """Parser for RPM metadata."""

    def __init__(self):
        """Initialize empty (use one of the alternate constructors)."""
        self.primary_xml_path = None
        self.filelists_xml_path = None
        self.other_xml_path = None

    @staticmethod
    def from_metadata_files(primary_xml_path, filelists_xml_path, other_xml_path):
        """Construct a parser from the three main metadata files."""
        parser = MetadataParser()
        parser.primary_xml_path = primary_xml_path
        parser.filelists_xml_path = filelists_xml_path
        parser.other_xml_path = other_xml_path
        return parser

    def count_packages(self):
        """Count the total number of packages."""
        # It would be much faster to just read the number in the header of the metadata.
        # But there's no way to do that, and also we can't necessarily rely on that number because
        # of duplicates.
        len(
            parse_repodata(
                self.primary_xml_path,
                self.filelists_xml_path,
                self.other_xml_path,
                only_primary=True,
            )
        )

    def parse_packages_iterative(self, file_extension, skip_srpms=False):
        """Parse packages iteratively using the hybrid parser."""
        extra_repodata_parser = iterative_files_changelog_parser(
            file_extension, self.filelists_xml_path, self.other_xml_path
        )
        seen_pkgids = set()
        # We *do not* want to skip srpms when parsing primary because otherwise we run into
        # trouble when we encounter them again on the iterative side of the parser. Just skip
        # them at the end.
        for pkg in self.parse_packages(only_primary=True):
            pkgid = pkg.pkgId
            while True:
                pkgid_extra, files, changelogs = next(extra_repodata_parser)
                if pkgid_extra in seen_pkgids:
                    # This is a dirty hack to handle cases that "shouldn't" happen.
                    # Sometimes repositories have packages listed twice under the same
                    # pkgid. This is a problem because the primary.xml parsing
                    # deduplicates the entries by placing them into a dict keyed by pkgid.
                    # So if the iterative parser(s) run into a package we've seen before,
                    # we should skip it and move on.
                    continue
                else:
                    seen_pkgids.add(pkgid)
                    break

            assert pkgid == pkgid_extra, (
                "Package id from primary metadata ({}), does not match package id "
                "from filelists, other metadata ({})"
            ).format(pkgid, pkgid_extra)

            if skip_srpms and pkg.arch == "src":
                continue

            pkg.files = files
            pkg.changelogs = changelogs
            yield pkg

    def parse_packages(self, only_primary=False, skip_srpms=False):
        """Parse packages using the traditional createrepo_c parser."""
        packages = parse_repodata(
            self.primary_xml_path,
            self.filelists_xml_path,
            self.other_xml_path,
            only_primary=only_primary,
        )
        while True:
            try:
                (pkgid, pkg) = packages.popitem(last=False)
            except KeyError:
                break

            if skip_srpms and pkg.arch == "src":
                continue

            yield pkg
