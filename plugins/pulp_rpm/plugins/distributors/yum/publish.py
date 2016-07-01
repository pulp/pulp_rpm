import copy
import itertools
import os
import subprocess
from gettext import gettext as _
from xml.etree import cElementTree

import mongoengine
from pulp.common import dateutils
from pulp.common.compat import json
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.util import misc as plugin_misc
from pulp.plugins.util import publish_step as platform_steps
from pulp.server.db import model
from pulp.server.exceptions import InvalidValue, PulpCodedException
from pulp.server.controllers import repository as repo_controller

from pulp_rpm.common import constants, ids
from pulp_rpm.yum_plugin import util
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.db import models
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


class BaseYumRepoPublisher(platform_steps.PluginStep):
    """
    Yum HTTP/HTTPS publisher class that is responsible for the actual publishing
    of a yum repository over HTTP and/or HTTPS.
    """

    def __init__(self, repo, publish_conduit, config, distributor_type, association_filters=None,
                 **kwargs):
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
        :type association_filters: mongoengine.Q

        """
        super(BaseYumRepoPublisher, self).__init__(constants.PUBLISH_REPO_STEP, repo,
                                                   publish_conduit, config,
                                                   plugin_type=distributor_type, **kwargs)

        self.repomd_file_context = None
        self.checksum_type = None

        self.add_child(InitRepoMetadataStep())
        dist_step = PublishDistributionStep()
        self.add_child(dist_step)
        self.rpm_step = PublishRpmStep(dist_step, repo_content_unit_q=association_filters)
        self.add_child(self.rpm_step)
        self.add_child(PublishDrpmStep(dist_step, repo_content_unit_q=association_filters))
        errata_step_kwargs = {}
        if config.get_boolean(constants.INCREMENTAL_EXPORT_REPOMD_KEYWORD):
            errata_step_kwargs['repo_content_unit_q'] = association_filters
        errata_step = PublishErrataStep(**errata_step_kwargs)
        self.add_child(errata_step)
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

    def __init__(self, repo, publish_conduit, config, distributor_type, **kwargs):
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

        date_q = export_utils.create_date_range_filter(config)

        if config.get_boolean(constants.INCREMENTAL_EXPORT_REPOMD_KEYWORD):
            super(ExportRepoPublisher, self).__init__(repo, publish_conduit, config,
                                                      distributor_type, association_filters=date_q,
                                                      **kwargs)
        else:
            super(ExportRepoPublisher, self).__init__(repo, publish_conduit, config,
                                                      distributor_type, **kwargs)
            if date_q:
                # Since this is a partial export we don't generate metadata
                # we have to clear out the previously added steps
                # we only need special version s of the rpm, drpm, and errata steps
                self.clear_children()
                self.add_child(PublishRpmAndDrpmStepIncremental(repo_content_unit_q=date_q))
                self.add_child(PublishErrataStepIncremental(repo_content_unit_q=date_q))

        working_directory = self.get_working_dir()
        export_dir = config.get(constants.EXPORT_DIRECTORY_KEYWORD)
        if export_dir:
            target_dir = os.path.join(export_dir,
                                      configuration.get_repo_relative_path(repo.repo_obj, config))
            self.add_child(platform_steps.CopyDirectoryStep(working_directory, target_dir))
            self.add_child(GenerateListingFileStep(export_dir, target_dir))
        else:
            # Reset the steps to use an internal scratch directory other than the base working dir
            content_dir = os.path.join(working_directory, 'scratch')
            for step in self.children:
                step.working_dir = content_dir
            self.working_dir = content_dir

            # Set up step to copy all the files to a realized directory with no symlinks
            # This could be optimized with a pathspec so that we don't create all the files
            # separately
            realized_dir = os.path.join(working_directory, 'realized')
            copy_target = os.path.join(realized_dir,
                                       configuration.get_repo_relative_path(repo.repo_obj, config))
            self.add_child(platform_steps.CopyDirectoryStep(content_dir, copy_target))
            self.add_child(GenerateListingFileStep(realized_dir, copy_target))

            # Create the steps to generate the ISO and publish them to their final location
            output_dir = os.path.join(working_directory, 'output')
            self.add_child(CreateIsoStep(realized_dir, output_dir))

            # create the PULP_MANIFEST file if requested in the config
            if config.get_boolean(constants.CREATE_PULP_MANIFEST) is True:
                self.add_child(platform_steps.CreatePulpManifestStep(output_dir))

            dirs = configuration.get_export_repo_publish_dirs(repo.repo_obj, config)
            publish_location = [('/', location) for location in dirs]

            master_dir = configuration.get_master_publish_dir(repo.repo_obj, self.get_plugin_type())
            atomic_publish = platform_steps.AtomicDirectoryPublishStep(
                output_dir, publish_location, master_dir)
            atomic_publish.description = _('Moving ISO to final location')
            self.add_child(atomic_publish)


class ExportRepoGroupPublisher(platform_steps.PluginStep):

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
                                                       plugin_type=distributor_type)

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

        repo_objs = model.Repository.objects(repo_id__in=repo_group.repo_ids)
        empty_repos = True
        for repo_obj in repo_objs:
            empty_repos = False
            repo = repo_obj.to_transfer_repo()
            # Make sure we only publish rpm repo's
            if repo.notes['_repo-type'] != 'rpm-repo':
                continue

            repo_config_copy = copy.deepcopy(repo_config)

            # Need some code to pull the distributor
            distributor = model.Distributor.objects(repo_id=repo_obj['repo_id'],
                                                    distributor_id=ids.EXPORT_DISTRIBUTOR_ID,
                                                    config__relative_url__exists=True).first()

            if distributor is not None:
                relative_url = distributor['config']['relative_url']
            else:
                relative_url = repo_obj['repo_id']

            if not export_dir:
                repo_config_copy.override_config['relative_url'] = relative_url
            else:
                merged_rel = repo_config_copy.get('relative_url', '') + '/' + relative_url
                repo_config_copy.override_config['relative_url'] = merged_rel

            repo_working_dir = os.path.join(scratch_dir, repo.id)
            repo_conduit = RepoPublishConduit(repo.id, distributor_type)
            publisher = ExportRepoPublisher(repo, repo_conduit, repo_config_copy,
                                            distributor_type, working_dir=repo_working_dir)
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

            # create the PULP_MANIFEST file if requested in the config
            if config.get_boolean(constants.CREATE_PULP_MANIFEST) is True:
                self.add_child(platform_steps.CreatePulpManifestStep(output_dir))

            export_dirs = configuration.get_export_repo_group_publish_dirs(repo_group, config)
            publish_location = [('/', location) for location in export_dirs]

            master_dir = configuration.get_master_publish_dir_from_group(repo_group,
                                                                         distributor_type)
            self.add_child(platform_steps.AtomicDirectoryPublishStep(output_dir, publish_location,
                                                                     master_dir))


class Publisher(BaseYumRepoPublisher):
    """
    Yum HTTP/HTTPS publisher class that is responsible for the actual publishing
    of a yum repository over HTTP and/or HTTPS.
    """

    def __init__(self, transfer_repo, publish_conduit, config, distributor_type,
                 association_filters=None, **kwargs):
        """
        :param transfer_repo: repository being published
        :type  transfer_repo: pulp.plugins.db.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :param association_filters: Any filters to be applied to the list of RPMs being published
        :type association_filters: mongoengine.Q
        :param distributor_type: The type of the distributor that is being published
        :type distributor_type: str
        """
        repo = transfer_repo.repo_obj

        repo_relative_path = configuration.get_repo_relative_path(repo, config)

        last_published = publish_conduit.last_publish()
        last_deleted = repo.last_unit_removed

        # NB: there is an "incremental publish optmization" (aka fast-forward
        # publish), and an unrelated "incremental publish". The former is
        # related to avoiding extra disk IO on publishes, and the latter is for
        # publishing units in a date range.  In order to do the "incremental
        # publish", we need to disable the "incremental publish optimization"
        # to ensure the prior published repo contents are cleared out. This is
        # done via the "force_full" option.

        if association_filters:
            force_full = True
            date_filter = association_filters
        else:
            force_full = config.get(constants.FORCE_FULL_KEYWORD, False)
            date_filter = None

        if last_published and \
                (last_deleted is None or last_published > last_deleted) and \
                not force_full:
            # Add the step to copy the current published directory into place
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
                # Pass something useful to the super so that it knows the publish info
                string_date = dateutils.format_iso8601_datetime(last_published)
                date_filter = mongoengine.Q(created__gte=string_date)

        super(Publisher, self).__init__(transfer_repo, publish_conduit, config, distributor_type,
                                        association_filters=date_filter, **kwargs)

        if date_filter:
            insert_step = platform_steps.CopyDirectoryStep(
                specific_master, self.get_working_dir(), preserve_symlinks=True)
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

        self.add_child(GenerateRepoviewStep(self.get_working_dir()))

        master_publish_dir = configuration.get_master_publish_dir(repo, distributor_type)
        atomic_publish_step = platform_steps.AtomicDirectoryPublishStep(
            self.get_working_dir(), target_directories, master_publish_dir)
        atomic_publish_step.description = _("Publishing files to web")

        self.add_child(atomic_publish_step)

        # add the listing file generation step(s)
        for step in listing_steps:
            self.add_child(step)


class GenerateListingFileStep(platform_steps.PluginStep):
    def __init__(self, root_dir, target_dir, step=constants.PUBLISH_GENERATE_LISTING_FILE_STEP):
        """
        Initialize and set the ID of the step
        """
        super(GenerateListingFileStep, self).__init__(step)
        self.description = _("Writing Listings File")
        self.root_dir = root_dir
        self.target_dir = target_dir

    def process_main(self, item=None):
        util.generate_listing_files(self.root_dir, self.target_dir)


class InitRepoMetadataStep(platform_steps.PluginStep):

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


class CloseRepoMetadataStep(platform_steps.PluginStep):

    def __init__(self, step=constants.PUBLISH_CLOSE_REPOMD_STEP):
        """
        Initialize and set the ID of the step
        """
        super(CloseRepoMetadataStep, self).__init__(step)
        self.description = _("Closing repo metadata")

    def finalize(self):
        if self.parent.repomd_file_context:
            self.parent.repomd_file_context.finalize()


class PublishRpmStep(platform_steps.UnitModelPluginStep):
    """
    Step for publishing RPM & SRPM units
    """

    def __init__(self, dist_step, **kwargs):
        super(PublishRpmStep, self).__init__(constants.PUBLISH_RPMS_STEP,
                                             [models.RPM, models.SRPM], **kwargs)
        self.description = _('Publishing RPMs')
        self.file_lists_context = None
        self.other_context = None
        self.primary_context = None
        self.dist_step = dist_step
        self.fast_forward = False

    @property
    def total_packages_in_repo(self):
        """
        Determine how many total RPMs and SRPMs are in the repo. This corresponds to the total
        number of published packages that will show up in the published metadata.

        :return:    total number of RPMs and SRPMs in the repo
        :rtype:     int
        """
        rpm_total = self.get_repo().repo_obj.content_unit_counts.get(
            models.RPM._content_type_id.default, 0)
        srpm_total = self.get_repo().repo_obj.content_unit_counts.get(
            models.SRPM._content_type_id.default, 0)
        return rpm_total + srpm_total

    def initialize(self):
        """
        Create each of the three metadata contexts required for publishing RPM & SRPM
        """
        total = self.total_packages_in_repo

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

    def process_main(self, item=None):
        """
        Link the unit to the content directory and the package_dir

        :param item: The item to process or none if this get_iterator is not defined
        :type item: pulp_rpm.plugins.db.models.RPM or pulp_rpm.plugins.db.models.SRPM
        """
        unit = item
        source_path = unit._storage_path
        destination_path = os.path.join(self.get_working_dir(), unit.filename)
        plugin_misc.create_symlink(source_path, destination_path)
        for package_dir in self.dist_step.package_dirs:
            destination_path = os.path.join(package_dir, unit.filename)
            plugin_misc.create_symlink(source_path, destination_path)

        for context in (self.file_lists_context, self.other_context, self.primary_context):
            context.add_unit_metadata(unit)


class PublishMetadataStep(platform_steps.UnitModelPluginStep):
    """
    Publish extra metadata files that are copied from another repo and not generated
    """

    def __init__(self):
        super(PublishMetadataStep, self).__init__(constants.PUBLISH_METADATA_STEP,
                                                  [models.YumMetadataFile])
        self.description = _('Publishing Metadata.')

    def process_main(self, item=None):
        """
        Copy the metadata file into place and add it tot he repomd file.

        :param item: The unit to process
        :type item: pulp.server.db.model.ContentUnit
        """
        unit = item
        # Copy the file to the location on disk where the published repo is built
        publish_location_relative_path = os.path.join(self.get_working_dir(),
                                                      REPO_DATA_DIR_NAME)

        metadata_file_name = os.path.basename(unit._storage_path)
        link_path = os.path.join(publish_location_relative_path, metadata_file_name)
        plugin_misc.create_symlink(unit._storage_path, link_path)

        # Add the proper relative reference to the metadata file to repomd
        self.parent.repomd_file_context.\
            add_metadata_file_metadata(unit.data_type, link_path)


class PublishDrpmStep(platform_steps.UnitModelPluginStep):
    """
    Publish Delta RPMS
    """

    def __init__(self, dist_step, **kwargs):
        super(PublishDrpmStep, self).__init__(constants.PUBLISH_DELTA_RPMS_STEP, [models.DRPM],
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
        if self.get_total() == 0:
            return True

        return super(PublishDrpmStep, self).is_skipped()

    def process_main(self, item=None):
        """
        Link the unit to the drpm content directory and
        update the prestodelta metadata file.

        :param item: The unit to process
        :type item: pulp.server.db.model.ContentUnit
        """
        unit = item
        source_path = unit._storage_path
        unit_filename = os.path.basename(unit.filename)
        relative_path = os.path.join('drpms', unit_filename)
        destination_path = os.path.join(self.get_working_dir(), relative_path)
        plugin_misc.create_symlink(source_path, destination_path)
        for package_dir in self.dist_step.package_dirs:
            destination_path = os.path.join(package_dir, relative_path)
            plugin_misc.create_symlink(source_path, destination_path)
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


class PublishErrataStep(platform_steps.UnitModelPluginStep):
    """
    Publish all errata
    """

    def __init__(self, **kwargs):
        super(PublishErrataStep, self).__init__(constants.PUBLISH_ERRATA_STEP, [models.Errata],
                                                **kwargs)
        self.context = None
        self.description = _('Publishing Errata')
        self.process_main = None

    def initialize(self):
        """
        Initialize the UpdateInfo file and set the method used to process the unit to the
        one that is built into the UpdateinfoXMLFileContext
        """
        repo_id = self.get_repo().id
        nevra_fields = ('name', 'epoch', 'version', 'release', 'arch')
        querysets = repo_controller.get_unit_model_querysets(repo_id, models.RPM)
        nevra_scalars = itertools.chain(*[q.scalar(*nevra_fields) for q in querysets])
        nevra_in_repo = set()
        for scalar in nevra_scalars:
            nevra_in_repo.add(models.NEVRA(*scalar))

        checksum_type = self.parent.get_checksum_type()
        updateinfo_checksum_type = self.get_config().get('updateinfo_checksum_type')
        self.context = UpdateinfoXMLFileContext(self.get_working_dir(), nevra_in_repo,
                                                checksum_type, self.get_conduit(),
                                                updateinfo_checksum_type)
        self.context.initialize()

        # set the self.process_unit method to the corresponding method on the
        # UpdateInfoXMLFileContext as there is no other processing to be done for each unit.
        self.process_main = self.context.add_unit_metadata

    def finalize(self):
        """
        Finalize and write to disk the metadata and add the updateinfo file to the repomd
        """
        if self.context:
            self.context.finalize()
            self.parent.repomd_file_context.\
                add_metadata_file_metadata('updateinfo', self.context.metadata_file_path,
                                           self.context.checksum)


class PublishRpmAndDrpmStepIncremental(platform_steps.UnitModelPluginStep):
    """
    Publish all incremental rpms and drpms
    """
    def __init__(self, **kwargs):
        super(PublishRpmAndDrpmStepIncremental, self).__init__(constants.PUBLISH_RPMS_STEP,
                                                               [models.RPM, models.SRPM,
                                                                models.DRPM], **kwargs)
        self.description = _('Publishing RPM, SRPM, and DRPM')

    def initialize(self):
        """
        In case there are no units that get processed, nothing else would create this directory.
        Its existence is required by the CopyDirectoryStep.
        """
        super(PublishRpmAndDrpmStepIncremental, self).initialize()
        if not os.path.exists(self.get_working_dir()):
            os.makedirs(self.get_working_dir())

    @property
    def unit_querysets(self):
        """
        Limits the queryset's fields

        :return:    generator of mongoengine.QuerySet objects that have fields limited
        :rtype:     generator
        """
        querysets = super(PublishRpmAndDrpmStepIncremental, self).unit_querysets
        # The repodata field can be huge, and we don't need it right now.
        return (qs.exclude('repodata') for qs in querysets)

    def process_main(self, item=None):
        """
        Link the unit to the content directory and the package_dir

        :param unit: The unit to process
        :type unit: pulp.server.db.model.NonMetadataPackage
        """
        unit = item
        source_path = unit._storage_path
        relative_path = unit.filename
        destination_path = os.path.join(self.get_working_dir(), relative_path)
        plugin_misc.create_symlink(source_path, destination_path)

        filename = unit.name + '-' + unit.version + '-' + unit.release + '.' + unit.arch + '.json'
        path = os.path.join(self.get_working_dir(), filename)

        metadata_dict = unit.create_legacy_metadata_dict()
        # The repodata is large, and can get re-generated during upload, so we leave it out here.
        metadata_dict.pop('repodata', None)
        dict_to_write = {'unit_key': unit.unit_key, 'unit_metadata': metadata_dict}

        with open(path, 'w') as f:
            json.dump(dict_to_write, f)


class PublishErrataStepIncremental(platform_steps.UnitModelPluginStep):
    """
    Publish all incremental errata
    """
    def __init__(self, **kwargs):
        super(PublishErrataStepIncremental, self).__init__(constants.PUBLISH_ERRATA_STEP,
                                                           [models.Errata], **kwargs)
        self.description = _('Publishing Errata')

    def process_main(self, item=None):
        """
        :param item: the errata unit to process
        :type item: pulp_rpm.plugins.db.models.Errata
        """
        unit = item
        errata_dict = {
            'unit_key': unit.unit_key,
            'unit_metadata': unit.create_legacy_metadata_dict()
        }

        json_file_path = os.path.join(self.get_working_dir(), unit.errata_id + '.json')
        with open(json_file_path, 'w') as f:
            json.dump(errata_dict, f)


class PublishCompsStep(platform_steps.UnitModelPluginStep):
    def __init__(self):
        super(PublishCompsStep, self).__init__(constants.PUBLISH_COMPS_STEP,
                                               [models.PackageGroup, models.PackageCategory,
                                                models.PackageEnvironment, models.PackageLangpacks])
        self.comps_context = None
        self.description = _('Publishing Comps file')

    def process_main(self, item=None):
        """
        Process each unit created by the generator using the associated
        process command
        """
        if isinstance(item, models.PackageCategory):
            self.comps_context.add_package_category_unit_metadata(item)
        elif isinstance(item, models.PackageEnvironment):
            self.comps_context.add_package_environment_unit_metadata(item)
        elif isinstance(item, models.PackageGroup):
            self.comps_context.add_package_group_unit_metadata(item)
        elif isinstance(item, models.PackageLangpacks):
            self.comps_context.add_package_langpacks_unit_metadata(item)
        else:
            logger.warning(_('Unknown comps unit type: %(n)s') % {'n': item.__class__})

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


class PublishDistributionStep(platform_steps.UnitModelPluginStep):
    """
    Publish distribution files associated with the anaconda installer
    """

    def __init__(self):
        """
        initialize and set the package_dir to None as it is referenced by other
        plugins even if it is not specified
        """
        super(PublishDistributionStep, self).__init__(constants.PUBLISH_DISTRIBUTION_STEP,
                                                      [models.Distribution])
        self.package_dirs = []
        self.description = _('Publishing Distribution files')

    def initialize(self):
        """
        When initializing the metadata verify that only one distribution exists
        """
        if self.get_total() > 1:
            msg = _('Error publishing repository %(repo)s.  '
                    'More than one distribution found.') % {'repo': self.parent.repo.repo_id}
            logger.debug(msg)
            raise Exception(msg)

    def process_main(self, item=None):
        """
        Process the distribution unit

        :param item: The unit to process
        :type  item: pulp_rpm.plugins.db.models.Distribution
        """
        unit = item
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
        :type distribution_unit: pulp_rpm.plugins.db.models.Distribution
        """
        distribution_unit_storage_path = distribution_unit._storage_path
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
            plugin_misc.create_symlink(src_treeinfo_path, symlink_treeinfo_path)

    def _publish_distribution_files(self, distribution_unit):
        """
        For a given AssociatedUnit for a distribution.  Create all the links back to the
        content units that are referenced within the 'files' metadata section of the unit.

        :param distribution_unit: The unit for the distribution from which the list
                                  of files to be published should be pulled from.
        :type distribution_unit: pulp_rpm.plugins.db.models.Distribution
        """
        if not distribution_unit.files:
            msg = "No distribution files found for unit %s" % distribution_unit
            logger.warning(msg)
            return

        # The files from `treeinfo` and `PULP_DISTRIBUTION.xml` are mashed into the
        # files list on the unit. This is a hacky work-around to unmash them, filter
        # out anything that is in the main repodata directory (which is potentially not
        # safe, but was happening before I got here and we don't have time to fix this
        # properly right now), and generate a new `PULP_DISTRIBUTION.xml` that doesn't
        # reference files that don't exist in this publish.
        pulp_distribution_file = False
        distro_files = [f['relativepath'] for f in distribution_unit.files]
        if constants.DISTRIBUTION_XML in distro_files:
            distro_files.remove(constants.DISTRIBUTION_XML)
            pulp_distribution_file = True
        distro_files = filter(lambda f: not f.startswith('repodata/'), distro_files)
        total_files = len(distro_files)
        logger.debug("Found %s distribution files to symlink" % total_files)

        source_path_dir = distribution_unit._storage_path
        symlink_dir = self.get_working_dir()
        for dfile in distro_files:
            source_path = os.path.join(source_path_dir, dfile)
            symlink_path = os.path.join(symlink_dir, dfile)
            plugin_misc.create_symlink(source_path, symlink_path)

        # Not all repositories have this file so this is only done if the upstream repo
        # had the file.
        if pulp_distribution_file:
            xml_file_path = os.path.join(source_path_dir, constants.DISTRIBUTION_XML)
            self._write_pulp_distribution_file(distro_files, xml_file_path)

    def _write_pulp_distribution_file(self, distro_files, old_xml_file_path):
        """
        This method re-creates the `PULP_DISTRIBUTION.xml` file.

        It only adds a file to the new `PULP_DISTRIBUTION.xml` if the file existed in the
        old one fetched from the upstream repository. This is to stop it from including
        files added to the Distribution from the treeinfo file. It's messy and it should
        go away as soon as we re-work Distributions.

        :param distro_files: A list of file paths pulled from a `Distribution` unit.
        :type  distro_files: list of str
        :param old_xml_file_path: The absolute path to the old PULP_DISTRIBUTION.xml
                                  from upstream. The files referenced in here act as
                                  a filter for the new PULP_DISTRIBUTION.xml file.
        :type  old_xml_file_path: basestring
        """
        old_xml_tree = cElementTree.parse(old_xml_file_path)
        old_xml_root = old_xml_tree.getroot()
        old_files = [old_element.text for old_element in old_xml_root.getiterator('file')]
        distro_files = filter(lambda f: f in old_files, distro_files)
        new_xml_root = cElementTree.Element("pulp_distribution", {'version': '1'})
        for distro_file in distro_files:
            element = cElementTree.SubElement(new_xml_root, 'file')
            element.text = distro_file

        tree = cElementTree.ElementTree(new_xml_root)
        distribution_xml_path = os.path.join(self.get_working_dir(), constants.DISTRIBUTION_XML)
        try:
            os.remove(distribution_xml_path)
        except OSError as e:
            if e.errno != os.errno.ENOENT:
                raise

        tree.write(distribution_xml_path)

    def _publish_distribution_packages_link(self, distribution_unit):
        """
        Create a Packages directory in the repo that is a sym link back to the root directory
        of the repository.  This is required for compatibility with RHEL 5.

        Also create the directory that is specified by packagesdir section in the config file

        :param distribution_unit: The unit for the distribution from which the list
                                  of files to be published should be pulled from.
        :type distribution_unit: pulp_rpm.plugins.db.models.Distribution
        """
        symlink_dir = self.get_working_dir()
        package_path = None

        if distribution_unit.packagedir:
            # The packages_dir is a relative directory that exists underneath the repo directory
            # Verify that this directory is valid.
            package_path = os.path.join(symlink_dir, distribution_unit.packagedir)
            real_symlink_dir = os.path.realpath(symlink_dir)
            real_package_path = os.path.realpath(package_path)
            common_prefix = os.path.commonprefix([real_symlink_dir, real_package_path])
            if not common_prefix.startswith(real_symlink_dir):
                # the specified package path is not contained within the directory
                # raise a validation exception
                msg = _('Error publishing repository: %(repo)s.  The treeinfo file specified a '
                        'packagedir \"%(packagedir)s\" that is not contained within the repository'
                        % {'repo': self.get_repo().repo_id, 'packagedir': package_path})
                logger.info(msg)
                raise InvalidValue(KEY_PACKAGEDIR)

            self.package_dirs.append(real_package_path)
            if os.path.islink(package_path):
                # a package path exists as a symlink we are going to remove it since
                # the _create_symlink will create a real directory
                os.unlink(package_path)
        default_dir = self.get_config().get('packages_directory', 'Packages')
        default_packages_symlink = os.path.join(symlink_dir, default_dir)
        if package_path != default_packages_symlink:
            # Add the Packages directory to the content directory
            self.package_dirs.append(default_packages_symlink)


class CreateIsoStep(platform_steps.PluginStep):
    """
    Export a directory to an ISO or a collection of ISO files

    """
    def __init__(self, content_dir, output_dir):
        super(CreateIsoStep, self).__init__(constants.PUBLISH_STEP_ISO)
        self.description = _('Exporting ISO')
        self.content_dir = content_dir
        self.output_dir = output_dir

    def process_main(self, item=None):
        """
        Publish a directory from to a tar file
        """
        image_size = self.get_config().get(constants.ISO_SIZE_KEYWORD)
        image_prefix = self.get_config().get(constants.ISO_PREFIX_KEYWORD) or self.get_repo().id
        generate_iso.create_iso(self.content_dir, self.output_dir, image_prefix, image_size)


class GenerateSqliteForRepoStep(platform_steps.PluginStep):
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

    def process_main(self, item=None):
        """
        Call out to createrepo command line in order to process the files.
        """
        checksum_type = self.parent.get_checksum_type()
        pipe = subprocess.Popen('createrepo_c -d --update --keep-all-metadata '
                                '--local-sqlite '
                                '-s %(checksum_type)s --skip-stat %(content_dir)s' %
                                {'checksum_type': checksum_type, 'content_dir': self.content_dir},
                                shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = pipe.communicate()
        if pipe.returncode != 0:
            raise PulpCodedException(error_codes.RPM0001, command='createrepo_c', stdout=stdout,
                                     stderr=stderr)


class GenerateRepoviewStep(platform_steps.PluginStep):
    """
    Generate the static HTML files for a given repository using the repoview command
    """
    def __init__(self, content_dir):
        """
        Initialize the step for creating sqlite files

        :param content_dir: The base directory of the repository.  This directory should contain
                            the repodata directory
        :type content_dir: str
        """
        super(GenerateRepoviewStep, self).__init__(constants.PUBLISH_GENERATE_REPOVIEW_STEP)
        self.description = _('Generating HTML files')
        self.content_dir = content_dir

    def is_skipped(self):
        """
        Check the repo for the config option to generate the HTML files.
        Skip generation if the config option is not specified.

        :returns: Whether or not generating HTML files has been enabled for this repository
        :rtype: bool
        """
        return not self.get_config().get('repoview', False)

    def process_main(self, item=None):
        """
        Call out to repoview command line in order to process the files.
        """
        pipe = subprocess.Popen('repoview --title %(repo)s %(content_dir)s' %
                                {'content_dir': self.content_dir, 'repo': self.get_repo().id},
                                shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = pipe.communicate()
        if pipe.returncode != 0:
            raise PulpCodedException(error_codes.RPM0001, command='repoview', stdout=stdout,
                                     stderr=stderr)
