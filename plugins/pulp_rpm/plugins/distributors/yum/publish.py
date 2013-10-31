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

import copy
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

from . import configuration, metadata

# -- constants -----------------------------------------------------------------

_LOG = util.getLogger(__name__)

# -- publishing steps ----------------------------------------------------------

PUBLISH_RPMS_STEP = 'rpms'
PUBLISH_DELTA_RPMS_STEP = 'drpms'
PUBLISH_ERRATA_STEP = 'errata'
PUBLISH_PACKAGE_GROUPS_STEP = 'package_groups'
PUBLISH_PACKAGE_CATEGORIES_STEP = 'package_categories'
PUBLISH_DISTRIBUTION_STEP = 'distribution'
PUBLISH_METADATA_STEP = 'metadata'
PUBLISH_OVER_HTTP_STEP = 'publish_over_http'
PUBLISH_OVER_HTTPS_STEP = 'publish_over_https'

PUBLISH_STEPS = (PUBLISH_RPMS_STEP, PUBLISH_DELTA_RPMS_STEP, PUBLISH_ERRATA_STEP,
                 PUBLISH_PACKAGE_GROUPS_STEP, PUBLISH_PACKAGE_CATEGORIES_STEP,
                 PUBLISH_DISTRIBUTION_STEP, PUBLISH_METADATA_STEP,
                 PUBLISH_OVER_HTTP_STEP, PUBLISH_OVER_HTTPS_STEP)

# -- publishing step states ----------------------------------------------------

PUBLISH_NOT_STARTED_STATE = 'NOT_STARTED'
PUBLISH_IN_PROGRESS_STATE = 'IN_PROGRESS'
PUBLISH_SKIPPED_STATE = 'SKIPPED'
PUBLISH_FINISHED_STATE = 'FINISHED'
PUBLISH_FAILED_STATE = 'FAILED'
PUBLISH_CANCELED_STATE = 'CANCELED'

PUBLISH_STATES = (PUBLISH_NOT_STARTED_STATE, PUBLISH_IN_PROGRESS_STATE, PUBLISH_SKIPPED_STATE,
                  PUBLISH_FINISHED_STATE, PUBLISH_FAILED_STATE, PUBLISH_CANCELED_STATE)

# -- publishing reporting ------------------------------------------------------

STATE = 'state'
TOTAL = 'total'
PROCESSED = 'processed'
SUCCESSES = 'successes'
FAILURES = 'failures'
ERROR_DETAILS = 'error_details'

PUBLISH_REPORT_KEYWORDS = (STATE, TOTAL, PROCESSED, SUCCESSES, FAILURES, ERROR_DETAILS)

PROGRESS_REPORT = {PUBLISH_RPMS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_DELTA_RPMS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_ERRATA_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_PACKAGE_GROUPS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_PACKAGE_CATEGORIES_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_DISTRIBUTION_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_METADATA_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_OVER_HTTP_STEP: {STATE: PUBLISH_NOT_STARTED_STATE},
                   PUBLISH_OVER_HTTPS_STEP: {STATE: PUBLISH_NOT_STARTED_STATE}}

PROGRESS_SUB_REPORT = {STATE: PUBLISH_IN_PROGRESS_STATE,
                       TOTAL: 0,
                       PROCESSED: 0,
                       SUCCESSES: 0,
                       FAILURES: 0,
                       ERROR_DETAILS: []}

# -- final reporting -----------------------------------------------------------

NUMBER_DISTRIBUTION_UNITS_ATTEMPTED = 'num_distribution_units_attempted'
NUMBER_DISTRIBUTION_UNITS_ERROR = 'num_distribution_units_error'
NUMBER_DISTRIBUTION_UNITS_PUBLISHED = 'num_distribution_units_published'
NUMBER_PACKAGE_CATEGORIES_PUBLISHED = 'num_package_categories_published'
NUMBER_PACKAGE_GROUPS_PUBLISHED = 'num_package_groups_published'
NUMBER_PACKAGE_UNITS_ATTEMPTED = 'num_package_units_attempted'
NUMBER_PACKAGE_UNITS_ERRORS = 'num_package_units_error'
NUMBER_PACKAGE_UNITS_PUBLISHED = 'num_package_units_published'
RELATIVE_PATH = 'relative_path'
SKIP_METADATA_UPDATE = 'skip_metadata_update'

SUMMARY_REPORT = {NUMBER_DISTRIBUTION_UNITS_ATTEMPTED: 0,
                  NUMBER_DISTRIBUTION_UNITS_ERROR: 0,
                  NUMBER_DISTRIBUTION_UNITS_PUBLISHED: 0,
                  NUMBER_PACKAGE_CATEGORIES_PUBLISHED: 0,
                  NUMBER_PACKAGE_GROUPS_PUBLISHED: 0,
                  NUMBER_PACKAGE_UNITS_ATTEMPTED: 0,
                  NUMBER_PACKAGE_UNITS_ERRORS: 0,
                  NUMBER_PACKAGE_UNITS_PUBLISHED: 0,
                  RELATIVE_PATH: None,
                  SKIP_METADATA_UPDATE: False}

ERRORS_LIST = 'errors'
METADATA_GENERATION_TIME = 'time_metadata_sec'

DETAILS_REPORT = {ERRORS_LIST: [],
                  METADATA_GENERATION_TIME: 0}

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
        :return:
        """

        self.repo = repo
        self.conduit = publish_conduit
        self.config = config

        self.progress_report = copy.deepcopy(PROGRESS_REPORT)
        self.canceled = False
        self.package_dir = None

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

        # The distribution must be published first in case it specifies a packagesdir
        # that is used by the other publish items
        self._publish_distribution()
        self._publish_rpms()
        self._publish_errata()

        self._publish_over_http()
        self._publish_over_https()

        self._clear_directory(self.repo.working_dir)

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

            elif sub_report[STATE] is PUBLISH_NOT_STARTED_STATE:
                sub_report[STATE] = PUBLISH_SKIPPED_STATE

    # -- publish helper methods ------------------------------------------------

    def _publish_rpms(self): # and srpms too

        if self.canceled:
            return

        if TYPE_ID_RPM in self.skip_list:
            self._report_progress(PUBLISH_RPMS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Publishing RPMs/SRPMs for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_RPMS_STEP)

        total = self.repo.content_unit_counts.get(TYPE_ID_RPM, 0) + \
                self.repo.content_unit_counts.get(TYPE_ID_SRPM, 0)
        self.progress_report[PUBLISH_RPMS_STEP][TOTAL] = total

        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_RPM, TYPE_ID_SRPM],
                                           unit_fields=PACKAGE_FIELDS)
        unit_gen = self.conduit.get_units(criteria=criteria, as_generator=True)

        file_lists_context = metadata.FilelistsXMLFileContext(self.repo.working_dir, total)
        other_context = metadata.OtherXMLFileContext(self.repo.working_dir, total)
        primary_context = metadata.PrimaryXMLFileContext(self.repo.working_dir, total)

        for context in (file_lists_context, other_context, primary_context):
            context.initialize()

        try:
            for unit in unit_gen:

                if self.canceled:
                    return

                self._report_progress(PUBLISH_RPMS_STEP)
                self.progress_report[PUBLISH_RPMS_STEP][PROCESSED] += 1

                try:
                    self._symlink_content(unit, self.repo.working_dir)
                    if self.package_dir:
                        self._symlink_content(unit, self.package_dir)

                except Exception, e:
                    self._record_failure(PUBLISH_RPMS_STEP, e)
                    continue

                try:
                    for context in (file_lists_context, other_context, primary_context):
                        context.add_unit_metadata(unit)

                except Exception, e:
                    self._record_failure(PUBLISH_RPMS_STEP, e)
                    continue

                # success
                self.progress_report[PUBLISH_RPMS_STEP][SUCCESSES] += 1

        finally:
            for context in (file_lists_context, other_context, primary_context):
                context.finalize()

        if self.progress_report[PUBLISH_RPMS_STEP][FAILURES]:
            self._report_progress(PUBLISH_RPMS_STEP, state=PUBLISH_FAILED_STATE)

        else:
            self._report_progress(PUBLISH_RPMS_STEP, state=PUBLISH_FINISHED_STATE)

    def _publish_drpms(self):

        if self.canceled:
            return

        if TYPE_ID_DRPM in self.skip_list:
            self._report_progress(PUBLISH_DELTA_RPMS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Publishing DRPMs for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_DELTA_RPMS_STEP)

    def _publish_errata(self):

        if self.canceled:
            return

        if TYPE_ID_ERRATA in self.skip_list:
            self._report_progress(PUBLISH_ERRATA_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Publishing errata for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_ERRATA_STEP)

        total = self.repo.content_unit_counts.get(TYPE_ID_ERRATA, 0)

        if total == 0:
            self._report_progress(PUBLISH_ERRATA_STEP, state=PUBLISH_FINISHED_STATE, total=0)
            return

        self.progress_report[PUBLISH_ERRATA_STEP][TOTAL] = total

        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_ERRATA])

        erratum_unit_gen = self.conduit.get_units(criteria, as_generator=True)

        with metadata.UpdateinfoXMLFileContext(self.repo.working_dir) as updateinfo_context:

            self._report_progress(PUBLISH_ERRATA_STEP)

            for erratum_unit in erratum_unit_gen:

                try:
                    updateinfo_context.add_unit_metadata(erratum_unit)

                except Exception, e:
                    self._record_failure(PUBLISH_ERRATA_STEP, e)

                else:
                    self.progress_report[PUBLISH_ERRATA_STEP][SUCCESSES] += 1

                self.progress_report[PUBLISH_ERRATA_STEP][PROCESSED] += 1

        if self.progress_report[PUBLISH_ERRATA_STEP][FAILURES]:
            self._report_progress(PUBLISH_ERRATA_STEP, state=PUBLISH_FAILED_STATE)

        else:
            self._report_progress(PUBLISH_ERRATA_STEP, state=PUBLISH_FINISHED_STATE)


    def _publish_package_groups(self):

        if self.canceled:
            return

        if TYPE_ID_PKG_GROUP in self.skip_list:
            self._report_progress(PUBLISH_PACKAGE_GROUPS_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Publishing Package Groups for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_PACKAGE_GROUPS_STEP)

    def _publish_package_categories(self):

        if self.canceled:
            return

        if TYPE_ID_PKG_CATEGORY in self.skip_list:
            self._report_progress(PUBLISH_PACKAGE_CATEGORIES_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        self._init_step_progress_report(PUBLISH_PACKAGE_CATEGORIES_STEP)

    def _publish_distribution(self):
        """
        Publish all information about any distribution that is associated with a yum repo
        into the repository working directory
        """

        if self.canceled:
            return

        if TYPE_ID_DISTRO in self.skip_list:
            self._report_progress(PUBLISH_DISTRIBUTION_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Publishing Distribution for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_DISTRIBUTION_STEP)

        total = self.repo.content_unit_counts.get(TYPE_ID_DISTRO, 0)

        criteria = UnitAssociationCriteria(type_ids=TYPE_ID_DISTRO)
        unit_list = self.conduit.get_units(criteria=criteria)

        try:
            #There should only ever be 0 or 1 distribution associated with a repo
            if total == 0:
                #No distribution was found so skip this step
                _LOG.debug('No Distribution found for repository: %s' % self.repo.id)
                self._report_progress(PUBLISH_DISTRIBUTION_STEP, state=PUBLISH_FINISHED_STATE)
            elif total == 1:
                distribution = unit_list[0]

                self._publish_distribution_treeinfo(distribution)
                # create the Packages directory required for RHEL 5
                self._publish_distribution_packages_link(distribution)

                # Link any files referenced by the unit - This must happen after
                # creating the packages directory in case the packages directory
                # has to replace a symlink with a hard directory
                self._publish_distribution_files(distribution)


                self._report_progress(PUBLISH_DISTRIBUTION_STEP, state=PUBLISH_FINISHED_STATE)
            elif total > 1:
                msg = _('Error publishing repository %(repo)s.  More than one distribution found.') % \
                    {'repo': self.repo.id}
                _LOG.debug(msg)
                raise Exception(msg)
        except Exception, e:
                self._record_failure(PUBLISH_DISTRIBUTION_STEP, e)
                self._report_progress(PUBLISH_DISTRIBUTION_STEP, state=PUBLISH_FAILED_STATE)

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
        for treeinfo in constants.TREE_INFO_LIST:
            test_treeinfo_path = os.path.join(distribution_unit_storage_path, treeinfo)
            if os.path.exists(test_treeinfo_path):
                # we found the treeinfo file
                src_treeinfo_path = test_treeinfo_path
                break
        if src_treeinfo_path is not None:
            # create a symlink from content location to repo location.
            self.progress_report[PUBLISH_DISTRIBUTION_STEP][TOTAL] += 1
            symlink_treeinfo_path = os.path.join(self.repo.working_dir, treeinfo)
            _LOG.debug("creating treeinfo symlink from %s to %s" % (src_treeinfo_path,
                                                                    symlink_treeinfo_path))
            self._create_symlink(src_treeinfo_path, symlink_treeinfo_path)
            self.progress_report[PUBLISH_DISTRIBUTION_STEP][SUCCESSES] += 1
            self.progress_report[PUBLISH_DISTRIBUTION_STEP][PROCESSED] += 1

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
        self.progress_report[PUBLISH_DISTRIBUTION_STEP][TOTAL] += total_files
        _LOG.debug("Found %s distribution files to symlink" % total_files)

        source_path_dir = distribution_unit.storage_path
        symlink_dir = self.repo.working_dir
        for dfile in distro_files:
            source_path = os.path.join(source_path_dir, dfile['relativepath'])
            symlink_path = os.path.join(symlink_dir, dfile['relativepath'])
            self._create_symlink(source_path, symlink_path)
            self.progress_report[PUBLISH_DISTRIBUTION_STEP][SUCCESSES] += 1
            self.progress_report[PUBLISH_DISTRIBUTION_STEP][PROCESSED] += 1

    def _publish_distribution_packages_link(self, distribution_unit):
        """
        Create a Packages directory in the repo that is a sym link back to the root directory
        of the repository.  This is required for compatibility with RHEL 5.

        Also create the directory that is specified by packagesdir section in the config file

        :param distribution_unit: The unit for the distribution from which the list
                                  of files to be published should be pulled from.
        :type distribution_unit: AssociatedUnit
        """
        symlink_dir = self.repo.working_dir

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
                        % {'repo': self.repo.id, 'packagedir': self.package_dir})
                _LOG.info(msg)
                raise InvalidValue(KEY_PACKAGEDIR)

            self.package_dir = distribution_unit.metadata[KEY_PACKAGEDIR]
            if os.path.islink(package_path):
                # a package path exists as a symlink we are going to remove it since
                # the _create_symlink will create a real directory
                os.unlink(package_path)

        if self.package_dir is not 'Packages':
            # create the Packages symlink to the content dir, in the content dir
            packages_symlink_path = os.path.join(symlink_dir, 'Packages')
            self._create_symlink("./", packages_symlink_path)

    def _publish_metadata(self):

        if self.canceled:
            return

        if TYPE_ID_YUM_REPO_METADATA_FILE in self.skip_list:
            self._report_progress(PUBLISH_METADATA_STEP, state=PUBLISH_SKIPPED_STATE)
            return

        _LOG.debug('Publishing Yum Repository Metadata for repository: %s' % self.repo.id)

        self._init_step_progress_report(PUBLISH_METADATA_STEP)

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

        self.progress_report[step] = copy.deepcopy(PROGRESS_SUB_REPORT)

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
        summary = copy.deepcopy(SUMMARY_REPORT)
        details = copy.deepcopy(DETAILS_REPORT)

        summary[RELATIVE_PATH] = configuration.get_repo_relative_path(self.repo, self.config)

        if self.progress_report[PUBLISH_METADATA_STEP][STATE] is PUBLISH_SKIPPED_STATE:
            summary[SKIP_METADATA_UPDATE] = True

        for step in PUBLISH_STEPS:

            # using .get() because the sub-sections won't be there if the step was skipped
            total = self.progress_report[step].get(TOTAL, 0)
            failures = self.progress_report[step].get(FAILURES, 0)
            successes = self.progress_report[step].get(SUCCESSES, 0)

            # XXX include errata?
            if step in (PUBLISH_RPMS_STEP, PUBLISH_DELTA_RPMS_STEP):
                summary[NUMBER_PACKAGE_UNITS_ATTEMPTED] += total
                summary[NUMBER_PACKAGE_UNITS_ERRORS] += failures
                summary[NUMBER_PACKAGE_UNITS_PUBLISHED] += successes

            elif step is PUBLISH_DISTRIBUTION_STEP:
                summary[NUMBER_DISTRIBUTION_UNITS_ATTEMPTED] = total
                summary[NUMBER_DISTRIBUTION_UNITS_ERROR] = failures
                summary[NUMBER_DISTRIBUTION_UNITS_PUBLISHED] = successes

            # XXX expand this to include attempted and error?
            elif step is PUBLISH_PACKAGE_CATEGORIES_STEP:
                summary[NUMBER_PACKAGE_CATEGORIES_PUBLISHED] = successes

            # XXX expand this to include attempted and error?
            elif step is PUBLISH_PACKAGE_GROUPS_STEP:
                summary[NUMBER_PACKAGE_GROUPS_PUBLISHED] = successes

            details[ERRORS_LIST].extend(self.progress_report[step].get(ERROR_DETAILS, []))

        # XXX not sure this is the best criteria, maybe 1 or more failure states?
        if details[ERRORS_LIST]:
            return self.conduit.build_failure_report(summary, details)

        return self.conduit.build_success_report(summary, details)

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

