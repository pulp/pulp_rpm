"""
Contains functionality related to rendering the progress report for a the RPM
plugins (both the sync and publish operations).
"""

from gettext import gettext as _

from pulp.client.commands.repo.sync_publish import StatusRenderer
from pulp.client.commands.repo.status import PublishStepStatusRenderer

from pulp_rpm.common import constants, ids
from pulp_rpm.common.status_utils import (
    render_general_spinner_step, render_itemized_in_progress_state)


class CancelException(Exception):
    pass


class RpmStatusRenderer(StatusRenderer):
    def __init__(self, context):
        super(RpmStatusRenderer, self).__init__(context)

        self.publish_steps_renderer = PublishStepStatusRenderer(context)

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
                # Proxy to the standard renderer
                self.publish_steps_renderer.display_report(progress_report)

        except CancelException:
            self.prompt.render_failure_message(_('Operation cancelled.'))

    def check_for_cancelled_state(self, state):
        if state == constants.STATE_CANCELLED:
            raise CancelException

    # -- render sync steps -----------------------------------------------------

    def render_metadata_step(self, progress_report):

        # Example Data:
        # "metadata": {
        # "state": "FINISHED"
        # }

        current_state = progress_report['yum_importer']['metadata']['state']
        self.check_for_cancelled_state(current_state)

        def update_func(new_state):
            self.metadata_last_state = new_state

        render_general_spinner_step(self.prompt, self.metadata_spinner, current_state,
                                    self.metadata_last_state, _('Downloading metadata...'),
                                    update_func)

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
            render_itemized_in_progress_state(self.prompt, data, _('distributions'),
                                              self.distribution_sync_bar, state)

        elif state in constants.STATE_FAILED and \
                self.distribution_sync_last_state not in constants.COMPLETE_STATES:

            self.prompt.render_spacer()
            self.prompt.render_failure_message(_('Errors encountered during distribution sync:'))

            # TODO: read this from config
            # display_error_count = self.context.extension_config.getint('main',
            # 'num_display_errors')
            display_error_count = 5

            num_errors = min(len(data['error_details']), display_error_count)

            if num_errors > 0:

                # Each error is a list of filename and dict of details
                # Example:
                # "error_details": [
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
                        'filename': error[0],
                        'message': error[1].get('error_message'),
                        'code': error[1].get('error_code'),
                    }

                    template = 'File: %(filename)s\n'
                    template += 'Error Code:   %(code)s\n'
                    template += 'Error Message: %(message)s'
                    message = template % message_data

                    self.prompt.render_failure_message(message)
                self.prompt.render_spacer()

        self.distribution_sync_last_state = state

    def render_download_step(self, progress_report):
        """
        :param progress_report: A dictionary containing a key called 'yum_importer' that is a
                                dictionary that has a key that is 'content' that indexes a
                                pulp_rpm.plugins.importers.yum.report.ContentReport.
        :type  progress_report: dict
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

        if state in (constants.STATE_RUNNING, constants.STATE_COMPLETE) and \
           self.download_last_state not in constants.COMPLETE_STATES:

            self.download_last_state = state

            template = _('RPMs:       %(rpm_done)s/%(rpm_total)s items\n'
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
                # display_error_count = self.context.extension_config.getint('main',
                # 'num_display_errors')
                display_error_count = 5

                num_errors = min(len(data['error_details']), display_error_count)

                if num_errors > 0:
                    self.prompt.render_failure_message(
                        _('Individual package errors encountered during sync:'))

                    for i in range(0, num_errors):
                        error = data['error_details'][i]
                        if error.get(constants.ERROR_CODE) == constants.ERROR_CHECKSUM_TYPE_UNKNOWN:
                            message_data = {
                                'name': error[constants.NAME],
                                'checksum_type': error[constants.CHECKSUM_TYPE],
                                'accepted': ','.join(
                                    error.get(constants.ACCEPTED_CHECKSUM_TYPES, []))
                            }
                            template = _('Package: %(name)s\nError: An invalid checksum type '
                                         '(%(checksum_type)s) was detected.\n'
                                         'Accepted checksum types: %(accepted)s')
                        elif error.get(
                                constants.ERROR_CODE) == constants.ERROR_CHECKSUM_VERIFICATION:
                            message_data = {
                                'name': error[constants.NAME],
                            }
                            template = _('Package: %(name)s\nError: An invalid checksum was '
                                         'detected.')

                        elif error.get(constants.ERROR_CODE) == constants.ERROR_SIZE_VERIFICATION:
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

        elif state == constants.STATE_FAILED and self.download_last_state not in \
                constants.COMPLETE_STATES:

            # This state means something went horribly wrong. There won't be
            # individual package error details which is why they are only
            # displayed above and not in this case.

            self.prompt.write(_('... failed'))
            self.download_last_state = constants.STATE_FAILED

    def render_errata_step(self, progress_report):

        # Example Data:
        # "errata": {
        # "state": "FINISHED",
        #    "num_errata": 0
        # }
        current_state = progress_report['yum_importer']['errata']['state']
        self.check_for_cancelled_state(current_state)
        if current_state in (constants.STATE_NOT_STARTED, constants.STATE_SKIPPED):
            return

        def update_func(new_state):
            self.errata_last_state = new_state

        render_general_spinner_step(self.prompt, self.errata_spinner, current_state,
                                    self.errata_last_state, _('Importing errata...'), update_func)

    def render_comps_step(self, progress_report):
        # Example Data:
        # "comps": {
        # "state": "FINISHED",
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

        render_general_spinner_step(self.prompt, self.comps_spinner, current_state,
                                    self.comps_last_state,
                                    _('Importing package groups/categories...'), update_func)
