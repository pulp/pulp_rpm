import bz2
import gzip
import logging
import lzma
import os
import re
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

            filelists_root_element.clear()  # clear all previously parsed ancestors of the root
            other_root_element.clear()

            (filelists_pkgid, files) = process_filelists_package_element(filelists_element)
            (other_pkgid, changelogs) = process_other_package_element(other_element)

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
    for element in element.findall("{*}file"):
        basename, filename = os.path.split(element.text)
        ftype = element.attrib.get("type")

        files.append((ftype, basename, filename))

    return pkgid, files


def process_other_package_element(element):
    """Parse package element from other.xml."""
    pkgid = element.attrib["pkgid"]

    changelogs = []
    for element in element.findall("{*}changelog"):
        author = element.attrib["author"]
        date = int(element.attrib["date"])
        text = element.text

        changelogs.append((author, date, text))

    return pkgid, changelogs
