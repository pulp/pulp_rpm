
import os
import rpmUtils
from createrepo import yumbased

from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)


def get_package_xml(pkg_path):
    """
    Method to generate repo xmls - primary, filelists and other
    for a given rpm.

    @param pkg_path: rpm package path on the filesystem
    @type pkg_path: str

    @return rpm metadata dictionary or empty if rpm path doesnt exist
    @rtype {}
    """
    if not os.path.exists(pkg_path):
        _LOG.info("Package path %s does not exist" % pkg_path)
        return {}
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    po = yumbased.CreateRepoPackage(ts, pkg_path)
    # RHEL6 createrepo throws a ValueError if _cachedir is not set
    po._cachedir = None
    primary_xml_snippet = change_location_tag(po.xml_dump_primary_metadata(), pkg_path)
    metadata = {'primary' : primary_xml_snippet,
                'filelists': po.xml_dump_filelists_metadata(),
                'other'   : po.xml_dump_other_metadata(),
               }
    return metadata

def change_location_tag(primary_xml_snippet, relpath):
    """
    Transform the <location> tag to strip out leading directories so it
    puts all rpms in the same directory as 'repodata'

    @param primary_xml_snippet: snippet of primary xml text for a single package
    @type primary_xml_snippet: str

    @param relpath: Package's 'relativepath'
    @type relpath: str
    """

    basename = os.path.basename(relpath)
    start_index = primary_xml_snippet.find("<location ")
    end_index = primary_xml_snippet.find("/>", start_index) + 2 # adjust to end of closing tag

    first_portion = util.string_to_unicode(primary_xml_snippet[:start_index])
    end_portion = util.string_to_unicode(primary_xml_snippet[end_index:])
    location = util.string_to_unicode("""<location href="%s"/>""" % (basename))
    return first_portion + location + end_portion

