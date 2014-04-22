import os
import shutil
import time
import sys
import traceback
from gettext import gettext as _
from pprint import pformat
from collections import namedtuple

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
from .reporting import (
    new_progress_report, initialize_progress_sub_report, build_final_report)




# -- constants -----------------------------------------------------------------

_LOG = util.getLogger(__name__)

# -- package fields ------------------------------------------------------------

PACKAGE_FIELDS = ['id', 'name', 'version', 'release', 'arch', 'epoch',
                  '_storage_path', 'checksum', 'checksumtype', 'repodata']

# -- publisher class -----------------------------------------------------------


class BasePublisher(object):
    """
    The BasePublisher can be used as the foundation for any step based processor

    Publishers follow the following phases
    1) Initialize metadata - Perform any global metadata initialization
    2) Process Steps - Process units that are part of the repository
    3) Finalize Metadata - Perform any metadata processing needed before final publish
    4) Post Metadata processing - Perform any final actions needed for the publish.  Usually
       this will include moving the data from the working directory to it's final location
       on the filesystem and making it available publicly
    """

    def __init__(self,
                 repo, publish_conduit, config,
                 initialize_metadata_steps=None,
                 process_steps=None,
                 finalize_metadata_steps=None,
                 post_metadata_process_steps=None):
        """
        :param repo: The repo to be published
        :type repo: Repository
        :param publish_conduit: The publish conduit for the repo to be published
        :type publish_conduit: RepoPublishConduit
        :param config: The publish configuration
        :type config: PluginCallConfiguration
        :param initialize_metadata_steps: A list of steps that will have metadata initialized
        :type initialize_metadata_steps: list of PublishStep
        :param process_steps: A list of steps that are part of the primary publish action
        :type process_steps: list of PublishStep
        :param finalize_metadata_steps: A list of steps that are run as part of the metadata
                                        finalization phase
        :type finalize_metadata_steps: list of PublishStep
        :param post_metadata_process_steps: A list of steps that are run after metadata has
                                            been processed
        :type post_metadata_process_steps: list of PublishStep

        """

        self.timestamp = str(time.time())

        self.repo = repo
        self.conduit = publish_conduit
        self.config = config
        self.progress_report = new_progress_report()
        self.canceled = False
        self.working_dir = repo.working_dir

        self.all_steps = {}
        self.initialize_metadata_steps = []
        self.process_steps = []
        self.finalize_metadata_steps = []
        self.post_metadata_process_steps = []

        self._add_steps(initialize_metadata_steps, self.initialize_metadata_steps)
        self._add_steps(process_steps, self.process_steps)
        self._add_steps(finalize_metadata_steps, self.finalize_metadata_steps)
        self._add_steps(post_metadata_process_steps, self.post_metadata_process_steps)

    def _add_steps(self, step_list, target_list):
        """
        Add a step to step specified list and to the map of all known steps

        :param step_list: The list of steps to be added to the publisher
        :type step_list: list of PublishStep
        :param target_list: the list that the steps should be added to
        :type step_list: list of PublishStep
        """
        if step_list:
            for step in step_list:
                if step.step_id in self.all_steps:
                    if step != self.all_steps[step.step_id]:
                        raise ValueError(_('An attempt has been made to register two different '
                                           'steps with the same id: %s' % step.step_id))

                self.all_steps[step.step_id] = step
                step.parent = self
            target_list.extend(step_list)

    def get_step(self, step_id):
        """
        Get a step using the unique ID

        :param step_id: a unique identifier for the step to be returned
        :type step_id: str
        :returns: The step matching the step_id
        :rtype: PublishStep
        """
        return self.all_steps[step_id]

    def publish(self):
        """
        Perform the publish action the repo & information specified in the constructor
        """
        _LOG.debug('Starting publish for repository: %s' % self.repo.id)

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        try:
            # attempt processing of all the steps
            try:
                for step in self.initialize_metadata_steps:
                    step.initialize_metadata()
                for step in self.process_steps:
                    step.process()
            finally:
                # metadata steps may have open file handles so attempt finalization
                for step in self.finalize_metadata_steps:
                    step.finalize_metadata()
                    # Since this step doesn't go through the normal processing we must update it
                    step.report_progress(step.step_id, state=constants.STATE_COMPLETE)
            for step in self.post_metadata_process_steps:
                step.process()
        finally:
            # Always cleanup the working directory
            shutil.rmtree(self.working_dir, ignore_errors=True)

        _LOG.debug('Publish completed with progress:\n%s' % pformat(self.progress_report))

        return self._build_final_report()

    @property
    def skip_list(self):
        """
        Calculate the list of resource types that should be skipped during processing
        """
        skip = self.config.get('skip', [])
        # there is a chance that the skip list is actually a dictionary with a
        # boolean to indicate whether or not each item should be skipped
        # if that is the case iterate over it to build a list of the items
        # that should be skipped instead
        if type(skip) is dict:
            return [k for k, v in skip.items() if v]
        return skip

    def cancel(self):
        """
        Cancel an in-progress publication.
        """
        _LOG.debug('Canceling publish for repository: %s' % self.repo.id)

        if self.canceled:
            return

        self.canceled = True

        # put the reporting logic here so I don't have to put it everywhere
        for sub_report in self.progress_report.values():

            if sub_report[constants.PROGRESS_STATE_KEY] is constants.STATE_RUNNING:
                sub_report[constants.PROGRESS_STATE_KEY] = constants.STATE_CANCELLED

    # -- progress methods ------------------------------------------------------

    def _build_final_report(self):
        """
        :return: report describing the publish run
        :rtype:  pulp.plugins.model.PublishReport
        """

        relative_path = configuration.get_repo_relative_path(self.repo, self.config)

        return build_final_report(self.conduit, relative_path, self.progress_report)


class PublishStep(object):

    def __init__(self, step_id, unit_type=None):
        """
        Set the default parent, step_id and unit_type for the the publish step
        the unit_type defaults to none since some steps are not used for processing units.

        :param step_id: The id of the step this processes
        :type step_id: str
        :param unit_type: The type of unit this step processes
        :type unit_type: str or list of str
        """
        self.parent = None
        self.step_id = step_id
        self.unit_type = unit_type

    def get_working_dir(self):
        """
        Return the working directory
        :returns: the working directory from the parent
        """
        return self.parent.working_dir

    def get_step(self, step_id):
        """
        get a step from the parent
        :returns: the a step from the parent matching the given id
        """
        return self.parent.get_step(step_id)

    def get_unit_generator(self):
        """
        This method returns a generator for the unit_type specified on the PublishStep.
        The units created by this generator will be iterated over by the process_unit method.

        :return: generator of units
        :rtype:  GeneratorTyp of Units
        """
        criteria = UnitAssociationCriteria(type_ids=[self.unit_type])
        return self.parent.conduit.get_units(criteria, as_generator=True)

    def is_skipped(self):
        """
        Test to find out if the step should be skipped.

        :return: whether or not the step should be skipped
        :rtype:  bool
        """
        return self.unit_type in self.parent.skip_list

    def initialize_metadata(self):
        """
        Method called to initialize metadata after units are processed
        """
        pass

    def finalize_metadata(self):
        """
        Method called to finalize metadata after units are processed
        """
        pass

    def process_unit(self, unit):
        """
        Do any work required for publishing a unit in this step

        :param unit: The unit to process
        :type unit: Unit
        """
        pass

    def process(self):
        """
        The process method is used to perform the work needed for this step.
        It will update the step progress and raise an exception on error.
        """
        if self.parent.canceled:
            return

        if self.is_skipped():
            self.report_progress(self.step_id, state=constants.STATE_SKIPPED)
            return

        _LOG.debug('Processing publish step of type %(type)s for repository: %(repo)s' %
                   {'type': self.step_id, 'repo': self.parent.repo.id})

        self._init_step_progress_report(self.step_id)
        try:
            total = self._get_total(self.unit_type)
            self.initialize_metadata()
            self.parent.progress_report[self.step_id][constants.PROGRESS_TOTAL_KEY] = total
            package_unit_generator = self.get_unit_generator()
            self.report_progress(self.step_id)

            for package_unit in package_unit_generator:
                if self.parent.canceled:
                    return
                self.parent.progress_report[self.step_id][constants.PROGRESS_PROCESSED_KEY] += 1
                self.process_unit(package_unit)
                self.parent.progress_report[self.step_id][constants.PROGRESS_SUCCESSES_KEY] += 1

        except Exception:
            e_type, e_value, tb = sys.exc_info()
            self._record_failure(self.step_id, e_value, tb)
            self.report_progress(self.step_id, state=constants.STATE_FAILED)
            raise

        finally:
            try:
                self.finalize_metadata()
            except Exception, e:
                # on the off chance that one of the finalize steps raise an exception we need to
                # record it as a failure.  If a finalize does fail that error should take precedence
                # over a previous error
                self._record_failure(self.step_id, e)
                self.report_progress(self.step_id, state=constants.STATE_FAILED)
                raise

        self.report_progress(self.step_id, state=constants.STATE_COMPLETE)

    def _get_total(self, id_list=None):
        """
        Return the total number of units that are processed by this step.
        This is used generally for progress reporting.  The value returned should not change
        during the processing of the step.
        """
        if id_list is None:
            id_list = self.unit_type
        total = 0
        if isinstance(id_list, list):
            for type_id in id_list:
                total += self.parent.repo.content_unit_counts.get(type_id, 0)
        else:
            total = self.parent.repo.content_unit_counts.get(id_list, 0)
        return total

    def _symlink_content(self, unit, working_sub_dir):
        """
        Create a symlink to a unit's storage path in the given working subdirectory.

        :param unit: unit to create symlink to
        :type  unit: pulp.plugins.model.Unit
        :param working_sub_dir: working subdirectory to create symlink in
        :type  working_sub_dir: str
        """
        _LOG.debug('Creating symbolic link to content: %s' % unit.unit_key.get('name', 'unknown'))

        source_path = unit.storage_path
        relative_path = util.get_relpath_from_unit(unit)
        destination_path = os.path.join(working_sub_dir, relative_path)

        self._create_symlink(source_path, destination_path)

    @staticmethod
    def _create_symlink(source_path, link_path):
        """
        Create a symlink from the link path to the source path.

        If the link_path points to a directory that does not exist the directory
        will be created first.

        If we are overriding a current symlink with a new target - a debug message will be logged

        If a file already exists at the location specified by link_path an exception will be raised

        :param source_path: path of the source to link to
        :type  source_path: str
        :param link_path: path of the link
        :type  link_path: str
        """

        if not os.path.exists(source_path):
            msg = _('Will not create a symlink to a non-existent source [%(s)s]')
            raise RuntimeError(msg % {'s': source_path})

        if link_path.endswith('/'):
            link_path = link_path[:-1]

        link_parent_dir = os.path.dirname(link_path)

        if not os.path.exists(link_parent_dir):
            os.makedirs(link_parent_dir, mode=0770)
        elif os.path.lexists(link_path):
            if os.path.islink(link_path):
                link_target = os.readlink(link_path)
                if link_target == source_path:
                    # a pre existing link already points to the correct location
                    return
                msg = _('Removing old link [%(l)s] that was pointing to [%(t)s]')
                _LOG.debug(msg % {'l': link_path, 't': link_target})
                os.unlink(link_path)
            else:
                msg = _('Link path [%(l)s] exists, but is not a symbolic link')
                raise RuntimeError(msg % {'l': link_path})

        msg = _('Creating symbolic link [%(l)s] pointing to [%(s)s]')
        _LOG.debug(msg % {'l': link_path, 's': source_path})
        os.symlink(source_path, link_path)

    def _init_step_progress_report(self, step):
        """
        Initialize a progress sub-report for the given step.

        :param step: step to initialize a progress sub-report for
        :type  step: str
        """
        assert step in constants.PUBLISH_STEPS

        initialize_progress_sub_report(self.parent.progress_report[step])

    def report_progress(self, step, **report_details):
        """
        Report the current progress back to the conduit, make any updates to the
        current step as necessary.

        :param step: current step of publication process
        :type  step: str
        :param report_details: keyword argument updates to the current step's
                               progress sub-report (if any)
        """
        assert step in constants.PUBLISH_STEPS
        assert set(report_details).issubset(set(constants.PUBLISH_REPORT_KEYS))

        self.parent.progress_report[step].update(report_details)
        self.parent.conduit.set_progress(self.parent.progress_report)

    def _record_failure(self, step, e=None, tb=None):
        """
        Record a failure in a step's progress sub-report.

        :param step: current step that encountered a failure
        :type  step: str
        :param e: exception instance (if any)
        :type  e: Exception or None
        :param tb: traceback instance (if any)
        :type  tb: Traceback or None
        """
        assert step in constants.PUBLISH_STEPS

        self.parent.progress_report[step][constants.PROGRESS_FAILURES_KEY] += 1

        error_details = {'error': None,
                         'traceback': None}

        if tb is not None:
            error_details['traceback'] = '\n'.join(traceback.format_tb(tb))

        if e is not None:
            error_details['error'] = e.message or str(e)

        if error_details.values() != (None, None):
            self.parent.progress_report[step][constants.PROGRESS_ERROR_DETAILS_KEY]\
                .append(error_details)

    @staticmethod
    def _clear_directory(path, skip_list=()):
        """
        Clear out the contents of the given directory.

        :param path: path of the directory to clear out
        :type  path: str
        :param skip_list: list of files or directories to not remove
        :type  skip_list: list or tuple
        """
        _LOG.debug('Clearing out directory: %s' % path)

        if not os.path.exists(path):
            return

        for entry in os.listdir(path):

            if entry in skip_list:
                continue

            entry_path = os.path.join(path, entry)

            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)

            elif os.path.isfile(entry_path):
                os.unlink(entry_path)


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
                                        initialize_metadata_steps=[repomd_step],
                                        process_steps=steps,
                                        finalize_metadata_steps=[repomd_step],
                                        post_metadata_process_steps=[PublishToMasterStep(),
                                                                     PublishOverHttpStep(),
                                                                     PublishOverHttpsStep(),
                                                                     ClearOldMastersStep()])


class PublishRepoMetaDataStep(PublishStep):
    """
    Step for managing overall repo metadata
    """

    def __init__(self):
        super(PublishRepoMetaDataStep, self).__init__(constants.PUBLISH_REPOMD_STEP, TYPE_ID_RPM)
        self.repomd_file_context = None
        self.checksum_type = None

    def initialize_metadata(self):
        """
        open the metadata context
        """
        self.checksum_type = configuration.get_repo_checksum_type(self.parent.conduit,
                                                                  self.parent.config)
        self.repomd_file_context = RepomdXMLFileContext(self.get_working_dir(), self.checksum_type)
        self.repomd_file_context.initialize()

    def finalize_metadata(self):
        """
        Close the metadata context
        """
        if self.repomd_file_context:
            self.repomd_file_context.finalize()


class PublishRpmStep(PublishStep):
    """
    Step for publishing RPM & SRPM units
    """

    def __init__(self):
        super(PublishRpmStep, self).__init__(constants.PUBLISH_RPMS_STEP, TYPE_ID_RPM)
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

    def initialize_metadata(self):
        """
        Create each of the three metadata contexts required for publishing RPM & SRPM
        """
        total = self._get_total([TYPE_ID_RPM, TYPE_ID_SRPM])
        checksum_type = self.get_step(constants.PUBLISH_REPOMD_STEP).checksum_type
        self.file_lists_context = FilelistsXMLFileContext(self.get_working_dir(), total, checksum_type)
        self.other_context = OtherXMLFileContext(self.get_working_dir(), total, checksum_type)
        self.primary_context = PrimaryXMLFileContext(self.get_working_dir(), total, checksum_type)
        for context in (self.file_lists_context, self.other_context, self.primary_context):
            context.initialize()

    def finalize_metadata(self):
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
        :type unit: Unit
        """
        self._symlink_content(unit, self.get_working_dir())
        package_dir = self.get_step(constants.PUBLISH_DISTRIBUTION_STEP).package_dir
        if package_dir:
            self._symlink_content(unit, package_dir)

        for context in (self.file_lists_context, self.other_context, self.primary_context):
            context.add_unit_metadata(unit)


class PublishMetadataStep(PublishStep):
    """
    Publish extra metadata files that are copied from another repo and not generated
    """

    def __init__(self):
        super(PublishMetadataStep, self).__init__(constants.PUBLISH_METADATA_STEP,
                                                  TYPE_ID_YUM_REPO_METADATA_FILE)

    def process_unit(self, unit):
        """
        Copy the metadata file into place and add it tot he repomd file.

        :param unit: The unit to process
        :type unit: Unit
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


class PublishDrpmStep(PublishStep):
    """
    Publish Delta RPMS
    """

    def __init__(self):
        super(PublishDrpmStep, self).__init__(constants.PUBLISH_DELTA_RPMS_STEP, TYPE_ID_DRPM)
        self.context = None

    def initialize_metadata(self):
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
        :type unit: Unit
        """
        self._symlink_content(unit, os.path.join(self.get_working_dir(), 'drpms'))
        if self.get_step(constants.PUBLISH_DISTRIBUTION_STEP).package_dir:
            self._symlink_content(unit, os.path.join(
                self.get_step(constants.PUBLISH_DISTRIBUTION_STEP).package_dir, 'drpms'))
        self.context.add_unit_metadata(unit)

    def finalize_metadata(self):
        """
        Close & finalize each of the metadata files
        """
        if self.context:
            self.context.finalize()
            self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context.\
                add_metadata_file_metadata('prestodelta', self.context.metadata_file_path,
                                           self.context.checksum)


class PublishErrataStep(PublishStep):
    """
    Publish all errata
    """
    def __init__(self):
        super(PublishErrataStep, self).__init__(constants.PUBLISH_ERRATA_STEP, TYPE_ID_ERRATA)
        self.context = None

    def initialize_metadata(self):
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

    def finalize_metadata(self):
        """
        Finalize and write to disk the metadata and add the updateinfo file to the repomd
        """
        if self.context:
            self.context.finalize()
            self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context.\
                add_metadata_file_metadata('updateinfo', self.context.metadata_file_path,
                                           self.context.checksum)


class PublishCompsStep(PublishStep):
    def __init__(self):
        super(PublishCompsStep, self).__init__(constants.PUBLISH_COMPS_STEP,
                                               [TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY,
                                                TYPE_ID_PKG_ENVIRONMENT])
        self.comps_context = None

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

    def initialize_metadata(self):
        """
        Initialize all metadata associated with the comps file
        """
        checksum_type = self.get_step(constants.PUBLISH_REPOMD_STEP).checksum_type
        self.comps_context = PackageXMLFileContext(self.get_working_dir(), checksum_type)
        self.comps_context.initialize()

    def finalize_metadata(self):
        """
        Finalize all metadata associated with the comps file
        """
        if self.comps_context:
            self.comps_context.finalize()
            self.get_step(constants.PUBLISH_REPOMD_STEP).repomd_file_context.\
                add_metadata_file_metadata('group', self.comps_context.metadata_file_path,
                                           self.comps_context.checksum)


class PublishDistributionStep(PublishStep):
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

    def initialize_metadata(self):
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

    def is_skipped(self):
        return False

    def _get_total(self, id_list=None):
        return 1

    def get_unit_generator(self):
        return [configuration.get_master_publish_dir(self.parent.repo)]

    def process_unit(self, master_publish_dir):

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

    def is_skipped(self):
        return False

    def _get_total(self, id_list=None):
        return 1

    def get_unit_generator(self):
        return [configuration.get_master_publish_dir(self.parent.repo)]

    def process_unit(self, master_publish_dir):
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

    def is_skipped(self):
        """
        Check whether publishing over http is enabled
        """
        return not self.parent.config.get('http')

    def _get_total(self, id_list=None):
        """
        Get total will always be 1 since this isn't truly iterating over a unit
        """
        return 1

    def get_unit_generator(self):
        """
        Return a fake unit so that the process_unit method will be called
        """
        return [configuration.get_http_publish_dir(self.parent.config)]

    def process_unit(self, root_publish_dir):
        """
        Publish a directory from the repo to a target directory.
        """

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

    def is_skipped(self):
        """
        Check whether publishing over HTTPS is enabled
        """
        return not self.parent.config.get('https')

    def get_unit_generator(self):
        """
        For the units return the https publish directory
        """
        return [configuration.get_https_publish_dir(self.parent.config)]
