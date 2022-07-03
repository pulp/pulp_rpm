import logging

import createrepo_c as cr

log = logging.getLogger(__name__)


def warningcb(warning_type, message):
    """Optional callback for warnings about wierd stuff and formatting in XML.

    Args:
        warning_type (int): One of the XML_WARNING_* constants.
        message (str): Message.
    """
    log.warn("PARSER WARNING: %s" % message)
    return True  # continue parsing


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

    def for_each_pkg_primary(self, pkgcb):
        """Execute a callback for each package, parsed from only primary package metadata.

        Only primary metadata means no files or changelogs.
        """
        cr.xml_parse_primary(self.primary_xml_path, pkgcb=pkgcb, do_files=False)

    def as_iterator(self):
        """Return a package iterator."""
        return cr.PackageIterator(
            primary_path=self.primary_xml_path,
            filelists_path=self.filelists_xml_path,
            other_path=self.other_xml_path,
            warningcb=warningcb,
        )
