import os
import shutil
from gettext import gettext as _
from collections import namedtuple

from pulp.plugins.util.publish_step import BasePublisher, PublishStep, UnitPublishStep
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.exceptions import InvalidValue

from pulp_rpm.common import constants
from pulp_rpm.common.ids import (
    TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_ENVIRONMENT, TYPE_ID_DISTRO, TYPE_ID_YUM_REPO_METADATA_FILE)
from pulp_rpm.yum_plugin import util
from pulp_rpm.plugins.importers.yum.parse.treeinfo import KEY_PACKAGEDIR
from . import configuration
from .metadata.filelists import FilelistsXMLFileContext
from .metadata.metadata import REPO_DATA_DIR_NAME
from .metadata.other import OtherXMLFileContext
from .metadata.prestodelta import PrestodeltaXMLFileContext
from .metadata.primary import PrimaryXMLFileContext
from .metadata.repomd import RepomdXMLFileContext
from .metadata.updateinfo import UpdateinfoXMLFileContext
from .metadata.package import PackageXMLFileContext


# -- constants -----------------------------------------------------------------

_LOG = util.getLogger(__name__)

# -- package fields ------------------------------------------------------------

PACKAGE_FIELDS = ['id', 'name', 'version', 'release', 'arch', 'epoch',
                  '_storage_path', 'checksum', 'checksumtype', 'repodata']

# -- publisher class -----------------------------------------------------------


class Publisher(BasePublisher):
    """
    Yum HTTP/HTTPS publisher class that is responsible for the actual publishing
    of a yum repository over HTTP and/or HTTPS.
    """

    def __init__(self, repo, publish_conduit, config):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        repomd_step = PublishRepoMetaDataStep()
        steps = [PublishDistributionStep(),
                 PublishRpmStep(),
                 PublishDrpmStep(),
                 PublishErrataStep(),
                 PublishCompsStep(),
                 PublishMetadataStep()]

        super(Publisher, self).__init__(repo, publish_conduit, config,
                                        initialize_steps=[repomd_step],
                                        process_steps=steps,
                                        finalize_steps=[repomd_step],
                                        post_process_steps=[PublishToMasterStep(),
                                                            PublishOverHttpStep(),
                                                            PublishOverHttpsStep(),
                                                            ClearOldMastersStep()])


class PublishRepoMetaDataStep(UnitPublishStep):
    """
    Step for managing overall repo metadata
    """

    def __init__(self):
        super(PublishRepoMetaDataStep, self).__init__(constants.PUBLISH_REPOMD_STEP, TYPE_ID_RPM)
        self.repomd_file_context = None
        self.checksum_type = None

    def initialize(self):
        """
        open the metadata context
        """
        self.checksum_type = configuration.get_repo_checksum_type(self.parent.conduit,
                                                                  self.parent.config)
        self.repomd_file_context = RepomdXMLFileContext(self.get_working_dir(), self.checksum_type)
        self.repomd_file_context.initialize()

    def finalize(self):
        """
        Close the metadata context
        """
        if self.repomd_file_context:
            self.repomd_file_context.finalize()


class PublishRpmStep(UnitPublishStep):
    """
    Step for publishing RPM & SRPM units
    """

    def __init__(self):
        super(PublishRpmStep, self).__init__(constants.PUBLISH_RPMS_STEP, TYPE_ID_RPM)
        self.description = _('Publishing RPMs')
        self.file_lists_context = None
        self.other_context = None
        self.primary_context = None

    def get_unit_generator(self):
        """
        Create a generator that returns both SRPM and RPM units
        """
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_RPM, TYPE_ID_SRPM],
                                           unit_fields=PACKAGE_FIELDS)
        return self.parent.conduit.get_units(criteria, as_generator=True)

    def initialize(self):
        """
        Create each of the three metadata contexts required for publishing RPM & SRPM
        """
        total = self._get_total([TYPE_ID_RPM, TYPE_ID_SRPM])
        checksum_type = self.get_step(constants.PUBLISH_REPOMD_STEP).checksum_type
        self.file_lists_context = FilelistsXMLFileContext(self.get_working_dir(), total,
                                                          checksum_type)
        self.other_context = OtherXMLFileContext(self.get_working_dir(), total, checksum_type)
        self.primary_context = PrimaryXMLFileContext(self.get_working_dir(), total, checksum_type)
        for context in (self.file_lists_context, self.other_context, self.primary_context):
            context.initialize()

    def finalize(self):
        """
        Close each context and write it to the repomd file
        """
        repomd = self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context

        if self.file_lists_context:
            self.file_lists_context.finalize()
            repomd.add_metadata_file_metadata('filelists',
                                              self.file_lists_context.metadata_file_path,
                                              self.file_lists_context.checksum)
        if self.other_context:
            self.other_context.finalize()
            repomd.add_metadata_file_metadata('other', self.other_context.metadata_file_path,
                                              self.other_context.checksum)

        if self.primary_context:
            self.primary_context.finalize()
            repomd.add_metadata_file_metadata('primary', self.primary_context.metadata_file_path,
                                              self.primary_context.checksum)

    def process_unit(self, unit):
        """
        Link the unit to the content directory and the package_dir

        :param unit: The unit to process
        :type unit: pulp.plugins.model.Unit
        """
        source_path = unit.storage_path
        relative_path = util.get_relpath_from_unit(unit)
        destination_path = os.path.join(self.get_working_dir(), relative_path)
        self._create_symlink(source_path, destination_path)
        package_dir = self.get_step(constants.PUBLISH_DISTRIBUTION_STEP).package_dir
        if package_dir:
            destination_path = os.path.join(package_dir, relative_path)
            self._create_symlink(source_path, destination_path)

        for context in (self.file_lists_context, self.other_context, self.primary_context):
            context.add_unit_metadata(unit)


class PublishMetadataStep(UnitPublishStep):
    """
    Publish extra metadata files that are copied from another repo and not generated
    """

    def __init__(self):
        super(PublishMetadataStep, self).__init__(constants.PUBLISH_METADATA_STEP,
                                                  TYPE_ID_YUM_REPO_METADATA_FILE)
        self.description = _('Publishing Metadata.')

    def process_unit(self, unit):
        """
        Copy the metadata file into place and add it tot he repomd file.

        :param unit: The unit to process
        :type unit: pulp.plugins.model.Unit
        """
        # Copy the file to the location on disk where the published repo is built
        publish_location_relative_path = os.path.join(self.get_working_dir(),
                                                      REPO_DATA_DIR_NAME)

        metadata_file_name = os.path.basename(unit.storage_path)
        link_path = os.path.join(publish_location_relative_path, metadata_file_name)
        self._create_symlink(unit.storage_path, link_path)

        # Add the proper relative reference to the metadata file to repomd
        self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context.\
            add_metadata_file_metadata(unit.unit_key['data_type'], link_path)


class PublishDrpmStep(UnitPublishStep):
    """
    Publish Delta RPMS
    """

    def __init__(self):
        super(PublishDrpmStep, self).__init__(constants.PUBLISH_DELTA_RPMS_STEP, TYPE_ID_DRPM)
        self.description = _('Publishing Delta RPMs')
        self.context = None

    def initialize(self):
        """
        Initialize the PrestoDelta metadata file
        """
        checksum_type = self.get_step(constants.PUBLISH_REPOMD_STEP).checksum_type
        self.context = PrestodeltaXMLFileContext(self.get_working_dir(), checksum_type)
        self.context.initialize()

    def process_unit(self, unit):
        """
        Link the unit to the drpm content directory and the package_dir

        :param unit: The unit to process
        :type unit: pulp.plugins.model.Unit
        """
        source_path = unit.storage_path
        relative_path = os.path.join('drpms', util.get_relpath_from_unit(unit))
        destination_path = os.path.join(self.get_working_dir(), relative_path)
        self._create_symlink(source_path, destination_path)
        package_dir = self.get_step(constants.PUBLISH_DISTRIBUTION_STEP).package_dir
        if package_dir:
            destination_path = os.path.join(package_dir, relative_path)
            self._create_symlink(source_path, destination_path)
        self.context.add_unit_metadata(unit)

    def finalize(self):
        """
        Close & finalize each of the metadata files
        """
        if self.context:
            self.context.finalize()
            self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context.\
                add_metadata_file_metadata('prestodelta', self.context.metadata_file_path,
                                           self.context.checksum)


class PublishErrataStep(UnitPublishStep):
    """
    Publish all errata
    """
    def __init__(self):
        super(PublishErrataStep, self).__init__(constants.PUBLISH_ERRATA_STEP, TYPE_ID_ERRATA)
        self.context = None
        self.description = _('Publishing Errata')

    def initialize(self):
        """
        Initialize the UpdateInfo file and set the method used to process the unit to the
        one that is built into the UpdateinfoXMLFileContext
        """
        checksum_type = self.get_step(constants.PUBLISH_REPOMD_STEP).checksum_type
        self.context = UpdateinfoXMLFileContext(self.get_working_dir(), checksum_type)
        self.context.initialize()
        # set the self.process_unit method to the corresponding method on the
        # UpdateInfoXMLFileContext as there is no other processing to be done for each unit.
        self.process_unit = self.context.add_unit_metadata

    def finalize(self):
        """
        Finalize and write to disk the metadata and add the updateinfo file to the repomd
        """
        if self.context:
            self.context.finalize()
            self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context.\
                add_metadata_file_metadata('updateinfo', self.context.metadata_file_path,
                                           self.context.checksum)


class PublishCompsStep(UnitPublishStep):
    def __init__(self):
        super(PublishCompsStep, self).__init__(constants.PUBLISH_COMPS_STEP,
                                               [TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY,
                                                TYPE_ID_PKG_ENVIRONMENT])
        self.comps_context = None
        self.description = _('Publishing Comps file')

    def get_unit_generator(self):
        """
        Returns a generator of Named Tuples containing the original unit and the
        processing method that will be used to process that particular unit.
        """

        # set the process unit method to categories
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_PKG_CATEGORY])
        category_generator = self.parent.conduit.get_units(criteria, as_generator=True)

        UnitProcessor = namedtuple('UnitProcessor', 'unit process')
        for category in category_generator:
            yield UnitProcessor(category, self.comps_context.add_package_category_unit_metadata)

        # set the process unit method to groups
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_PKG_GROUP])
        groups_generator = self.parent.conduit.get_units(criteria, as_generator=True)
        for group in groups_generator:
            yield UnitProcessor(group, self.comps_context.add_package_group_unit_metadata)

        # set the process unit method to environments
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_PKG_ENVIRONMENT])
        groups_generator = self.parent.conduit.get_units(criteria, as_generator=True)
        for group in groups_generator:
            yield UnitProcessor(group, self.comps_context.add_package_environment_unit_metadata)

    def process_unit(self, unit):
        """
        Process each unit created by the generator using the associated
        process command
        """
        unit.process(unit.unit)

    def initialize(self):
        """
        Initialize all metadata associated with the comps file
        """
        checksum_type = self.get_step(constants.PUBLISH_REPOMD_STEP).checksum_type
        self.comps_context = PackageXMLFileContext(self.get_working_dir(), checksum_type)
        self.comps_context.initialize()

    def finalize(self):
        """
        Finalize all metadata associated with the comps file
        """
        if self.comps_context:
            self.comps_context.finalize()
            self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context.\
                add_metadata_file_metadata('group', self.comps_context.metadata_file_path,
                                           self.comps_context.checksum)


class PublishDistributionStep(UnitPublishStep):
    """
    Publish distribution files associated with the anaconda installer
    """

    def __init__(self):
        """
        initialize and set the package_dir to None as it is referenced by other
        plugins even if it is not specified
        """
        super(PublishDistributionStep, self).__init__(constants.PUBLISH_DISTRIBUTION_STEP,
                                                      TYPE_ID_DISTRO)
        self.package_dir = None
        self.description = _('Publishing Distribution files')

    def initialize(self):
        """
        When initializing the metadata verify that only one distribution exists
        """
        if self._get_total() > 1:
            msg = _('Error publishing repository %(repo)s.  '
                    'More than one distribution found.') % {'repo': self.parent.repo.id}
            _LOG.debug(msg)
            raise Exception(msg)

    def process_unit(self, unit):
        """
        Process the distribution unit

        :param unit: The unit to process
        :type unit: Unit
        """
        self._publish_distribution_treeinfo(unit)

        # create the Packages directory required for RHEL 5
        self._publish_distribution_packages_link(unit)

        # Link any files referenced by the unit - This must happen after
        # creating the packages directory in case the packages directory
        # has to replace a symlink with a hard directory
        self._publish_distribution_files(unit)

    def _publish_distribution_treeinfo(self, distribution_unit):
        """
        For a given AssociatedUnit for a distribution.  Create the links for the treeinfo file
        back to the treeinfo in the content.

        :param distribution_unit: The unit for the distribution from which the list
                                  of files to be published should be pulled from.
        :type distribution_unit: AssociatedUnit
        """
        distribution_unit_storage_path = distribution_unit.storage_path
        src_treeinfo_path = None
        treeinfo_file_name = None
        for treeinfo in constants.TREE_INFO_LIST:
            test_treeinfo_path = os.path.join(distribution_unit_storage_path, treeinfo)
            if os.path.exists(test_treeinfo_path):
                # we found the treeinfo file
                src_treeinfo_path = test_treeinfo_path
                treeinfo_file_name = treeinfo
                break
        if src_treeinfo_path is not None:
            # create a symlink from content location to repo location.
            symlink_treeinfo_path = os.path.join(self.get_working_dir(), treeinfo_file_name)
            _LOG.debug("creating treeinfo symlink from %s to %s" % (src_treeinfo_path,
                                                                    symlink_treeinfo_path))
            self._create_symlink(src_treeinfo_path, symlink_treeinfo_path)

    def _publish_distribution_files(self, distribution_unit):
        """
        For a given AssociatedUnit for a distribution.  Create all the links back to the
        content units that are referenced within the 'files' metadata section of the unit.

        :param distribution_unit: The unit for the distribution from which the list
                                  of files to be published should be pulled from.
        :type distribution_unit: AssociatedUnit
        """
        if 'files' not in distribution_unit.metadata:
            msg = "No distribution files found for unit %s" % distribution_unit
            _LOG.warning(msg)
            return

        distro_files = distribution_unit.metadata['files']
        total_files = len(distro_files)
        _LOG.debug("Found %s distribution files to symlink" % total_files)

        source_path_dir = distribution_unit.storage_path
        symlink_dir = self.get_working_dir()
        for dfile in distro_files:
            source_path = os.path.join(source_path_dir, dfile['relativepath'])
            if source_path.endswith('repomd.xml'):
                continue
            symlink_path = os.path.join(symlink_dir, dfile['relativepath'])
            self._create_symlink(source_path, symlink_path)

    def _publish_distribution_packages_link(self, distribution_unit):
        """
        Create a Packages directory in the repo that is a sym link back to the root directory
        of the repository.  This is required for compatibility with RHEL 5.

        Also create the directory that is specified by packagesdir section in the config file

        :param distribution_unit: The unit for the distribution from which the list
                                  of files to be published should be pulled from.
        :type distribution_unit: AssociatedUnit
        """
        symlink_dir = self.get_working_dir()
        package_path = None

        if KEY_PACKAGEDIR in distribution_unit.metadata and \
           distribution_unit.metadata[KEY_PACKAGEDIR] is not None:
            # The packages_dir is a relative directory that exists underneath the repo directory
            # Verify that this directory is valid.
            package_path = os.path.join(symlink_dir, distribution_unit.metadata[KEY_PACKAGEDIR])
            real_symlink_dir = os.path.realpath(symlink_dir)
            real_package_path = os.path.realpath(package_path)
            common_prefix = os.path.commonprefix([real_symlink_dir, real_package_path])
            if not common_prefix.startswith(real_symlink_dir):
                # the specified package path is not contained within the directory
                # raise a validation exception
                msg = _('Error publishing repository: %(repo)s.  The treeinfo file specified a '
                        'packagedir \"%(packagedir)s\" that is not contained within the repository'
                        % {'repo': self.parent.repo.id, 'packagedir': self.package_dir})
                _LOG.info(msg)
                raise InvalidValue(KEY_PACKAGEDIR)

            self.package_dir = real_package_path
            if os.path.islink(package_path):
                # a package path exists as a symlink we are going to remove it since
                # the _create_symlink will create a real directory
                os.unlink(package_path)

        if package_path is not os.path.join(symlink_dir, 'Packages'):
            # create the Packages symlink to the content dir, in the content dir
            packages_symlink_path = os.path.join(symlink_dir, 'Packages')
            self._create_symlink("./", packages_symlink_path)


class PublishToMasterStep(PublishStep):

    def __init__(self, step=constants.PUBLISH_TO_MASTER_STEP):
        """
        Initialize and set the ID of the step
        """
        super(PublishToMasterStep, self).__init__(step)
        self.description = _("Copying files to master directory")

    def process_main(self):
        """
        Create & populate the master publish directory
        """
        master_publish_dir = configuration.get_master_publish_dir(self.parent.repo)

        # Use the timestamp as the name of the current master repository
        # directory. This allows us to identify when these were created as well
        # as having more than one side-by-side during the publishing process.
        master_repo_directory = os.path.join(master_publish_dir, self.parent.timestamp)

        _LOG.debug('Copying tree from %s to %s' % (self.get_working_dir(), master_repo_directory))

        shutil.copytree(self.get_working_dir(), master_repo_directory, symlinks=True)


class ClearOldMastersStep(PublishStep):

    def __init__(self, step=constants.PUBLISH_CLEAR_OLD_MASTERS):
        """
        Initialize and set the ID of the step
        """
        super(ClearOldMastersStep, self).__init__(step)

    def process_main(self):
        """
        Clear out the old master directories
        """
        master_publish_dir = configuration.get_master_publish_dir(self.parent.repo)
        self._clear_directory(master_publish_dir, skip_list=[self.parent.timestamp])


class PublishOverHttpStep(PublishStep):
    """
    Publish http repo directory if configured
    """
    def __init__(self, step=constants.PUBLISH_OVER_HTTP_STEP):
        """
        Initialize and set the ID of the step
        """
        super(PublishOverHttpStep, self).__init__(step)
        self.description = _('Publishing via http')

    def is_skipped(self):
        """
        Check whether publishing over http is enabled
        """
        return not self.parent.config.get('http')

    def _get_publish_dir(self):
        """
        Get the directory to publish to.  This is so that https can use the same base class
        """
        return configuration.get_http_publish_dir(self.parent.config)

    def process_main(self):
        """
        Publish a directory from the repo to a target directory.
        """
        root_publish_dir = self._get_publish_dir()

        # Find the location of the master repository tree structure
        master_publish_dir = os.path.join(configuration.get_master_publish_dir(self.parent.repo),
                                          self.parent.timestamp)

        # Find the location of the published repository tree structure
        repo_relative_dir = configuration.get_repo_relative_path(self.parent.repo,
                                                                 self.parent.config)
        repo_publish_dir = os.path.join(root_publish_dir, repo_relative_dir)
        # Without the trailing '/'
        if repo_publish_dir.endswith('/'):
            repo_publish_dir = repo_publish_dir[:-1]

        # Create the parent directory of the published repository tree, if needed
        repo_publish_dir_parent = repo_publish_dir.rsplit('/', 1)[0]
        if not os.path.exists(repo_publish_dir_parent):
            os.makedirs(repo_publish_dir_parent, 0750)

        # Create a temporary symlink in the parent of the published directory tree
        tmp_link_name = os.path.join(repo_publish_dir_parent, self.parent.timestamp)
        os.symlink(master_publish_dir, tmp_link_name)

        # Rename the symlink to the official published repository directory name.
        # This has two desirable effects:
        # 1. it will overwrite an existing link, if it's there
        # 2. the operation is atomic, instantly changing the published directory
        # NOTE: it's not easy (possible?) to directly edit the target of a symlink
        os.rename(tmp_link_name, repo_publish_dir)

        # (Re)generate the listing files
        util.generate_listing_files(root_publish_dir, repo_publish_dir)


class PublishOverHttpsStep(PublishOverHttpStep):
    """
    Publish https repo directory if configured
    """
    def __init__(self):
        super(PublishOverHttpsStep, self).__init__(constants.PUBLISH_OVER_HTTPS_STEP)
        self.description = _('Publishing via https')

    def is_skipped(self):
        """
        Check whether publishing over HTTPS is enabled
        """
        return not self.parent.config.get('https')

    def _get_publish_dir(self):
        """
        For the units return the https publish directory
        """
        return configuration.get_https_publish_dir(self.parent.config)
