import yum
from yum.misc import to_xml
from yum.update_md import UpdateMetadata, UpdateNotice

import util


log = util.getLogger(__name__)
#
# yum 3.2.22 compat:  UpdateMetadata.add_notice() not
# supported in 3.2.22.
#
if yum.__version__ < (3, 2, 28):
    def add_notice(self, un):
        if not un or not un["update_id"] or un['update_id'] in self._notices:
            return
        self._notices[un['update_id']] = un
        pkglist = un['pkglist'] or []
        for pkg in pkglist:
            for filedata in pkg['packages']:
                self._cache['%s-%s-%s' % (filedata['name'],
                                          filedata['version'],
                                          filedata['release'])] = un
                no = self._no_cache.setdefault(filedata['name'], set())
                no.add(un)
        return True

    UpdateMetadata.add_notice = add_notice


# Work around for:  https://bugzilla.redhat.com/show_bug.cgi?id=886240#c13
# Yum's UpdateMetadata.xml() is injecting an extra </pkglist> if an errata spans more than 1
# collection
# Our fix is to remove all but the last closing </pkglist>
def remove_extra_pkglist_closing_tag(self):
    # Assumes that the XML should be formated with only one <pkglist>...</pkglist>
    # Therefore all extra </pkglist> beyond the final closing tag are invalid
    orig_xml = YUM_UPDATE_MD_UPDATE_NOTICE_ORIG_XML_METHOD(self)
    num_closing_pkglist_tags = orig_xml.count("</pkglist>")
    fixed_xml = orig_xml.replace('</pkglist>', '', num_closing_pkglist_tags - 1)
    return fixed_xml


YUM_UPDATE_MD_UPDATE_NOTICE_ORIG_XML_METHOD = yum.update_md.UpdateNotice.xml
yum.update_md.UpdateNotice.xml = remove_extra_pkglist_closing_tag
# End of workaround for https://bugzilla.redhat.com/show_bug.cgi?id=886240#c13


def get_update_notices(path_to_updateinfo):
    """
    path_to_updateinfo:  path to updateinfo.xml

    Returns a list of dictionaries
    Dictionary is based on keys from yum.update_md.UpdateNotice
    """
    um = UpdateMetadata()
    um.add(path_to_updateinfo)
    notices = []
    for info in um.get_notices():
        notices.append(info.get_metadata())
    return notices


def get_errata(path_to_updateinfo):
    """
    @param path_to_updateinfo: path to updateinfo metadata xml file

    Returns a list of pulp.model.Errata objects
    Parses updateinfo xml file and converts yum.update_md.UpdateNotice
    objects to pulp.model.Errata objects
    """
    errata = []
    uinfos = get_update_notices(path_to_updateinfo)
    for u in uinfos:
        e = _translate_updatenotice_to_erratum(u)
        errata.append(e)
    return errata


def _translate_updatenotice_to_erratum(unotice):
    id = unotice['update_id']
    title = unotice['title']
    description = unotice['description']
    version = unotice['version']
    release = unotice['release']
    type = unotice['type']
    status = unotice['status']
    updated = unotice['updated']
    issued = unotice['issued']
    pushcount = unotice['pushcount']
    from_str = unotice['from']
    reboot_suggested = unotice['reboot_suggested']
    references = unotice['references']
    pkglist = unotice['pkglist']
    severity = ""
    if 'severity' in unotice:
        severity = unotice['severity']
    rights = ""
    if 'rights' in unotice:
        rights = unotice['rights']
    summary = ""
    if 'summary' in unotice:
        summary = unotice['summary']
    solution = ""
    if 'solution' in unotice:
        solution = unotice['solution']
    erratum = Errata(id, title, description, version, release, type,
                     status, updated, issued, pushcount, from_str, reboot_suggested,
                     references, pkglist, severity, rights, summary, solution)
    return erratum


class Errata(dict):
    """
    Errata object to represent software updates
    maps to yum.update_md.UpdateNotice fields
    """

    def __init__(self, id, title, description, version, release, type, status=u"",
                 updated=u"", issued=u"", pushcount=1, from_str=u"",
                 reboot_suggested=False, references=[], pkglist=[], severity=u"",
                 rights=u"", summary=u"", solution=u""):
        self.id = id
        self.title = title
        self.description = description
        self.version = version
        self.release = release
        self.type = type
        self.status = status
        self.updated = updated
        self.issued = issued
        if pushcount:
            self.pushcount = int(pushcount)
        else:
            self.pushcount = 1
        self.from_str = from_str
        self.reboot_suggested = reboot_suggested
        self.references = references
        self.pkglist = pkglist
        self.rights = rights
        self.severity = severity
        self.summary = summary
        self.solution = solution

    def __getattr__(self, attr):
        return self.get(attr, None)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def updateinfo(errata_units, save_location):
    um = UpdateMetadata()
    for e in errata_units:
        encode_epoch(e)
        un = UpdateNotice()

        _md = {
            'from': e.metadata['from'],
            'type': e.metadata['type'],
            'title': e.metadata['title'],
            'release': e.metadata.get('release', ''),
            'status': e.metadata['status'],
            'version': e.metadata['version'],
            'pushcount': e.metadata.get('pushcount', ''),
            'update_id': e.unit_key['id'],
            'issued': e.metadata['issued'],
            'updated': e.metadata.get('updated', ''),
            'description': e.metadata['description'],
            'references': e.metadata['references'],
            'pkglist': e.metadata['pkglist'],
            'reboot_suggested': e.metadata.get('reboot_suggested', False),
            'severity': e.metadata.get('severity', ''),
            'rights': e.metadata.get('rights', ''),
            'summary': e.metadata.get('summary', ''),
            'solution': e.metadata.get('solution', ''),
        }
        un._md = _md
        um.add_notice(un)

    if not um._notices:
        # nothing to do return
        return
    updateinfo_path = None
    try:
        updateinfo_path = "%s/%s" % (save_location, "updateinfo.xml")
        f = open(updateinfo_path, 'wt')
        try:
            um.xml(fileobj=f)
            log.info("updateinfo.xml generated and written to file %s" % updateinfo_path)
        finally:
            f.close()
    except Exception, e:
        log.error("Error writing updateinfo.xml to path %s: %s" % (updateinfo_path, e))
    return updateinfo_path


def encode_epoch(erratum):
    """
    This is a workaround for https://bugzilla.redhat.com/show_bug.cgi?id=1020415

    Yum forgot to call it's "to_xml" function on the "epoch" field only. Also,
    that function does not convert anything to XML. It only prepares the input
    for inclusion in an XML document, mostly by decoding it from unicode to a
    string. This is known to affect yum 3.4.3-111 and newer. Note that earlier
    builds of 3.4.3 did not have this problem; they did in fact change the
    code without bumping the version, which can cause confusion.

    The yum bug is being tracked here:
    https://bugzilla.redhat.com/show_bug.cgi?id=1020540

    :param erratum: an erratum whose package epochs should be converted to a
                    yum-friendly state.
    :type  erratum: pulp.plugins.model.Unit
    """
    for packages_dict in erratum.metadata['pkglist']:
        for package in packages_dict['packages']:
            if 'epoch' in package:
                # yum calls this on every other field except this one, which can
                # cause problems if there are non-ascii characters in published
                # XML file.
                package['epoch'] = to_xml(package['epoch'])
