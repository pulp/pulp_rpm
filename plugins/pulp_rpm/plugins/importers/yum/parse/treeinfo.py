import ConfigParser
import logging
import os
import shutil
import tempfile

from gettext import gettext as _
from lxml import etree as ET
from urlparse import urljoin

from mongoengine import Q

from nectar.listener import AggregatingEventListener
from nectar.request import DownloadRequest

from pulp.plugins.util import verification
from pulp.server.db.model import LazyCatalogEntry, RepositoryContentUnit
from pulp.server.exceptions import PulpCodedValidationException
from pulp.server.controllers import repository as repo_controller

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.db.models import Distribution
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.importers.yum.listener import DistFileListener
from pulp_rpm.plugins.importers.yum.repomd import nectar_factory


SECTION_GENERAL = 'general'
SECTION_STAGE2 = 'stage2'
SECTION_CHECKSUMS = 'checksums'
KEY_PACKAGEDIR = 'packagedir'
KEY_TIMESTAMP = 'timestamp'
KEY_DISTRIBUTION_CONTEXT = 'distribution_context'
RELATIVE_PATH = 'relativepath'
CHECKSUM = 'checksum'
CHECKSUM_TYPE = 'checksumtype'

_logger = logging.getLogger(__name__)


class DownloadFailed(Exception):
    pass


class DistSync(object):
    """
    :ivar parent: The parent sync object.
    :type parent: pulp_rpm.plugins.importers.yum.sync.RepoSync
    :ivar feed: The feed url.
    :type feed: str
    """

    def __init__(self, parent, feed):
        """
        :param parent: The parent sync object.
        :type parent: pulp_rpm.plugins.importers.yum.sync.RepoSync
        :param feed: The feed url.
        :type feed: str
        """
        self.parent = parent
        self.feed = feed

    @property
    def nectar_config(self):
        """
        The nectar configuration used for downloading.

        :return: The nectar configuration.
        :rtype: nectar.config.DownloaderConfig
        """
        return self.parent.nectar_config

    @property
    def working_dir(self):
        """
        The working directory used for downloads.

        :return: The absolute path to the directory.
        :type: str
        """
        return self.parent.working_dir

    @property
    def progress_report(self):
        """
        The distribution progress report.

        :return: The progress report.
        :type: pulp_rpm.plugins.importers.yum.report.DistributionReport
        """
        return self.parent.distribution_report

    @property
    def repo(self):
        """
        The repository being synchronized.

        :return: A repository
        :rtype: pulp.server.db.model.Repository
        """
        return self.parent.repo

    @property
    def download_deferred(self):
        """
        Test the download policy to determine if downloading is deferred.

        :return: True if deferred.
        :rtype: bool
        """
        return self.parent.download_deferred

    def set_progress(self):
        """
        Send the progress report.
        """
        self.parent.set_progress()

    def run(self):
        """
        Look for a distribution in the target repo and sync it if found
        """
        tmp_dir = tempfile.mkdtemp(dir=self.working_dir)
        try:
            self._run(tmp_dir)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _run(self, tmp_dir):
        """
        Look for a distribution in the target repo and sync it if found

        :param tmp_dir: The absolute path to the temporary directory
        :type tmp_dir: str
        """
        treeinfo_path = self.get_treefile(tmp_dir)
        if not treeinfo_path:
            _logger.debug(_('No treeinfo found'))
            return

        try:
            unit, files = self.parse_treeinfo_file(treeinfo_path)
        except ValueError:
            _logger.error(_('could not parse treeinfo'))
            self.progress_report['state'] = constants.STATE_FAILED
            return

        existing_units = repo_controller.find_repo_content_units(
            self.repo,
            repo_content_unit_q=Q(unit_type_id=ids.TYPE_ID_DISTRO),
            yield_content_unit=True)

        existing_units = list(existing_units)

        # Continue only when the distribution has changed.
        if len(existing_units) == 1 and \
                self.existing_distribution_is_current(existing_units[0], unit):
            _logger.debug(_('upstream distribution unchanged; skipping'))
            return

        # Process the distribution
        dist_files = self.process_distribution(tmp_dir)
        files.extend(dist_files)

        self.update_unit_files(unit, files)

        # Download distribution files
        if not self.download_deferred:
            try:
                downloaded = self.download_files(tmp_dir, files)
            except DownloadFailed:
                # All files must be downloaded to continue.
                return
        else:
            unit.downloaded = False
            downloaded = []

        # Save the unit.
        unit.save()

        # Update deferred downloading catalog
        self.update_catalog_entries(unit, files)

        # The treeinfo file is always imported into platform
        # # storage regardless of the download policy
        unit.safe_import_content(treeinfo_path, os.path.basename(treeinfo_path))

        # The downloaded files are imported into platform storage.
        for destination, location in downloaded:
            unit.safe_import_content(destination, location)

        # Associate the unit.
        repo_controller.associate_single_unit(self.repo, unit)

        # find any old distribution units and remove them. See BZ #1150714
        for existing_unit in existing_units:
            if existing_unit == unit:
                continue
            msg = _('Removing out-of-date distribution unit {k} for repo {r}')
            _logger.info(msg.format(k=existing_unit.unit_key, r=self.repo.repo_id))
            qs = RepositoryContentUnit.objects.filter(
                repo_id=self.repo.repo_id,
                unit_id=existing_unit.id)
            qs.delete()

    def update_catalog_entries(self, unit, files):
        """
        Update entries to the deferred downloading (lazy) catalog.

        :param unit: A distribution model object.
        :type unit: pulp_rpm.plugins.db.models.Distribution
        :param files: List of distribution files.
        :type files: list
        """
        for _file in files:
            root = unit.storage_path
            entry = LazyCatalogEntry()
            entry.path = os.path.join(root, _file[RELATIVE_PATH])
            entry.url = urljoin(self.feed, _file[RELATIVE_PATH])
            entry.unit_id = unit.id
            entry.unit_type_id = unit.type_id
            entry.importer_id = str(self.parent.conduit.importer_object_id)
            entry.save_revision()

    @staticmethod
    def update_unit_files(unit, files):
        """
        Update the *files* list on the unit.

        :param unit: A distribution model object.
        :type unit: pulp_rpm.plugins.db.models.Distribution
        :param files: List of distribution files.
        :type files: list
        """
        _list = []
        if not isinstance(unit.files, list):
            _list = list(unit.files)
        for _file in files:
            if _file[CHECKSUM_TYPE] is not None:
                _file[CHECKSUM_TYPE] = verification.sanitize_checksum_type(_file[CHECKSUM_TYPE])
            _list.append({
                RELATIVE_PATH: _file[RELATIVE_PATH],
                CHECKSUM: _file[CHECKSUM],
                CHECKSUM_TYPE: _file[CHECKSUM_TYPE]})
        unit.files = _list

    def download_files(self, tmp_dir, files):
        """
        Download distribution files.

        :param tmp_dir: The absolute to where the downloaded files.
        :type tmp_dir: str
        :param files: List of distribution dictionary files.
        :type files: list
        :return: generator of: (destination, location)
            The *destination* is the absolute path to the downloaded file.
            The *location* is the relative path within the tmp_dir.
        :rtype: generator
        :raise DownloadFailed: if any of the downloads fail.
        """
        listener = DistFileListener(self)
        self.progress_report.set_initial_values(len(files))
        downloader = nectar_factory.create_downloader(self.feed, self.nectar_config, listener)
        requests = (self.file_to_download_request(f, tmp_dir) for f in files)
        downloader.download(requests)
        if len(listener.failed_reports):
            _logger.error(_('some distro file downloads failed'))
            self.progress_report['state'] = constants.STATE_FAILED
            self.progress_report['error_details'] = [
                (fail.url, fail.error_report) for fail in listener.failed_reports
            ]
            raise DownloadFailed()
        for report in listener.succeeded_reports:
            location = report.destination.lstrip(tmp_dir)
            yield report.destination, location.lstrip('/')

    @staticmethod
    def process_successful_download_reports(unit, reports):
        """
        Once downloading is complete, add information about each file to this
        model instance. This is required before saving the new unit.

        :param unit:    A distribution model object.
        :type  unit:    pulp_rpm.plugins.db.models.Distribution
        :param reports: list of successful pulp.common.download.report.DownloadReport
        :type  reports: list
        """
        files = []
        if not isinstance(unit.files, list):
            files = list(unit.files)
        for report in reports:
            _file = report.data
            if _file[CHECKSUM_TYPE] is not None:
                _file[CHECKSUM_TYPE] = verification.sanitize_checksum_type(_file[CHECKSUM_TYPE])
            files.append({
                RELATIVE_PATH: _file[RELATIVE_PATH],
                CHECKSUM: _file[CHECKSUM],
                CHECKSUM_TYPE: _file[CHECKSUM_TYPE]})
        unit.files = files

    @staticmethod
    def existing_distribution_is_current(existing_unit, unit):
        """
        Determines if the remote model is newer than the existing unit we have in
        the database. This uses the timestamp attribute of each's treeinfo file to
        make that determination.

        :param existing_unit: unit that currently exists in the repo
        :type existing_unit: pulp_rpm.plugins.db.models.Distribution
        :param unit: This model's unit key will be searched for in the DB
        :type unit: pulp_rpm.plugins.db.models.Distribution
        :return: False if model's timestamp is greater than existing_unit's timestamp,
            or if that comparison cannot be made because timestamp data is
            missing. Otherwise, True.
        :rtype: bool
        """
        existing_timestamp = existing_unit.timestamp
        remote_timestamp = unit.timestamp
        if existing_timestamp is None or remote_timestamp is None:
            _logger.debug(_('treeinfo timestamp missing; will fetch upstream distribution'))
            return False
        return remote_timestamp <= existing_timestamp

    def file_to_download_request(self, file_dict, tmp_dir):
        """
        Takes information about a file described in a treeinfo file and turns that
        into a download request suitable for use with nectar.

        :param file_dict: A dict of: {relativepath: <str>, ...}
        :type file_dict: dict
        :param tmp_dir: The absolute to where the downloaded files.
        :type tmp_dir: str
        :return: new download request
        :rtype: nectar.request.DownloadRequest
        """
        destination = os.path.join(tmp_dir, file_dict[RELATIVE_PATH])
        # make directories such as "images"
        if not os.path.exists(os.path.dirname(destination)):
            os.makedirs(os.path.dirname(destination))
        return DownloadRequest(
            os.path.join(self.feed, file_dict[RELATIVE_PATH]),
            destination,
            file_dict)

    @staticmethod
    def strip_treeinfo_repomd(treeinfo_path):
        """
        strip repomd checksums from the treeinfo. These cause two issues:
          * pulp thinks repomd.xml is content and not metadata if it's listed here
          * pulp regenerates the repomd.xml file anyway, which would cause the
            listed checksum to be wrong

        :param treeinfo_path: The path to the on-disk treeinfo file
        :type treeinfo_path: str
        """
        # read entire treeinfo, strip entry we don't want, and replace with our new treeinfo
        with open(treeinfo_path, 'r+') as f:
            original_treeinfo_data = f.readlines()
            new_treeinfo_data = []
            for line in original_treeinfo_data:
                if not line.startswith('repodata/repomd.xml = '):
                    new_treeinfo_data.append(line)
            f.seek(0)
            f.writelines(new_treeinfo_data)
            # truncate file to current position before closing
            f.truncate()

    def get_treefile(self, tmp_dir):
        """
        Download the treefile and return its full path on disk, or None if not found

        :param tmp_dir: The absolute path to the temporary directory
        :type tmp_dir: str
        :return: The absolute path to treefile on disk, or None if not found
        :rtype: str or None
        """
        for filename in constants.TREE_INFO_LIST:
            path = os.path.join(tmp_dir, filename)
            url = os.path.join(self.feed, filename)
            request = DownloadRequest(url, path)
            listener = AggregatingEventListener()
            downloader = nectar_factory.create_downloader(self.feed, self.nectar_config, listener)
            downloader.download([request])
            if len(listener.succeeded_reports) == 1:
                # bz 1095829
                self.strip_treeinfo_repomd(path)
                return path

    def process_distribution(self, tmp_dir):
        """
        Get the pulp_distribution.xml file from the server and if it exists download all the
        files it references to add them to the distribution unit.

        :param tmp_dir: The absolute path to the temporary directory
        :type tmp_dir: str
        :return: A list of file dictionaries
        :rtype: list
        """
        # Get the Distribution file
        result = self.get_distribution_file(tmp_dir)
        files = []
        # If there is a Distribution file - parse it and add all files to the file_list
        if result:
            xsd = os.path.join(constants.USR_SHARE_DIR, 'pulp_distribution.xsd')
            schema_doc = ET.parse(xsd)
            xmlschema = ET.XMLSchema(schema_doc)
            try:
                tree = ET.parse(result)
                xmlschema.assertValid(tree)
            except Exception, e:
                raise PulpCodedValidationException(validation_exceptions=[
                    PulpCodedValidationException(
                        error_code=error_codes.RPM1001,
                        feed=self.feed,
                        validation_exceptions=[e])])

            # This is broken and best I can tell - not used.
            # model.metadata[constants.CONFIG_KEY_DISTRIBUTION_XML_FILE] = \
            #     constants.DISTRIBUTION_XML

            # parse the distribution file and add all the files to the download request
            root = tree.getroot()
            for file_element in root.findall('file'):
                relative_path = file_element.text
                files.append({
                    RELATIVE_PATH: relative_path,
                    CHECKSUM: None,
                    CHECKSUM_TYPE: None,
                })

            # Add the distribution file to the list of files
            files.append({
                RELATIVE_PATH: constants.DISTRIBUTION_XML,
                CHECKSUM: None,
                CHECKSUM_TYPE: None,
            })
        return files

    def get_distribution_file(self, tmp_dir):
        """
        Download the pulp_distribution.xml and return its full path on disk, or None if not found

        :param tmp_dir: The absolute path to the temporary directory
        :type tmp_dir: str
        :return: The absolute path to distribution file on disk, or None if not found
        :rtype: str or None
        """
        filename = constants.DISTRIBUTION_XML
        path = os.path.join(tmp_dir, filename)
        url = os.path.join(self.feed, filename)
        request = DownloadRequest(url, path)
        listener = AggregatingEventListener()
        downloader = nectar_factory.create_downloader(self.feed, self.nectar_config, listener)
        downloader.download([request])
        if len(listener.succeeded_reports) == 1:
            return path
        return None

    @staticmethod
    def parse_treeinfo_file(path):
        """
        The treefile seems to be approximately in INI format, which can be read
        by the standard library's ConfigParser.

        :param path: The absolute path to the treefile
        :return: instance of Distribution model, and a list of dicts
            describing the distribution's files
        :rtype: (pulp_rpm.plugins.db.models.Distribution, list of dict)
        """
        parser = ConfigParser.RawConfigParser()
        # the default implementation of this method makes all option names lowercase,
        # which we don't want. This is the suggested solution in the python.org docs.
        parser.optionxform = str
        with open(path) as fp:
            try:
                parser.readfp(fp)
            except ConfigParser.ParsingError:
                # wouldn't need this if ParsingError subclassed ValueError.
                raise ValueError(_('could not parse treeinfo file'))

        # apparently the 'variant' is optional. for example, it does not appear
        # in the RHEL 5.9 treeinfo file. This is how the previous importer
        # handled that.
        try:
            variant = parser.get(SECTION_GENERAL, 'variant')
        except ConfigParser.NoOptionError:
            variant = None
        try:
            packagedir = parser.get(SECTION_GENERAL, KEY_PACKAGEDIR)
        except ConfigParser.NoOptionError:
            packagedir = None

        try:
            new_dist = Distribution(
                family=parser.get(SECTION_GENERAL, 'family'),
                variant=variant,
                version=parser.get(SECTION_GENERAL, 'version'),
                arch=parser.get(SECTION_GENERAL, 'arch'),
                packagedir=packagedir,
                timestamp=float(parser.get(SECTION_GENERAL, KEY_TIMESTAMP))
            )
            # Look for an existing distribution
            existing_dist = Distribution.objects.filter(
                family=new_dist.family,
                variant=new_dist.variant,
                version=new_dist.version,
                arch=new_dist.arch
            ).first()
            if existing_dist:
                # update with the new information:
                existing_dist.packagedir = packagedir
                existing_dist.timestamp = new_dist.timestamp
                unit = existing_dist
            else:
                unit = new_dist
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            raise ValueError('invalid treefile: could not find unit key components')

        files = {}
        # this section is likely to have all the files we care about listed with
        # checksums. But, it might not. Other sections checked below will only add
        # files to the "files" dict if they are not already present. For those cases,
        # there will not be checksums available.
        if parser.has_section(SECTION_CHECKSUMS):
            for item in parser.items(SECTION_CHECKSUMS):
                relativepath = item[0]
                checksumtype, checksum = item[1].split(':')
                checksumtype = verification.sanitize_checksum_type(checksumtype)
                files[relativepath] = {
                    RELATIVE_PATH: relativepath,
                    CHECKSUM: checksum,
                    CHECKSUM_TYPE: checksumtype
                }
        for section_name in parser.sections():
            if section_name.startswith('images-') or section_name == SECTION_STAGE2:
                for item in parser.items(section_name):
                    if item[1] not in files:
                        relativepath = item[1]
                        files[relativepath] = {
                            RELATIVE_PATH: relativepath,
                            CHECKSUM: None,
                            CHECKSUM_TYPE: None,
                        }

        return unit, files.values()
