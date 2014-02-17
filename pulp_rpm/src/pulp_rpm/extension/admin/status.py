# Copyright (c) 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

"""
Contains functionality related to rendering the progress report for a the RPM
plugins (both the sync and publish operations).
"""

from gettext import gettext as _
import functools

from pulp.client.commands.repo.sync_publish import StatusRenderer

from pulp_rpm.common import constants, ids, models
from pulp_rpm.common.status_utils import (
    render_general_spinner_step, render_itemized_in_progress_state,
    render_publish_step_in_progress_state)


class CancelException(Exception):
    pass


class RpmStatusRenderer(StatusRenderer):

    def __init__(self, context):
        super(RpmStatusRenderer, self).__init__(context)

        # Sync Steps
        self.metadata_last_state = constants.STATE_NOT_STARTED
        self.download_last_state = constants.STATE_NOT_STARTED
        self.distribution_sync_last_state = constants.STATE_NOT_STARTED
        self.errata_last_state = constants.STATE_NOT_STARTED
        self.comps_last_state = constants.STATE_NOT_STARTED

        # Publish Steps
        self.publish_steps_last_state = dict.fromkeys(constants.PUBLISH_STEPS,
                                                      constants.STATE_NOT_STARTED)

        self.distribution_publish_last_state = constants.STATE_NOT_STARTED
        self.generate_metadata_last_state = constants.STATE_NOT_STARTED
        self.publish_http_last_state = constants.STATE_NOT_STARTED
        self.publish_https_last_state = constants.STATE_NOT_STARTED

        # UI Widgets
        self.metadata_spinner = self.prompt.create_spinner()
        self.download_bar = self.prompt.create_progress_bar()
        self.distribution_sync_bar = self.prompt.create_progress_bar()
        self.errata_spinner = self.prompt.create_spinner()
        self.comps_spinner = self.prompt.create_spinner()

        self.packages_bar = self.prompt.create_progress_bar()
        self.distribution_publish_bar = self.prompt.create_progress_bar()
        self.generate_metadata_spinner = self.prompt.create_spinner()
        self.publish_http_spinner = self.prompt.create_spinner()
        self.publish_https_spinner = self.prompt.create_spinner()

    def display_report(self, progress_report):
        """
        Displays the contents of the progress report to the user. This will
        aggregate the calls to render individual sections of the report.
        """

        # There's a small race condition where the task will indicate it's
        # begun running but the importer has yet to submit a progress report
        # (or it has yet to be saved into the task). This should be alleviated
        # by the if statements below.
        try:
            # Sync Steps
            if 'yum_importer' in progress_report:
                self.render_metadata_step(progress_report)
                self.render_download_step(progress_report)
                self.render_distribution_sync_step(progress_report)
                self.render_errata_step(progress_report)
                self.render_comps_step(progress_report)

            # Publish Steps
            if ids.YUM_DISTRIBUTOR_ID in progress_report:
                self.render_packages_step(progress_report, constants.PUBLISH_DISTRIBUTION_STEP)
                self.render_packages_step(progress_report, constants.PUBLISH_RPMS_STEP)
                self.render_packages_step(progress_report, constants.PUBLISH_DELTA_RPMS_STEP)
                self.render_packages_step(progress_report, constants.PUBLISH_ERRATA_STEP)
                self.render_packages_step(progress_report, constants.PUBLISH_COMPS_STEP)
                self.render_packages_step(progress_report, constants.PUBLISH_METADATA_STEP)
                self.render_publish_https_step(progress_report)
                self.render_publish_http_step(progress_report)

        except CancelException:
            self.prompt.render_failure_message(_('Operation cancelled.'))

    def check_for_cancelled_state(self, state):
        if state == constants.STATE_CANCELLED:
            raise CancelException

    # -- render sync steps -----------------------------------------------------

    def render_metadata_step(self, progress_report):

        # Example Data:
        # "metadata": {
        #    "state": "FINISHED"
        # }

        current_state = progress_report['yum_importer']['metadata']['state']
        self.check_for_cancelled_state(current_state)
        def update_func(new_state):
            self.metadata_last_state = new_state
        render_general_spinner_step(self.prompt, self.metadata_spinner, current_state, self.metadata_last_state, _('Downloading metadata...'), update_func)

        if self.metadata_last_state == constants.STATE_FAILED:
            self.prompt.render_failure_message(progress_report['yum_importer']['metadata']['error'])

    def render_distribution_sync_step(self, progress_report):
        data = progress_report['yum_importer']['distribution']
        state = data['state']
        self.check_for_cancelled_state(state)
        # Render nothing if we haven't begun yet or if this step is skipped
        if state in (constants.STATE_NOT_STARTED, constants.STATE_SKIPPED):
            return

        # Only render this on the first non-not-started state
        if self.distribution_sync_last_state == constants.STATE_NOT_STARTED:
            self.prompt.write(_('Downloading distribution files...'))

        if (state in (constants.STATE_RUNNING, constants.STATE_COMPLETE) and
                    self.distribution_sync_last_state not in constants.COMPLETE_STATES):
            render_itemized_in_progress_state(self.prompt, data, _('distributions'), self.distribution_sync_bar, state)

        elif state in constants.STATE_FAILED and \
             self.distribution_sync_last_state not in constants.COMPLETE_STATES:

            self.prompt.render_spacer()
            self.prompt.render_failure_message(_('Errors encountered during distribution sync:'))

            # TODO: read this from config
            # display_error_count = self.context.extension_config.getint('main', 'num_display_errors')
            display_error_count = 5

            num_errors = min(len(data['error_details']), display_error_count)

            if num_errors > 0:

                # Each error is a list of filename and dict of details
                # Example:
                #    "error_details": [
                #      [
                #        "file:///mnt/iso/f18/images/boot.iso",
                #        {
                #          "response_code": 0,
                #          "error_message": "Couldn't open file /mnt/iso/f18/images/boot.iso",
                #          "error_code": 37
                #        }
                #      ]
                #    ],

                for i in range(0, num_errors):
                    error = data['error_details'][i]

                    message_data = {
                        'filename' : error[0],
                        'message' : error[1]['error_message'],
                        'code' : error[1]['error_code'],
                    }

                    template  = 'File: %(filename)s\n'
                    template += 'Error Code:   %(code)s\n'
                    template += 'Error Message: %(message)s'
                    message = template % message_data

                    self.prompt.render_failure_message(message)
                self.prompt.render_spacer()

        self.distribution_sync_last_state = state

    def render_download_step(self, progress_report):
        """
        :type  progress_report: pulp_rpm.plugins.importers.yum.report.ContentReport
        """
        data = progress_report['yum_importer']['content']
        state = data['state']
        self.check_for_cancelled_state(state)

        # Render nothing if we haven't begun yet or if this step is skipped
        if state in (constants.STATE_NOT_STARTED, constants.STATE_SKIPPED):
            return

        details = data['details']

        # Only render this on the first non-not-started state
        if self.download_last_state == constants.STATE_NOT_STARTED:
            self.prompt.write(_('Downloading repository content...'))

        # If it's running or finished, the output is still the same. This way,
        # if the status is viewed after this step, the content download
        # summary is still available.

        if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE) and self.download_last_state not in constants.COMPLETE_STATES:

            self.download_last_state = state

            template  = _('RPMs:       %(rpm_done)s/%(rpm_total)s items\n'
                          'Delta RPMs: %(drpm_done)s/%(drpm_total)s items\n')

            bar_message = template % details

            overall_done = data['size_total'] - data['size_left']
            overall_total = data['size_total']

            # If all of the packages are already downloaded and up to date,
            # the total bytes to process will be 0. This means the download
            # step is basically finished, so fill the progress bar.
            if overall_total == 0:
                overall_total = overall_done = 1

            self.download_bar.render(overall_done, overall_total, message=bar_message)

            if state == constants.STATE_COMPLETE:
                self.prompt.write(_('... completed'))
                self.prompt.render_spacer()

                # If there are any errors, write them out here
                # TODO: read this from config
                # display_error_count = self.context.extension_config.getint('main', 'num_display_errors')
                display_error_count = 5

                num_errors = min(len(data['error_details']), display_error_count)

                if num_errors > 0:
                    self.prompt.render_failure_message(_('Individual package errors encountered during sync:'))

                    for i in range(0, num_errors):
                        error = data['error_details'][i]
                        if error[constants.ERROR_CODE] == constants.ERROR_CHECKSUM_TYPE_UNKNOWN:
                            message_data = {
                                'name': error[constants.NAME],
                                'checksum_type': error[constants.CHECKSUM_TYPE],
                                'accepted': ','.join(error.get(constants.ACCEPTED_CHECKSUM_TYPES, []))
                            }
                            template = _('Package: %(name)s\nError: An invalid checksum type '
                                         '(%(checksum_type)s) was detected.\n'
                                         'Accepted checksum types: %(accepted)s')
                        elif error[constants.ERROR_CODE] == constants.ERROR_CHECKSUM_VERIFICATION:
                            message_data = {
                                'name': error[constants.NAME],
                            }
                            template = _('Package: %(name)s\nError: An invalid checksum was '
                                         'detected.')

                        elif error[constants.ERROR_CODE] == constants.ERROR_SIZE_VERIFICATION:
                            message_data = {
                                'name': error[constants.NAME],
                            }
                            template = _('Package: %(name)s\nError: The size did not match the '
                                         'value specified in the repository metadata.')
                        else:
                            error_msg = error.get('error', '')
                            traceback = '\n'.join(error.get('traceback', []))

                            message_data = {
                                'name': error['url'],
                                'error': error_msg,
                                'traceback': traceback
                            }

                            template = 'Package: %(name)s\n'
                            template += 'Error:   %(error)s\n'
                            if message_data["traceback"]:
                                template += 'Traceback:\n'
                                template += '%(traceback)s'

                        message = template % message_data

                        self.prompt.render_failure_message(message)
                    self.prompt.render_spacer()

        elif state == constants.STATE_FAILED and self.download_last_state not in constants.COMPLETE_STATES:

            # This state means something went horribly wrong. There won't be
            # individual package error details which is why they are only
            # displayed above and not in this case.

            self.prompt.write(_('... failed'))
            self.download_last_state = constants.STATE_FAILED

    def render_errata_step(self, progress_report):

        # Example Data:
        # "errata": {
        #    "state": "FINISHED",
        #    "num_errata": 0
        # }
        current_state = progress_report['yum_importer']['errata']['state']
        self.check_for_cancelled_state(current_state)
        if current_state in (constants.STATE_NOT_STARTED, constants.STATE_SKIPPED):
            return

        def update_func(new_state):
            self.errata_last_state = new_state
        render_general_spinner_step(self.prompt, self.errata_spinner, current_state, self.errata_last_state, _('Importing errata...'), update_func)

    def render_packages_step(self, progress_report, step):

        # Example Data:
        # "rpms": {
        #    "state": "FINISHED",
        #    "total": 21,
        #    "processed": 21,
        #    "successes": 21,
        #    "failures": 0
        #    "error_details": [],
        # },

        data = progress_report['yum_distributor'][step]
        state = data[constants.PROGRESS_STATE_KEY]
        total = data.get(constants.PROGRESS_TOTAL_KEY, 0)

        self.check_for_cancelled_state(state)

        if state in (constants.STATE_NOT_STARTED, constants.STATE_SKIPPED) or total == 0:
            return

        last_state = self.publish_steps_last_state[step]

        # Only render this on the first non-not-started state
        if last_state == constants.STATE_NOT_STARTED:
            self.prompt.write(_('Publishing %(step)s...') % {'step': step})

        # If it's running or finished, the output is still the same. This way,
        # if the status is viewed after this step, the content download
        # summary is still available.

        if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE) and last_state not in constants.COMPLETE_STATES:

            self.publish_steps_last_state[step] = state
            render_publish_step_in_progress_state(self.prompt, data, step, self.packages_bar, state)

        elif state == constants.STATE_FAILED and last_state not in constants.COMPLETE_STATES:

            # This state means something went horribly wrong. There won't be
            # individual package error details which is why they are only
            # displayed above and not in this case.

            self.prompt.write(_('... failed'))
            self.publish_steps_last_state[step] = constants.STATE_FAILED

    def render_distribution_publish_step(self, progress_report):

        # Example Data:
        # "distribution": {
        #    "num_success": 0,
        #    "items_left": 0,
        #    "items_total": 0,
        #    "state": "FINISHED",
        #    "error_details": [],
        #    "num_error": 0
        # },

        data = progress_report['yum_distributor']['distribution']
        state = data['state']

        if state in (constants.STATE_NOT_STARTED, constants.STATE_SKIPPED):
            return

        # Only render this on the first non-not-started state
        if self.distribution_publish_last_state  == constants.STATE_NOT_STARTED:
            self.prompt.write(_('Publishing distributions...'))

        # If it's running or finished, the output is still the same. This way,
        # if the status is viewed after this step, the content download
        # summary is still available.

        if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE) and self.distribution_publish_last_state not in constants.COMPLETE_STATES:

            self.distribution_publish_last_state = state
            render_itemized_in_progress_state(self.prompt, data, _('distributions'), self.distribution_publish_bar, state)

        elif state == constants.STATE_FAILED and self.distribution_publish_last_state not in constants.COMPLETE_STATES:

            # This state means something went horribly wrong. There won't be
            # individual package error details which is why they are only
            # displayed above and not in this case.

            self.prompt.write(_('... failed'))
            self.distribution_publish_last_state = constants.STATE_FAILED

    def render_comps_step(self, progress_report):
        # Example Data:
        # "comps": {
        #    "state": "FINISHED",
        #    "num_available_groups": 0,
        #    "num_available_categories": 0,
        #    "num_orphaned_groups": 0,
        #    "num_orphaned_categories": 0,
        #    "num_new_groups": 0,
        #    "num_new_categories": 0,
        # }

        current_state = progress_report['yum_importer']['comps']['state']
        def update_func(new_state):
            self.comps_last_state = new_state
        render_general_spinner_step(self.prompt, self.comps_spinner, current_state, self.comps_last_state, _('Importing package groups/categories...'), update_func)

    def render_generate_metadata_step(self, progress_report):

        # Example Data:
        # "metadata": {
        #    "state": "FINISHED"
        # }

        current_state = progress_report['yum_distributor']['metadata']['state']
        def update_func(new_state):
            self.generate_metadata_last_state = new_state
        render_general_spinner_step(self.prompt, self.generate_metadata_spinner, current_state, self.generate_metadata_last_state, _('Generating metadata'), update_func)

    def render_publish_http_step(self, progress_report):

        # Example Data:
        # "publish_over_http": {
        #    "state": "SKIPPED"
        # },

        current_state = progress_report[ids.YUM_DISTRIBUTOR_ID][constants.PUBLISH_OVER_HTTP_STEP][constants.PROGRESS_STATE_KEY]
        def update_func(new_state):
            self.publish_steps_last_state[constants.PUBLISH_OVER_HTTP_STEP] = new_state
        render_general_spinner_step(self.prompt, self.publish_http_spinner, current_state,
                                    self.publish_steps_last_state[constants.PUBLISH_OVER_HTTP_STEP],
                                    _('Publishing repository over HTTP'), update_func)

    def render_publish_https_step(self, progress_report):

        # Example Data:
        # "publish_over_http": {
        #    "state": "SKIPPED"
        # },

        current_state = progress_report[ids.YUM_DISTRIBUTOR_ID][constants.PUBLISH_OVER_HTTPS_STEP][constants.PROGRESS_STATE_KEY]
        def update_func(new_state):
            self.publish_steps_last_state[constants.PUBLISH_OVER_HTTPS_STEP] = new_state
        render_general_spinner_step(self.prompt, self.publish_https_spinner, current_state,
                                    self.publish_steps_last_state[constants.PUBLISH_OVER_HTTPS_STEP],
                                    _('Publishing repository over HTTPS'), update_func)


class RpmExportStatusRenderer(StatusRenderer):
    """
    Progress reporting for the rpm repo export command. The progress report is expected to have the
    following format:

    pulp_rpm.common.ids.TYPE_ID_DISTRIBUTOR_EXPORT: {
      pulp_rpm.common.models.Errata.TYPE: {
        constants.PROGRESS_NUM_SUCCESS_KEY: 12,
        constants.PROGRESS_NUM_ERROR_KEY: 0,
        constants.PROGRESS_ITEMS_LEFT_KEY: 0,
        constants.PROGRESS_STATE_KEY: "FINISHED",
        constants.PROGRESS_ITEMS_TOTAL_KEY: 12,
        constants.PROGRESS_ERROR_DETAILS_KEY: []
      },
      constants.PROGRESS_PUBLISH_HTTP: {
        constants.PROGRESS_STATE_KEY: "FINISHED",
      },
      constants.PROGRESS_PUBLISH_HTTPS: {
        constants.PROGRESS_STATE_KEY: "FINISHED",
      },
      constants.PROGRESS_ISOS_KEYWORD: {
        constants.PROGRESS_NUM_SUCCESS_KEY: 1,
        constants.PROGRESS_NUM_ERROR_KEY: 0,
        constants.PROGRESS_ITEMS_LEFT_KEY: 0,
        constants.PROGRESS_STATE_KEY: "FINISHED",
        constants.PROGRESS_ITEMS_TOTAL_KEY: 1,
        constants.PROGRESS_ERROR_DETAILS_KEY: []
      },
      pulp_rpm.common.models.Distribution.TYPE: {
        constants.PROGRESS_NUM_SUCCESS_KEY: 1,
        constants.PROGRESS_NUM_ERROR_KEY: 0,
        constants.PROGRESS_ITEMS_LEFT_KEY: 0,
        constants.PROGRESS_STATE_KEY: "FINISHED",
        constants.PROGRESS_ITEMS_TOTAL_KEY: 1,
        constants.PROGRESS_ERROR_DETAILS_KEY: []
      },
      pulp_rpm.common.models.RPM.TYPE: {
        constants.PROGRESS_NUM_SUCCESS_KEY: 43,
        constants.PROGRESS_NUM_ERROR_KEY: 0,
        constants.PROGRESS_ITEMS_LEFT_KEY: 0,
        constants.PROGRESS_STATE_KEY: "FINISHED",
        constants.PROGRESS_ITEMS_TOTAL_KEY: 43,
        constants.PROGRESS_ERROR_DETAILS_KEY: []
      },
      'metadata': {
        constants.PROGRESS_STATE_KEY: "FINISHED",
      }
    }

    All constants can be found in pulp_rpm.common.constants
    """

    def __init__(self, context):
        """
        Class constructor

        :param context: The client context to use for this renderer.
        :type  context: pulp.client.extensions.core.ClientContext
        """
        super(RpmExportStatusRenderer, self).__init__(context)

        # Publish Steps
        self.rpms_last_state = constants.STATE_NOT_STARTED
        self.errata_last_state = constants.STATE_NOT_STARTED
        self.distributions_last_state = constants.STATE_NOT_STARTED
        self.generate_metadata_last_state = constants.STATE_NOT_STARTED
        self.isos_last_state = constants.STATE_NOT_STARTED
        self.publish_http_last_state = constants.STATE_NOT_STARTED
        self.publish_https_last_state = constants.STATE_NOT_STARTED

        # UI Widgets
        self.rpms_bar = self.prompt.create_progress_bar()
        self.errata_bar = self.prompt.create_progress_bar()
        self.distributions_bar = self.prompt.create_progress_bar()
        self.generate_metadata_spinner = self.prompt.create_spinner()
        self.isos_bar = self.prompt.create_progress_bar()
        self.publish_http_spinner = self.prompt.create_spinner()
        self.publish_https_spinner = self.prompt.create_spinner()

    def display_report(self, progress_report):
        """
        Displays the contents of the progress report to the user. This will
        aggregate the calls to render individual sections of the report.
        """
        # Publish Steps
        if ids.TYPE_ID_DISTRIBUTOR_EXPORT in progress_report:
            self.render_rpms_step(progress_report)
            self.render_errata_step(progress_report)
            self.render_distribution_publish_step(progress_report)
            self.render_generate_metadata_step(progress_report)
            self.render_isos_step(progress_report)
            self.render_publish_https_step(progress_report)
            self.render_publish_http_step(progress_report)

    def render_rpms_step(self, progress_report):
        """
        Render the rpm export progress.

        :param progress_report: A dictionary containing the progress report from the export distributor
        :type progress_report: dict
        """
        data = progress_report[ids.TYPE_ID_DISTRIBUTOR_EXPORT][models.RPM.TYPE]
        state = data[constants.PROGRESS_STATE_KEY]

        if state == constants.STATE_NOT_STARTED:
            return

        # Only render this on the first non-not-started state
        if self.rpms_last_state == constants.STATE_NOT_STARTED:
            self.prompt.write(_('Exporting packages...'))

        if self.rpms_last_state not in constants.COMPLETE_STATES:
            if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE):
                self.rpms_last_state = state
                render_itemized_in_progress_state(self.prompt, data, _('rpms'), self.rpms_bar, state)

            elif state == constants.STATE_FAILED:
                self.prompt.write(_('... failed'))
                self.rpms_last_state = constants.STATE_FAILED

    def render_errata_step(self, progress_report):
        """
        Render the errata export progress.

        :param progress_report: A dictionary containing the progress report from the export distributor
        :type progress_report: dict
        """
        data = progress_report[ids.TYPE_ID_DISTRIBUTOR_EXPORT][models.Errata.TYPE]
        state = data[constants.PROGRESS_STATE_KEY]

        if state == constants.STATE_NOT_STARTED:
            return

        # Only render this on the first non-not-started state
        if self.errata_last_state == constants.STATE_NOT_STARTED:
            self.prompt.write(_('Exporting errata...'))

        # Render the progress bar while the state is running and once on state completion
        if self.errata_last_state not in constants.COMPLETE_STATES:
            if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE):
                self.errata_last_state = state
                render_itemized_in_progress_state(self.prompt, data, _('errata'), self.errata_bar, state)
            elif state == constants.STATE_FAILED:
                self.prompt.write(_('... failed'))
                self.errata_last_state = constants.STATE_FAILED

    def render_distribution_publish_step(self, progress_report):
        """
        Render the errata export progress.

        :param progress_report: A dictionary containing the progress report from the export distributor
        :type progress_report: dict
        """
        data = progress_report[ids.TYPE_ID_DISTRIBUTOR_EXPORT][models.Distribution.TYPE]
        state = data[constants.PROGRESS_STATE_KEY]

        if state == constants.STATE_NOT_STARTED:
            return

        # Only render this on the first non-not-started state
        if self.distributions_last_state == constants.STATE_NOT_STARTED:
            self.prompt.write(_('Exporting distributions...'))

        if self.distributions_last_state not in constants.COMPLETE_STATES:
            if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE):
                self.distributions_last_state = state
                render_itemized_in_progress_state(self.prompt, data, _('distributions'),
                                                  self.distributions_bar, state)
            elif state == constants.STATE_FAILED:
                self.prompt.write(_('... failed'))
                self.distributions_last_state = constants.STATE_FAILED

    def render_isos_step(self, progress_report):
        """
        Render the ISO image generation export progress.

        :param progress_report: A dictionary containing the progress report from the export distributor
        :type progress_report: dict
        """
        data = progress_report[ids.TYPE_ID_DISTRIBUTOR_EXPORT][constants.PROGRESS_ISOS_KEYWORD]
        state = data[constants.PROGRESS_STATE_KEY]

        if state == constants.STATE_NOT_STARTED:
            return

        if self.isos_last_state not in constants.COMPLETE_STATES:
            if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE):
                self.isos_last_state = state
                render_itemized_in_progress_state(self.prompt, data, _('ISO images'), self.isos_bar,
                                                  state)
            elif state == constants.STATE_FAILED:
                self.prompt.write(_('... failed'))
                self.isos_last_state = constants.STATE_FAILED

    def render_generate_metadata_step(self, progress_report):
        """
        Render the metadata generation progress.

        :param progress_report: A dictionary containing the progress report from the export distributor
        :type progress_report: dict
        """
        data = progress_report[ids.TYPE_ID_DISTRIBUTOR_EXPORT][constants.PROGRESS_METADATA_KEYWORD]
        current_state = data[constants.PROGRESS_STATE_KEY]

        render_general_spinner_step(self.prompt, self.generate_metadata_spinner, current_state,
                                    self.generate_metadata_last_state, _('Generating metadata...'),
                                    functools.partial(setattr, self, 'generate_metadata_last_state'))

    def render_publish_http_step(self, progress_report):
        """
        This function handles the rendering of the constants.PROGRESS_HTTP_KEYWORD progress report

        :param progress_report: The progress report from the group export distributor
        :type  progress_report: dict
        """
        # Grab the http report out of the progress_report dictionary
        report = progress_report[ids.TYPE_ID_DISTRIBUTOR_EXPORT][constants.PROGRESS_PUBLISH_HTTP]

        render_general_spinner_step(self.prompt, self.publish_http_spinner,
                                    report[constants.PROGRESS_STATE_KEY], self.publish_http_last_state,
                                    _('Publishing over HTTP...'),
                                    functools.partial(setattr, self, 'publish_http_last_state'))

    def render_publish_https_step(self, progress_report):
        """
        This function handles the rendering of the constants.PROGRESS_PUBLISH_HTTPS_KEYWORD progress
        report

        :param progress_report: The progress report from the group export distributor
        :type  progress_report: dict
        """
        # Grab the https report out of the progress_report dictionary
        report = progress_report[ids.TYPE_ID_DISTRIBUTOR_EXPORT][constants.PROGRESS_PUBLISH_HTTPS]

        render_general_spinner_step(self.prompt, self.publish_https_spinner,
                                    report[constants.PROGRESS_STATE_KEY], self.publish_https_last_state,
                                    _('Publishing over HTTPS...'),
                                    functools.partial(setattr, self, 'publish_https_last_state'))


class RpmGroupExportStatusRenderer(StatusRenderer):
    """
    Progress reporting for the rpm repo group export command. The progress report is expected to have
    the following dictionaries in it:

    ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT: {
      constants.PROGRESS_PUBLISH_HTTP: {
        constants.PROGRESS_STATE_KEY: "FINISHED",
      },
      constants.PROGRESS_ISOS_KEYWORD: {
        constants.PROGRESS_NUM_SUCCESS_KEY: 2,
        constants.PROGRESS_NUM_ERROR_KEY: 0,
        constants.PROGRESS_ITEMS_LEFT_KEY: 0,
        constants.PROGRESS_STATE_KEY: "FINISHED",
        constants.PROGRESS_ITEMS_TOTAL_KEY: 2,
        constants.PROGRESS_ERROR_DETAILS_KEY: []
      },
      constants.PROGRESS_REPOS_KEYWORD: {
        constants.PROGRESS_NUM_SUCCESS_KEY: 5,
        constants.PROGRESS_NUM_ERROR_KEY: 0,
        constants.PROGRESS_ITEMS_LEFT_KEY: 0,
        constants.PROGRESS_STATE_KEY: "FINISHED",
        constants.PROGRESS_ITEMS_TOTAL_KEY: 5,
        constants.PROGRESS_ERROR_DETAILS_KEY: []
      },
      constants.PROGRESS_PUBLISH_HTTPS: {
        constants.PROGRESS_STATE_KEY: "FINISHED",
      }
    }

    All constants and ids can found in pulp_rpm.common.constants and pulp_rpm.common.ids
    """
    def __init__(self, context):
        """
        Class constructor

        :param context: The client context to use for this renderer.
        :type  context: pulp.client.extensions.core.ClientContext
        """
        super(RpmGroupExportStatusRenderer, self).__init__(context)

        # Publish Steps
        self.repos_last_state = constants.STATE_NOT_STARTED
        self.isos_last_state = constants.STATE_NOT_STARTED
        self.publish_http_last_state = constants.STATE_NOT_STARTED
        self.publish_https_last_state = constants.STATE_NOT_STARTED

        # UI Widgets
        self.repos_bar = self.prompt.create_progress_bar()
        self.isos_bar = self.prompt.create_progress_bar()
        self.publish_http_spinner = self.prompt.create_spinner()
        self.publish_https_spinner = self.prompt.create_spinner()

    def display_report(self, progress_report):
        """
        Displays the contents of the progress report to the user. This will
        aggregate the calls to render individual sections of the report.

        :param progress_report: The progress report from the group export distributor
        :type progress_report: dict
        """
        # Publish Steps
        if ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT in progress_report:
            self.render_repos_step(progress_report)
            self.render_isos_step(progress_report)
            self.render_publish_https_step(progress_report)
            self.render_publish_http_step(progress_report)

    def render_repos_step(self, progress_report):
        """
        This function handles the rendering of the constants.PROGRESS_REPOS_KEYWORD progress report

        :param progress_report: The progress report from the group export distributor
        :type progress_report: dict
        """
        # Grab the repositories progress report out of the progress_report dict
        data = progress_report[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_REPOS_KEYWORD]
        state = data[constants.PROGRESS_STATE_KEY]

        if state == constants.STATE_NOT_STARTED:
            return

        if self.repos_last_state not in constants.COMPLETE_STATES:
            if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE):
                self.repos_last_state = state
                render_itemized_in_progress_state(self.prompt, data, _('Exporting repositories...'),
                                                  self.repos_bar, state)
            elif state == constants.STATE_FAILED:
                self.prompt.write(_('... failed'))
                self.repos_last_state = constants.STATE_FAILED

    def render_isos_step(self, progress_report):
        """
        This function handles the rendering of the constants.PROGRESS_ISOS_KEYWORD progress report

        :param progress_report: The progress report from the group export distributor
        :type progress_report: dict
        """
        # Grab the iso progress report out of the progress_report dict
        data = progress_report[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_ISOS_KEYWORD]
        state = data[constants.PROGRESS_STATE_KEY]

        if state == constants.STATE_NOT_STARTED:
            return

        if self.isos_last_state not in constants.COMPLETE_STATES:
            if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE):
                self.isos_last_state = state
                render_itemized_in_progress_state(self.prompt, data, _('Generating ISO images...'),
                                                  self.isos_bar, state)
            elif state == constants.STATE_FAILED:
                self.prompt.write(_('... failed'))
                self.isos_last_state = constants.STATE_FAILED

    def render_publish_http_step(self, progress_report):
        """
        This function handles the rendering of the constants.PROGRESS_PUBLISH_HTTP_KEYWORD progress
        report

        :param progress_report: The progress report from the group export distributor
        :type progress_report: dict
        """
        # Grab the http report out of the progress_report dictionary
        report = progress_report[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_PUBLISH_HTTP]

        render_general_spinner_step(self.prompt, self.publish_http_spinner,
                                    report[constants.PROGRESS_STATE_KEY], self.publish_http_last_state,
                                    _('Publishing over HTTP...'),
                                    functools.partial(setattr, self, 'publish_http_last_state'))

    def render_publish_https_step(self, progress_report):
        """
        This function handles the rendering of the constants.PROGRESS_PUBLISH_HTTPS_KEYWORD progress
        report

        :param progress_report: The progress report from the group export distributor
        :type progress_report: dict
        """
        # Grab the https report out of the progress_report dictionary
        report = progress_report[ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT][constants.PROGRESS_PUBLISH_HTTPS]

        render_general_spinner_step(self.prompt, self.publish_https_spinner,
                                    report[constants.PROGRESS_STATE_KEY], self.publish_https_last_state,
                                    _('Publishing over HTTPS...'),
                                    functools.partial(setattr, self, 'publish_https_last_state'))

