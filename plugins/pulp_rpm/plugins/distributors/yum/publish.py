from collections import namedtuple
import copy
from gettext import gettext as _
import os
import subprocess

from pulp.common import dateutils
from pulp.common.compat import json
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.util.publish_step import PublishStep, UnitPublishStep, CopyDirectoryStep
from pulp.plugins.util.publish_step import AtomicDirectoryPublishStep
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.managers.repo.query import RepoQueryManager
import pulp.server.managers.repo._common as common_utils
from pulp.server.exceptions import InvalidValue, PulpCodedException

from pulp_rpm.common import constants
from pulp_rpm.common.ids import (
    TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_ENVIRONMENT, TYPE_ID_DISTRO, TYPE_ID_YUM_REPO_METADATA_FILE)
from pulp_rpm.yum_plugin import util
from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.plugins.distributors.export_distributor import generate_iso
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


logger = util.getLogger(__name__)
PACKAGE_FIELDS = ['id', 'name', 'version', 'release', 'arch', 'epoch',
                  '_storage_path', 'checksum', 'checksumtype', 'repodata']


class BaseYumRepoPublisher(PublishStep):
    """
    Yum HTTP/HTTPS publisher class that is responsible for the actual publishing
    of a yum repository over HTTP and/or HTTPS.
    """

    def __init__(self, repo, publish_conduit, config, distributor_type, association_filters=None):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :param distributor_type: The type of the distributor that is being published
        :type distributor_type: str
        :param association_filters: Any filters to be applied to the list of RPMs being published,
                                    See pulp.server.db.model.criteria.UnitAssociationCriteria
                                    for details on what can be included in the association_filters
        :type association_filters: dict

        """
        super(BaseYumRepoPublisher, self).__init__(constants.PUBLISH_REPO_STEP, repo,
                                                   publish_conduit, config,
                                                   distributor_type=distributor_type)

        self.repomd_file_context = None
        self.checksum_type = None

        self.add_child(InitRepoMetadataStep())
        dist_step = PublishDistributionStep()
        self.add_child(dist_step)
        self.rpm_step = PublishRpmStep(dist_step, association_filters=association_filters)
        self.add_child(self.rpm_step)
        self.add_child(PublishDrpmStep(dist_step))
        self.add_child(PublishErrataStep())
        self.add_child(PublishCompsStep())
        self.add_child(PublishMetadataStep())
        self.add_child(CloseRepoMetadataStep())
        self.add_child(GenerateSqliteForRepoStep(self.get_working_dir()))

    def get_checksum_type(self):
        if not self.checksum_type:
            self.checksum_type = configuration.get_repo_checksum_type(self.get_conduit(),
                                                                      self.get_config())
        return self.checksum_type

    def on_error(self):
        if self.repomd_file_context:
            self.repomd_file_context.finalize()


class ExportRepoPublisher(BaseYumRepoPublisher):
    """
    Yum HTTP/HTTPS publisher class that is responsible for the actual publishing
    of a yum repository over HTTP and/or HTTPS.
    """

    def __init__(self, repo, publish_conduit, config, distributor_type):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :param distributor_type: The type of the distributor that is being published
        :type distributor_type: str
        """
        super(ExportRepoPublisher, self).__init__(repo, publish_conduit, config, distributor_type)

        date_filter = export_utils.create_date_range_filter(config)
        if date_filter:
            # Since this is a partial export we don't generate metadata
            # we have to clear out the previously added steps
            # we only need special version s of the rpm, drpm, and errata steps
            self.clear_children()
            self.add_child(PublishRpmAndDrpmStepIncremental(association_filters=date_filter))
            self.add_child(PublishErrataStepIncremental(association_filters=date_filter))

        working_directory = self.get_working_dir()
        export_dir = config.get(constants.EXPORT_DIRECTORY_KEYWORD)
        if export_dir:
            target_dir = os.path.join(export_dir,
                                      configuration.get_repo_relative_path(repo, config))
            self.add_child(CopyDirectoryStep(working_directory, target_dir))
            self.add_child(GenerateListingFileStep(export_dir, target_dir))
        else:
            # Reset the steps to use an internal scratch directory other than the base working dir
            content_dir = os.path.join(working_directory, 'scratch')
            for step in self.children:
                step.working_dir = content_dir

            # Set up step to copy all the files to a realized directory with no symlinks
            # This could be optimized with a pathspec so that we don't create all the files
            # separately
            realized_dir = os.path.join(working_directory, 'realized')
            copy_target = os.path.join(realized_dir,
                                       configuration.get_repo_relative_path(repo, config))
            self.add_child(CopyDirectoryStep(content_dir, copy_target))
            self.add_child(GenerateListingFileStep(realized_dir, copy_target))

            # Create the steps to generate the ISO and publish them to their final location
            output_dir = os.path.join(working_directory, 'output')
            self.add_child(CreateIsoStep(realized_dir, output_dir))
            publish_location = [('/', location)
                                for location in configuration.get_export_repo_publish_dirs(repo,
                                                                                           config)]

            master_dir = configuration.get_master_publish_dir(repo, self.get_distributor_type())
            atomic_publish = AtomicDirectoryPublishStep(output_dir, publish_location, master_dir)
            atomic_publish.description = _('Moving ISO to final location')
            self.add_child(atomic_publish)


class ExportRepoGroupPublisher(PublishStep):

    def __init__(self, repo_group, publish_conduit, config, distributor_type):
        """
        :param repo_group: Pulp managed Yum repository
        :type  repo_group: pulp.plugins.model.RepositoryGroup
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoGroupPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :param distributor_type: The type of the distributor that is being published
        :type distributor_type: str
        """
        super(ExportRepoGroupPublisher, self).__init__(constants.PUBLISH_STEP_EXPORT_REPO_GROUP,
                                                       repo_group, publish_conduit, config,
                                                       working_dir=repo_group.working_dir,
                                                       distributor_type=distributor_type)

        working_dir = self.get_working_dir()
        scratch_dir = os.path.join(working_dir, 'scratch')
        realized_dir = os.path.join(working_dir, 'realized')

        flat_config = config.flatten()
        export_dir = config.get(constants.EXPORT_DIRECTORY_KEYWORD)
        if export_dir:
            repo_config = config
        else:
            repo_config = PluginCallConfiguration(flat_config, {constants.EXPORT_DIRECTORY_KEYWORD:
                                                                realized_dir})
        query_manager = RepoQueryManager()

        repos = query_manager.find_by_id_list(repo_group.repo_ids)
        empty_repos = True
        for repo in repos:
            empty_repos = False
            repo = common_utils.to_transfer_repo(repo)
            # Make sure we only publish rpm repo's
            if repo.notes['_repo-type'] != 'rpm-repo':
                continue

            repo_config_copy = copy.deepcopy(repo_config)
            repo.working_dir = os.path.join(scratch_dir, repo.id)
            repo_conduit = RepoPublishConduit(repo.id, distributor_type)
            publisher = ExportRepoPublisher(repo, repo_conduit, repo_config_copy,
                                            distributor_type)
            publisher.description = _("Exporting Repo: %s") % repo.id
            self.add_child(publisher)
        if empty_repos:
            os.makedirs(realized_dir)
            self.add_child(GenerateListingFileStep(realized_dir, realized_dir))

        # If we aren't exporting to a directory add the ISO create & publish steps
        if not export_dir:
            # Create the steps to generate the ISO and publish them to their final location
            output_dir = os.path.join(working_dir, 'output')
            self.add_child(CreateIsoStep(realized_dir, output_dir))
            export_dirs = configuration.get_export_repo_group_publish_dirs(repo_group, config)
            publish_location = [('/', location) for location in export_dirs]

            master_dir = configuration.get_master_publish_dir(repo_group, distributor_type)
            self.add_child(AtomicDirectoryPublishStep(output_dir, publish_location, master_dir))


class Publisher(BaseYumRepoPublisher):
    """
    Yum HTTP/HTTPS publisher class that is responsible for the actual publishing
    of a yum repository over HTTP and/or HTTPS.
    """

    def __init__(self, repo, publish_conduit, config, distributor_type):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :param distributor_type: The type of the distributor that is being published
        :type distributor_type: str
        """

        repo_relative_path = configuration.get_repo_relative_path(repo, config)

        last_published = publish_conduit.last_publish()
        last_deleted = repo.last_unit_removed
        date_filter = None

        insert_step = None
        if last_published and \
                ((last_deleted and last_published > last_deleted) or not last_deleted):
            # Add the step to copy the current published directory into place
            working_dir = repo.working_dir
            specific_master = None

            if config.get(constants.PUBLISH_HTTPS_KEYWORD):
                root_publish_dir = configuration.get_https_publish_dir(config)
                repo_publish_dir = os.path.join(root_publish_dir, repo_relative_path)
                specific_master = os.path.realpath(repo_publish_dir)
            if not specific_master and config.get(constants.PUBLISH_HTTP_KEYWORD):
                root_publish_dir = configuration.get_http_publish_dir(config)
                repo_publish_dir = os.path.join(root_publish_dir, repo_relative_path)
                specific_master = os.path.realpath(repo_publish_dir)

            # Only do an incremental publish if the previous publish can be found
            if os.path.exists(specific_master):
                insert_step = CopyDirectoryStep(specific_master, working_dir,
                                                preserve_symlinks=True)
                # Pass something useful to the super so that it knows the publish info
                string_date = dateutils.format_iso8601_datetime(last_published)
                date_filter = export_utils.create_date_range_filter(
                    {constants.START_DATE_KEYWORD: string_date})

        super(Publisher, self).__init__(repo, publish_conduit, config, distributor_type,
                                        association_filters=date_filter)

        if insert_step:
            self.insert_child(0, insert_step)
            self.rpm_step.fast_forward = True

        # Add the web specific directory publishing processing steps
        target_directories = []

        # it's convenient to create these now, but we won't add them until later,
        # because we want them to run last
        listing_steps = []

        if config.get(constants.PUBLISH_HTTPS_KEYWORD):
            root_publish_dir = configuration.get_https_publish_dir(config)
            repo_publish_dir = os.path.join(root_publish_dir, repo_relative_path)
            target_directories.append(['/', repo_publish_dir])
            listing_steps.append(GenerateListingFileStep(root_publish_dir, repo_publish_dir))
        if config.get(constants.PUBLISH_HTTP_KEYWORD):
            root_publish_dir = configuration.get_http_publish_dir(config)
            repo_publish_dir = os.path.join(root_publish_dir, repo_relative_path)
            target_directories.append(['/', repo_publish_dir])
            listing_steps.append(GenerateListingFileStep(root_publish_dir, repo_publish_dir))

        master_publish_dir = configuration.get_master_publish_dir(repo, distributor_type)
        atomic_publish_step = AtomicDirectoryPublishStep(self.get_working_dir(),
                                                         target_directories,
                                                         master_publish_dir)
        atomic_publish_step.description = _("Publishing files to web")

        self.add_child(atomic_publish_step)

        # add the listing file generation step(s)
        for step in listing_steps:
            self.add_child(step)


class GenerateListingFileStep(PublishStep):
    def __init__(self, root_dir, target_dir, step=constants.PUBLISH_GENERATE_LISTING_FILE_STEP):
        """
        Initialize and set the ID of the step
        """
        super(GenerateListingFileStep, self).__init__(step)
        self.description = _("Writing Listings File")
        self.root_dir = root_dir
        self.target_dir = target_dir

    def process_main(self):
        util.generate_listing_files(self.root_dir, self.target_dir)


class InitRepoMetadataStep(PublishStep):

    def __init__(self, step=constants.PUBLISH_INIT_REPOMD_STEP):
        """
        Initialize and set the ID of the step
        """
        super(InitRepoMetadataStep, self).__init__(step)
        self.description = _("Initializing repo metadata")

    def initialize(self):
        self.parent.repomd_file_context = RepomdXMLFileContext(self.get_working_dir(),
                                                               self.parent.get_checksum_type())
        self.parent.repomd_file_context.initialize()


class CloseRepoMetadataStep(PublishStep):

    def __init__(self, step=constants.PUBLISH_CLOSE_REPOMD_STEP):
        """
        Initialize and set the ID of the step
        """
        super(CloseRepoMetadataStep, self).__init__(step)
        self.description = _("Closing repo metadata")

    def finalize(self):
        if self.parent.repomd_file_context:
            self.parent.repomd_file_context.finalize()


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
        self.repomd_file_context = RepomdXMLFileContext(self.get_working_dir(),
                                                        self.parent.get_checksum_type())
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

    def __init__(self, dist_step, **kwargs):
        super(PublishRpmStep, self).__init__(constants.PUBLISH_RPMS_STEP,
                                             [TYPE_ID_RPM, TYPE_ID_SRPM], **kwargs)
        self.description = _('Publishing RPMs')
        self.file_lists_context = None
        self.other_context = None
        self.primary_context = None
        self.dist_step = dist_step
        self.fast_forward = False

    def initialize(self):
        """
        Create each of the three metadata contexts required for publishing RPM & SRPM
        """
        total = self._get_total(ignore_filter=self.fast_forward)

        checksum_type = self.parent.get_checksum_type()
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
        repomd = self.parent.repomd_file_context

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
        for package_dir in self.dist_step.package_dirs:
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
        self.parent.repomd_file_context.\
            add_metadata_file_metadata(unit.unit_key['data_type'], link_path)


class PublishDrpmStep(UnitPublishStep):
    """
    Publish Delta RPMS
    """

    def __init__(self, dist_step, **kwargs):
        super(PublishDrpmStep, self).__init__(constants.PUBLISH_DELTA_RPMS_STEP, TYPE_ID_DRPM,
                                              **kwargs)
        self.description = _('Publishing Delta RPMs')
        self.context = None
        self.dist_step = dist_step

    def initialize(self):
        """
        Initialize the PrestoDelta metadata file
        """
        checksum_type = self.parent.get_checksum_type()
        self.context = PrestodeltaXMLFileContext(self.get_working_dir(), checksum_type)
        self.context.initialize()

    def is_skipped(self):
        """
        Test to find out if the step should be skipped.

        :return: whether or not the step should be skipped
        :rtype:  bool
        """
        # skip if there are no DRPMs.
        if self._get_total() == 0:
            return True

        return super(PublishDrpmStep, self).is_skipped()

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
        for package_dir in self.dist_step.package_dirs:
            destination_path = os.path.join(package_dir, relative_path)
            self._create_symlink(source_path, destination_path)
        self.context.add_unit_metadata(unit)

    def finalize(self):
        """
        Close & finalize each of the metadata files
        """
        if self.context:
            self.context.finalize()
            self.parent.repomd_file_context.\
                add_metadata_file_metadata('prestodelta', self.context.metadata_file_path,
                                           self.context.checksum)


class PublishErrataStep(UnitPublishStep):
    """
    Publish all errata
    """
    def __init__(self, **kwargs):
        super(PublishErrataStep, self).__init__(constants.PUBLISH_ERRATA_STEP, TYPE_ID_ERRATA,
                                                **kwargs)
        self.context = None
        self.description = _('Publishing Errata')
        self.process_unit = None

    def initialize(self):
        """
        Initialize the UpdateInfo file and set the method used to process the unit to the
        one that is built into the UpdateinfoXMLFileContext
        """
        checksum_type = self.parent.get_checksum_type()
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
            self.parent.repomd_file_context.\
                add_metadata_file_metadata('updateinfo', self.context.metadata_file_path,
                                           self.context.checksum)


class PublishRpmAndDrpmStepIncremental(UnitPublishStep):
    """
    Publish all incremental errata
    """
    def __init__(self, **kwargs):
        super(PublishRpmAndDrpmStepIncremental, self).__init__(constants.PUBLISH_RPMS_STEP,
                                                               [TYPE_ID_RPM, TYPE_ID_SRPM,
                                                                TYPE_ID_DRPM],
                                                               unit_fields=PACKAGE_FIELDS, **kwargs)
        self.description = _('Publishing RPM, SRPM, and DRPM')

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

        filename = unit.unit_key['name'] + '-' + unit.unit_key['version'] + '-' + \
            unit.unit_key['release'] + '.' + unit.unit_key['arch'] + '.json'
        path = os.path.join(self.get_working_dir(), filename)

        # Remove all keys that start with an underscore, like _id and _ns
        for key_to_remove in filter(lambda key: key[0] == '_', unit.metadata.keys()):
            unit.metadata.pop(key_to_remove)
        # repodata will be regenerated on import, so remove it as well
        if 'repodata' in unit.metadata:
            unit.metadata.pop('repodata')

        dict_to_write = {'unit_key': unit.unit_key, 'unit_metadata': unit.metadata}

        with open(path, 'w') as f:
            json.dump(dict_to_write, f)


class PublishErrataStepIncremental(UnitPublishStep):
    """
    Publish all incremental errata
    """
    def __init__(self, **kwargs):
        super(PublishErrataStepIncremental, self).__init__(constants.PUBLISH_ERRATA_STEP,
                                                           TYPE_ID_ERRATA, **kwargs)
        self.description = _('Publishing Errata')

    def process_unit(self, unit):
        # Remove unnecessary keys, like _id
        for key_to_remove in filter(lambda key: key[0] == '_', unit.metadata.keys()):
            unit.metadata.pop(key_to_remove)
        errata_dict = {
            'unit_key': unit.unit_key,
            'unit_metadata': unit.metadata
        }

        json_file_path = os.path.join(self.get_working_dir(), unit.unit_key['id'] + '.json')
        with open(json_file_path, 'w') as f:
            json.dump(errata_dict, f)


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
        category_generator = self.get_conduit().get_units(criteria, as_generator=True)

        UnitProcessor = namedtuple('UnitProcessor', 'unit process')
        for category in category_generator:
            yield UnitProcessor(category, self.comps_context.add_package_category_unit_metadata)

        # set the process unit method to groups
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_PKG_GROUP])
        groups_generator = self.get_conduit().get_units(criteria, as_generator=True)
        for group in groups_generator:
            yield UnitProcessor(group, self.comps_context.add_package_group_unit_metadata)

        # set the process unit method to environments
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_PKG_ENVIRONMENT])
        groups_generator = self.get_conduit().get_units(criteria, as_generator=True)
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
        checksum_type = self.parent.get_checksum_type()
        self.comps_context = PackageXMLFileContext(self.get_working_dir(), checksum_type)
        self.comps_context.initialize()

    def finalize(self):
        """
        Finalize all metadata associated with the comps file
        """
        if self.comps_context:
            self.comps_context.finalize()
            if self.parent.repomd_file_context:
                self.parent.repomd_file_context.\
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
        self.package_dirs = []
        self.description = _('Publishing Distribution files')

    def initialize(self):
        """
        When initializing the metadata verify that only one distribution exists
        """
        if self._get_total() > 1:
            msg = _('Error publishing repository %(repo)s.  '
                    'More than one distribution found.') % {'repo': self.parent.repo.id}
            logger.debug(msg)
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
            logger.debug("creating treeinfo symlink from %s to %s" % (src_treeinfo_path,
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
            logger.warning(msg)
            return

        distro_files = distribution_unit.metadata['files']
        total_files = len(distro_files)
        logger.debug("Found %s distribution files to symlink" % total_files)

        source_path_dir = distribution_unit.storage_path
        symlink_dir = self.get_working_dir()
        for dfile in distro_files:
            source_path = os.path.join(source_path_dir, dfile['relativepath'])
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
                        % {'repo': self.parent.repo.id, 'packagedir': package_path})
                logger.info(msg)
                raise InvalidValue(KEY_PACKAGEDIR)

            self.package_dirs.append(real_package_path)
            if os.path.islink(package_path):
                # a package path exists as a symlink we are going to remove it since
                # the _create_symlink will create a real directory
                os.unlink(package_path)

        default_packages_symlink = os.path.join(symlink_dir, 'Packages')
        if package_path != default_packages_symlink:
            # Add the Packages directory to the content directory
            self.package_dirs.append(default_packages_symlink)


class CreateIsoStep(PublishStep):
    """
    Export a directory to an ISO or a collection of ISO files

    """
    def __init__(self, content_dir, output_dir):
        super(CreateIsoStep, self).__init__(constants.PUBLISH_STEP_ISO)
        self.description = _('Exporting ISO')
        self.content_dir = content_dir
        self.output_dir = output_dir

    def process_main(self):
        """
        Publish a directory from to a tar file
        """
        image_size = self.get_config().get(constants.ISO_SIZE_KEYWORD)
        image_prefix = self.get_config().get(constants.ISO_PREFIX_KEYWORD) or self.get_repo().id
        generate_iso.create_iso(self.content_dir, self.output_dir, image_prefix, image_size)


class GenerateSqliteForRepoStep(PublishStep):
    """
    Generate the Sqlite files for a given repository using the createrepo command
    """
    def __init__(self, content_dir):
        """
        Initialize the step for creating sqlite files

        :param content_dir: The base directory of the repository.  This directory should contain
                            the repodata directory
        :type content_dir: str
        """
        super(GenerateSqliteForRepoStep, self).__init__(constants.PUBLISH_GENERATE_SQLITE_FILE_STEP)
        self.description = _('Generating sqlite files')
        self.content_dir = content_dir

    def is_skipped(self):
        """
        Check the repo for the config option to generate the sqlite files.
        Skip generation if the config option is not specified.

        :returns: Whether or not generating sqlite files has been enabled for this repository
        :rtype: bool
        """
        return not self.get_config().get('generate_sqlite', False)

    def process_main(self):
        """
        Call out to createrepo command line in order to process the files.
        """
        pipe = subprocess.Popen('createrepo -d --update --skip-stat %s' % self.content_dir,
                                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = pipe.communicate()
        if pipe.returncode != 0:
            result_string = '%s\n::\n%s' % (stdout, stderr)
            raise PulpCodedException(message=result_string)
