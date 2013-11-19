# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import os
import shutil
import sys
import traceback
from gettext import gettext as _
from pprint import pformat

from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.exceptions import InvalidValue

from pulp_rpm.common import constants
from pulp_rpm.common.ids import (
    TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO, TYPE_ID_YUM_REPO_METADATA_FILE)
from pulp_rpm.yum_plugin import util
from pulp_rpm.plugins.importers.yum.parse.treeinfo import KEY_PACKAGEDIR

from . import configuration
from .metadata.filelists import FilelistsXMLFileContext
from .metadata.metadata import REPO_DATA_DIR_NAME
from .metadata.other import OtherXMLFileContext
from .metadata.prestodelta import PrestodeltaXMLFileContext
from .metadata.primary import PrimaryXMLFileContext
from .metadata.repomd import RepomdXMLFileContext, DEFAULT_CHECKSUM_TYPE
from .metadata.updateinfo import UpdateinfoXMLFileContext
from .metadata.package import PackageXMLFileContext
from .reporting import (
    PUBLISH_RPMS_STEP, PUBLISH_DELTA_RPMS_STEP, PUBLISH_ERRATA_STEP,
    PUBLISH_PACKAGE_GROUPS_STEP, PUBLISH_PACKAGE_CATEGORIES_STEP,
    PUBLISH_DISTRIBUTION_STEP, PUBLISH_METADATA_STEP, PUBLISH_OVER_HTTP_STEP,
    PUBLISH_OVER_HTTPS_STEP, PUBLISH_STEPS, PUBLISH_NOT_STARTED_STATE,
    PUBLISH_IN_PROGRESS_STATE, PUBLISH_SKIPPED_STATE, PUBLISH_FINISHED_STATE,
    PUBLISH_FAILED_STATE, PUBLISH_CANCELED_STATE, STATE, TOTAL, PROCESSED,
    SUCCESSES, FAILURES, ERROR_DETAILS, PUBLISH_REPORT_KEYWORDS,
    new_progress_report, initialize_progress_sub_report, build_final_report)

# -- constants -----------------------------------------------------------------

_LOG = util.getLogger(__name__)

# -- package fields ------------------------------------------------------------

PACKAGE_FIELDS = ['id', 'name', 'version', 'release', 'arch', 'epoch',
                  '_storage_path', 'checksum', 'checksumtype', 'repodata']

# -- publisher class -----------------------------------------------------------


class Publisher(object):
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

        self.repo = repo
        self.conduit = publish_conduit
        self.config = config

        self.progress_report = new_progress_report()
        self.canceled = False

        self.package_dir = None
        self.repomd_file_context = None
        self.package_context = None

    @property
    def skip_list(self):
        skip = self.config.get('skip', [])
        # there is a chance that the skip list is actually a dictionary with a
        # boolean to indicate whether or not each item should be skipped
        # if that is the case iterate over it to build a list of the items
        # that should be skipped instead
        if type(skip) is dict:
            return [k for k, v in skip.items() if v]
        return skip

    # -- publish api methods ---------------------------------------------------

    def publish(self):
        """
        Publish the contents of the repository and their metadata via HTTP/HTTPS.

        :return: report describing the publication
        :rtype:  pulp.plugins.model.PublishReport
        """
        _LOG.debug('Starting Yum HTTP/HTTPS publish for repository: %s' % self.repo.id)

        if not os.path.exists(self.repo.working_dir):
            os.makedirs(self.repo.working_dir, mode=0770)

        checksum_type = configuration.get_repo_checksum_type(self.conduit, self.config)
        try:
            with RepomdXMLFileContext(self.repo.working_dir, checksum_type) as self.repomd_file_context:
                # The distribution must be published first in case it specifies a packagesdir
                # that is used by the other publish items
                self._publish_distribution()
                self._publish_rpms()
                self._publish_drpms()
                self._publish_errata()
                self._publish_comps()

            self._publish_over_http()
            self._publish_over_https()

            self._clear_directory(self.repo.working_dir)
        except Exception, e:
            # do nothing with the exception as the returned report has the details.
            pass

        _LOG.debug('Publish completed with progress:\n%s' % pformat(self.progress_report))
        return self._build_final_report()

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

            if sub_report[STATE] is PUBLISH_IN_PROGRESS_STATE:
                sub_report[STATE] = PUBLISH_CANCELED_STATE

    # -- publish helper methods ------------------------------------------------

    def _publish_rpms(self):
        """
        Wrapper for publishing RPM & SRPM
        """
        PublishRpmStep(self).process()

    def _publish_drpms(self):
        """
        Wrapper for publishing Delta RPMS
        """
        PublishDrpmStep(self).process()

    def _publish_errata(self):
        """
        Wrapper for publishing errata
        """
        PublishErrataStep(self).process()

    def _publish_comps(self):
        """
        Publish package groups and categories and update the repomd.xml file.
        """
        groups_step = PublishPackageGroupsStep(self)
        categories_step = PublishPackageCategoriesStep(self)
        if (groups_step._get_total() + categories_step._get_total()) > 0:
            groups_file = None
            with PackageXMLFileContext(self.repo.working_dir) as self.package_context:
                PublishPackageGroupsStep(self).process()
                PublishPackageCategoriesStep(self).process()
                groups_file = self.package_context.metadata_file_path
            self.repomd_file_context.add_metadata_file_metadata('group', groups_file)

    def _publish_distribution(self):
        """
        Publish all information about any distribution that is associated with a yum repo
        into the repository working directory
        """
        PublishDistributionStep(self).process()

    def _publish_metadata(self):
        """
        Wrapper for publishing non-generated metadata files
        """
        PublishMetadataStep(self).process()

    def _publish_over_http(self):

        if self.canceled:
            return

        if not self.config.get('http'):
            self._report_progress(PUBLISH_OVER_HTTP_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Creating HTTP published directory for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_OVER_HTTP_STEP)
        self._report_progress(PUBLISH_OVER_HTTP_STEP, total=1)

        root_http_publish_dir = configuration.get_http_publish_dir(self.config)
        repo_relative_dir = configuration.get_repo_relative_path(self.repo, self.config)
        repo_http_publish_dir = os.path.join(root_http_publish_dir, repo_relative_dir)

        try:
            if os.path.exists(repo_http_publish_dir):
                _LOG.debug('Removing old HTTP published directory: %s' % repo_http_publish_dir)
                shutil.rmtree(repo_http_publish_dir)

            _LOG.debug('Copying tree from %s to %s' % (self.repo.working_dir, repo_http_publish_dir))
            shutil.copytree(self.repo.working_dir, repo_http_publish_dir, symlinks=True)

            util.generate_listing_files(root_http_publish_dir, repo_http_publish_dir)

        except Exception, e:
            tb = sys.exc_info()[2]
            self._record_failure(PUBLISH_OVER_HTTP_STEP, e, tb)

        else:
            self.progress_report[PUBLISH_OVER_HTTP_STEP][SUCCESSES] = 1

        self.progress_report[PUBLISH_OVER_HTTP_STEP][PROCESSED] = 1

        if self.progress_report[PUBLISH_OVER_HTTP_STEP][SUCCESSES]:
            self._report_progress(PUBLISH_OVER_HTTP_STEP, state=PUBLISH_FINISHED_STATE)

        else:
            self._report_progress(PUBLISH_OVER_HTTP_STEP, state=PUBLISH_FAILED_STATE)

    def _publish_over_https(self):

        if self.canceled:
            return

        if not self.config.get('https'):
            self._report_progress(PUBLISH_OVER_HTTPS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Creating HTTPS published directory for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_OVER_HTTPS_STEP)
        self._report_progress(PUBLISH_OVER_HTTPS_STEP, total=1)

        root_https_publish_dir = configuration.get_https_publish_dir(self.config)
        repo_relative_path = configuration.get_repo_relative_path(self.repo, self.config)
        repo_https_publish_dir = os.path.join(root_https_publish_dir, repo_relative_path)

        try:
            if os.path.exists(repo_https_publish_dir):
                _LOG.debug('Removing old HTTPS published directory: %s' % repo_https_publish_dir)
                shutil.rmtree(repo_https_publish_dir)

            _LOG.debug('Copying tree from %s to %s' % (self.repo.working_dir, repo_https_publish_dir))
            shutil.copytree(self.repo.working_dir, repo_https_publish_dir, symlinks=True)

            util.generate_listing_files(root_https_publish_dir, repo_https_publish_dir)

        except Exception, e:
            tb = sys.exc_info()[2]
            self._record_failure(PUBLISH_OVER_HTTPS_STEP, e, tb)

        else:
            self.progress_report[PUBLISH_OVER_HTTPS_STEP][SUCCESSES] = 1

        self.progress_report[PUBLISH_OVER_HTTPS_STEP][PROCESSED] = 1

        if self.progress_report[PUBLISH_OVER_HTTPS_STEP][SUCCESSES]:
            self._report_progress(PUBLISH_OVER_HTTPS_STEP, state=PUBLISH_FINISHED_STATE)

        else:
            self._report_progress(PUBLISH_OVER_HTTPS_STEP, state=PUBLISH_FAILED_STATE)

        # XXX I believe the process_repo_auth_cert_bundle needs to go around here somewhere

    # -- progress methods ------------------------------------------------------

    def _init_step_progress_report(self, step):
        """
        Initialize a progress sub-report for the given step.

        :param step: step to initialize a progress sub-report for
        :type  step: str
        """
        assert step in PUBLISH_STEPS

        initialize_progress_sub_report(self.progress_report[step])

    def _report_progress(self, step, **report_details):
        """
        Report the current progress back to the conduit, make any updates to the
        current step as necessary.

        :param step: current step of publication process
        :type  step: str
        :param report_details: keyword argument updates to the current step's
                               progress sub-report (if any)
        """
        assert step in PUBLISH_STEPS
        assert set(report_details).issubset(set(PUBLISH_REPORT_KEYWORDS))

        self.progress_report[step].update(report_details)
        self.conduit.set_progress(self.progress_report)

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
        assert step in PUBLISH_STEPS

        self.progress_report[step][FAILURES] += 1

        error_details = []

        if tb is not None:
            error_details.extend(traceback.format_tb(tb))

        if e is not None:
            error_details.append(e.message or str(e))

        if error_details:
            self.progress_report[step][ERROR_DETAILS].append('\n'.join(error_details))

    def _build_final_report(self):
        """
        :return: report describing the publish run
        :rtype:  pulp.plugins.model.PublishReport
        """

        relative_path = configuration.get_repo_relative_path(self.repo, self.config)

        return build_final_report(self.conduit, relative_path, self.progress_report)


    # -- cleanup ---------------------------------------------------------------

    @staticmethod
    def _clear_directory(path):
        """
        Clear out the contents of the given directory.

        :param path: path of the directory to clear out
        :type  path: str
        """
        _LOG.debug('Clearing out directory: %s' % path)

        if not os.path.exists(path):
            return

        for entry in os.listdir(path):
            entry_path = os.path.join(path, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)
            elif os.path.isfile(entry_path) or os.path.islink(entry_path):
                os.unlink(entry_path)


class PublishStep(object):

    def __init__(self, parent, step_id, unit_type):
        self.parent = parent
        self.step_id = step_id
        self.unit_type = unit_type

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
        It will update the step progress and throw an exception on error.
        """
        if self.parent.canceled:
            return

        if self.is_skipped():
            self.parent._report_progress(self.step_id, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Publishing Packages of type %(type)s for repository: %(repo)s' %
                   {'type': self.unit_type, 'repo': self.parent.repo.id})

        self.parent._init_step_progress_report(self.step_id)

        total = self._get_total(self.unit_type)
        if total == 0:
            self.parent._report_progress(self.step_id, state=PUBLISH_FINISHED_STATE, total=0)
            return

        try:
            self.initialize_metadata()
            self.parent.progress_report[self.step_id][TOTAL] = total
            package_unit_generator = self.get_unit_generator()
            self.parent._report_progress(self.step_id)

            for package_unit in package_unit_generator:
                if self.parent.canceled:
                    return
                self.parent.progress_report[self.step_id][PROCESSED] += 1
                self.process_unit(package_unit)
                self.parent.progress_report[self.step_id][SUCCESSES] += 1
        except Exception, e:
            self.parent._record_failure(self.step_id, e)
            self.parent._report_progress(self.step_id, state=PUBLISH_FAILED_STATE)
            raise e
        finally:
            self.finalize_metadata()
        self.parent._report_progress(self.step_id, state=PUBLISH_FINISHED_STATE)

    def _get_total(self, id_list=None):
        if id_list is None:
            id_list = self.unit_type
        total = 0
        if isinstance(id_list, list):
            for id in id_list:
                total += self.parent.repo.content_unit_counts.get(id, 0)
        else:
            total = self.parent.repo.content_unit_counts.get(id_list, 0)
        return total

    # -- linking methods -------------------------------------------------------

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

        :param source_path: path of the source to link to
        :type  source_path: str
        :param link_path: path of the link
        :type  link_path: str
        """

        if not os.path.exists(source_path):
            msg = _('Cannot create a symlink to a non-existent source [%(s)s]')
            raise RuntimeError(msg % {'s': source_path})

        if link_path.endswith('/'):
            link_path = link_path[:-1]

        link_parent_dir = os.path.dirname(link_path)

        if not os.path.exists(link_parent_dir):
            os.makedirs(link_parent_dir, mode=0770)
        elif not os.access(link_parent_dir, os.R_OK | os.W_OK | os.X_OK):
            msg = _('Insufficient permissions to create symlink in directory [%(d)s]')
            raise RuntimeError(msg % {'d': link_parent_dir})
        elif os.path.lexists(link_path):
            if os.path.islink(link_path):
                link_target = os.readlink(link_path)
                if link_target == source_path:
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


class PublishRpmStep(PublishStep):
    """
    Step for publishing RPM & SRPM units
    """

    def __init__(self, parent):
        super(PublishRpmStep, self).__init__(parent, PUBLISH_RPMS_STEP, TYPE_ID_RPM)

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
        self.file_lists_context = FilelistsXMLFileContext(self.parent.repo.working_dir, total)
        self.other_context = OtherXMLFileContext(self.parent.repo.working_dir, total)
        self.primary_context = PrimaryXMLFileContext(self.parent.repo.working_dir, total)
        for context in (self.file_lists_context, self.other_context, self.primary_context):
            context.initialize()

    def finalize_metadata(self):
        """
        Close each context and write it to the repomd file
        """
        for context in (self.file_lists_context, self.other_context, self.primary_context):
            context.finalize()
        self.parent.repomd_file_context.add_metadata_file_metadata('filelists', self.file_lists_context.metadata_file_path)
        self.parent.repomd_file_context.add_metadata_file_metadata('other', self.other_context.metadata_file_path)
        self.parent.repomd_file_context.add_metadata_file_metadata('primary', self.primary_context.metadata_file_path)

    def process_unit(self, unit):
        """
        Link the unit to the content directory and the package_dir

        :param unit: The unit to process
        :type unit: Unit
        """
        self._symlink_content(unit, self.parent.repo.working_dir)
        if self.parent.package_dir:
            self._symlink_content(unit, self.parent.package_dir)


class PublishMetadataStep(PublishStep):
    """
    Publish extra metadata files that are copied from another repo and not generated
    """

    def __init__(self, parent):
        super(PublishMetadataStep, self).__init__(parent, PUBLISH_METADATA_STEP,
                                                  TYPE_ID_YUM_REPO_METADATA_FILE)

    def process_unit(self, unit):
        """
        Copy the metadata file into place and add it tot he repomd file.

        :param unit: The unit to process
        :type unit: Unit
        """
        # Copy the file to the location on disk where the published repo is built
        publish_location_relative_path = os.path.join(self.parent.repo.working_dir,
                                                      REPO_DATA_DIR_NAME)

        metadata_file_name = os.path.basename(unit.storage_path)
        link_path = os.path.join(publish_location_relative_path, metadata_file_name)
        self._create_symlink(unit.storage_path, link_path)

        # Add the proper relative reference to the metadata file to repomd
        repomd_relative_filename = os.path.join(REPO_DATA_DIR_NAME, metadata_file_name)
        self.parent.repomd_file_context.add_metadata_file_metadata(
            unit.unit_key['data_type'], repomd_relative_filename)


class PublishDrpmStep(PublishStep):
    """
    Publish Delta RPMS
    """

    def __init__(self, parent):
        super(PublishDrpmStep, self).__init__(parent, PUBLISH_DELTA_RPMS_STEP, TYPE_ID_DRPM)

    def initialize_metadata(self):
        """
        Initialize the PrestoDelta metadata file
        """
        self.context = PrestodeltaXMLFileContext(self.parent.repo.working_dir)
        self.context.initialize()

    def process_unit(self, unit):
        """
        Link the unit to the drpm content directory and the package_dir

        :param unit: The unit to process
        :type unit: Unit
        """
        self._symlink_content(unit, os.path.join(self.parent.repo.working_dir, 'drpms'))
        if self.parent.package_dir:
            self._symlink_content(unit, os.path.join(self.parent.package_dir, 'drpms'))

    def finalize_metadata(self):
        """
        Close & finalize each of the metadata files
        """
        self.context.finalize()
        self.parent.repomd_file_context.add_metadata_file_metadata('prestodelta',
                                                                   self.context.metadata_file_path)


class PublishErrataStep(PublishStep):
    """
    Publish all errata
    """
    def __init__(self, parent):
        super(PublishErrataStep, self).__init__(parent, PUBLISH_ERRATA_STEP, TYPE_ID_ERRATA)

    def initialize_metadata(self):
        """
        Initialize the UpdateInfo file and set the method used to process the unit to the
        one that is built into the UpdateinfoXMLFileContext
        """
        self.context = UpdateinfoXMLFileContext(self.parent.repo.working_dir)
        self.context.initialize()
        self.process_unit = self.context.add_unit_metadata

    def finalize_metadata(self):
        """
        Finalize and write to disk the metadata and add the updateinfo file to the repomd
        """
        self.context.finalize()
        self.parent.repomd_file_context.add_metadata_file_metadata('updateinfo',
                                                                   self.context.metadata_file_path)


class PublishPackageGroupsStep(PublishStep):
    """
    Publish all package groups to the comps metadata file
    """
    def __init__(self, parent):
        super(PublishPackageGroupsStep, self).__init__(parent, PUBLISH_PACKAGE_GROUPS_STEP,
                                                       TYPE_ID_PKG_GROUP)

    def initialize_metadata(self):
        """
        Use the built in method for processing the metadata.  This is added here
        since the step is initialized before the context exists
        """
        self.process_unit = self.parent.package_context.add_package_group_unit_metadata


class PublishPackageCategoriesStep(PublishStep):
    """
    Publish all package categories to the comps metadata file
    """
    def __init__(self, parent):
        super(PublishPackageCategoriesStep, self).__init__(parent, PUBLISH_PACKAGE_CATEGORIES_STEP,
                                                           TYPE_ID_PKG_CATEGORY)

    def initialize_metadata(self):
        """
        Use the built in method for processing the metadata.  This is added here
        since the step is initialized before the context exists
        """
        self.process_unit = self.parent.package_context.add_package_category_unit_metadata


class PublishDistributionStep(PublishStep):
    """
    Publish distribution files associated with the anaconda installer
    """

    def __init__(self, parent):
        super(PublishDistributionStep, self).__init__(parent, PUBLISH_DISTRIBUTION_STEP, TYPE_ID_DISTRO)

    def initialize_metadata(self):
        """
        When initializing the metadata verify that only one distribution exists
        """
        if self._get_total() > 1:
            msg = _('Error publishing repository %(repo)s.  More than one distribution found.') % \
                    {'repo': self.parent.repo.id}
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
            self.parent.progress_report[PUBLISH_DISTRIBUTION_STEP][TOTAL] += 1
            symlink_treeinfo_path = os.path.join(self.parent.repo.working_dir, treeinfo_file_name)
            _LOG.debug("creating treeinfo symlink from %s to %s" % (src_treeinfo_path,
                                                                    symlink_treeinfo_path))
            self._create_symlink(src_treeinfo_path, symlink_treeinfo_path)
            self.parent.progress_report[PUBLISH_DISTRIBUTION_STEP][SUCCESSES] += 1
            self.parent.progress_report[PUBLISH_DISTRIBUTION_STEP][PROCESSED] += 1

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
        self.parent.progress_report[PUBLISH_DISTRIBUTION_STEP][TOTAL] += total_files
        _LOG.debug("Found %s distribution files to symlink" % total_files)

        source_path_dir = distribution_unit.storage_path
        symlink_dir = self.parent.repo.working_dir
        for dfile in distro_files:
            source_path = os.path.join(source_path_dir, dfile['relativepath'])
            symlink_path = os.path.join(symlink_dir, dfile['relativepath'])
            self._create_symlink(source_path, symlink_path)
            self.parent.progress_report[PUBLISH_DISTRIBUTION_STEP][SUCCESSES] += 1
            self.parent.progress_report[PUBLISH_DISTRIBUTION_STEP][PROCESSED] += 1

    def _publish_distribution_packages_link(self, distribution_unit):
        """
        Create a Packages directory in the repo that is a sym link back to the root directory
        of the repository.  This is required for compatibility with RHEL 5.

        Also create the directory that is specified by packagesdir section in the config file

        :param distribution_unit: The unit for the distribution from which the list
                                  of files to be published should be pulled from.
        :type distribution_unit: AssociatedUnit
        """
        symlink_dir = self.parent.repo.working_dir

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
                        % {'repo': self.parent.repo.id, 'packagedir': self.parent.package_dir})
                _LOG.info(msg)
                raise InvalidValue(KEY_PACKAGEDIR)

            self.parent.package_dir = distribution_unit.metadata[KEY_PACKAGEDIR]
            if os.path.islink(package_path):
                # a package path exists as a symlink we are going to remove it since
                # the _create_symlink will create a real directory
                os.unlink(package_path)

        if self.parent.package_dir is not 'Packages':
            # create the Packages symlink to the content dir, in the content dir
            packages_symlink_path = os.path.join(symlink_dir, 'Packages')
            self._create_symlink("./", packages_symlink_path)