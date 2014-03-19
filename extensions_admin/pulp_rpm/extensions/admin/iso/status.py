from datetime import datetime
from gettext import gettext as _

from pulp.client.commands.repo.sync_publish import StatusRenderer

from pulp_rpm.common import ids, progress


class ISOStatusRenderer(StatusRenderer):
    def __init__(self, context):
        super(self.__class__, self).__init__(context)

        self._sync_isos_bar = self.prompt.create_progress_bar()

        # Let's have our status renderer track the same state transitions are the ProgressReport
        self._sync_state = progress.ISOProgressReport.STATE_NOT_STARTED

    def display_report(self, progress_report):
        """
        Bet you couldn't guess that this method displays the progress_report.

        :param progress_report: The progress report that we want to display to the user
        :type  progress_report: pulp_rpm.common.progress.ISOProgressReport
        """
        if ids.TYPE_ID_IMPORTER_ISO in progress_report:
            sync_report = progress.SyncProgressReport.from_progress_report(
                progress_report[ids.TYPE_ID_IMPORTER_ISO])
            self._display_manifest_sync_report(sync_report)
            self._display_iso_sync_report(sync_report)

            if sync_report.state == sync_report.STATE_CANCELLED:
                self.prompt.render_failure_message('The download was cancelled.', tag='cancelled')

        if ids.TYPE_ID_DISTRIBUTOR_ISO in progress_report:
            publish_report = progress.PublishProgressReport.from_progress_report(
                progress_report[ids.TYPE_ID_DISTRIBUTOR_ISO])
            self._display_publish_report(publish_report)

    def _display_iso_sync_report(self, sync_report):
        """
        Display the ISO retrieval step.
        """
        if (self._sync_state == sync_report.STATE_MANIFEST_IN_PROGRESS and
                sync_report.state != sync_report.STATE_MANIFEST_IN_PROGRESS):
            if sync_report.num_isos:
                self.prompt.write(_('Downloading %(num)s ISOs...') % {'num': sync_report.num_isos},
                                  tag='download_starting')
                self._sync_state = sync_report.STATE_ISOS_IN_PROGRESS
            else:
                self.prompt.render_success_message(
                    _('There are no ISOs that need to be downloaded.'), tag='none_to_download')
                self._sync_state = sync_report.STATE_COMPLETE

        if self._sync_state == sync_report.STATE_ISOS_IN_PROGRESS:
            if sync_report.total_bytes:
                runtime = (datetime.utcnow() -
                           sync_report.state_times[sync_report.STATE_MANIFEST_IN_PROGRESS])
                runtime = (runtime.days * 3600 * 24) + runtime.seconds
                if runtime: 
                    average_speed = human_readable_bytes(sync_report.finished_bytes/runtime)
                else:
                    average_speed = 0
                bar_message = _("ISOs: %(num_complete)s/%(num_total)s\tData: "
                                "%(bytes_complete)s/%(bytes_total)s\tAvg: %(speed)s/s")
                bar_message = bar_message % {
                    'num_complete': sync_report.num_isos_finished, 'num_total': sync_report.num_isos,
                    'speed': average_speed,
                    'bytes_complete': human_readable_bytes(sync_report.finished_bytes),
                    'bytes_total': human_readable_bytes(sync_report.total_bytes)}
                self._sync_isos_bar.render(sync_report.finished_bytes, sync_report.total_bytes,
                                           message=bar_message)
            if sync_report.state != sync_report.STATE_ISOS_IN_PROGRESS:
                self.prompt.write('\n')
                if sync_report.state == sync_report.STATE_COMPLETE:
                    msg = _('Successfully downloaded %(num)s ISOs.') % {
                        'num': sync_report.num_isos_finished}
                    self.prompt.render_success_message(msg, tag='download_success')
                else:
                    msg = _('Failed to retrieve %(num)s ISOs.')
                    msg = msg % {'num': sync_report.num_isos - sync_report.num_isos_finished}
                    self.prompt.render_failure_message(msg, tag='download_failed')
                    for failed_iso in sync_report.iso_error_messages:
                        self.prompt.render_failure_message(
                            '\t%(name)s: %(msg)s' % {
                                'name': failed_iso['name'], 'msg': failed_iso['error']},
                                tag='iso_error_msg')
                self._sync_state = sync_report.state

    def _display_manifest_sync_report(self, sync_report):
        """
        Display the manifest retrieval step.
        """
        # We should skip this step if the sync hasn't begun
        if sync_report.state == sync_report.STATE_NOT_STARTED:
            return

        if (sync_report.state == sync_report.STATE_MANIFEST_FAILED and
                self._sync_state != sync_report.STATE_MANIFEST_FAILED):
            self.prompt.render_failure_message(_('Downloading the Pulp Manifest failed:'),
                                               tag='manifest_failed')
            self.prompt.render_failure_message('\t%s' % sync_report.error_message,
                                               tag='manifest_error_message')
            self._sync_state = sync_report.STATE_MANIFEST_FAILED
            return

        if self._sync_state == sync_report.STATE_NOT_STARTED:
            # The sync_report has moved on, so let's respond
            self._sync_state = sync_report.STATE_MANIFEST_IN_PROGRESS

            if sync_report.state == sync_report.STATE_MANIFEST_IN_PROGRESS:
                self.prompt.write(_('Downloading the Pulp Manifest...'), tag='downloading_manifest')

        if (self._sync_state == sync_report.STATE_MANIFEST_IN_PROGRESS and
                sync_report.state != sync_report.STATE_MANIFEST_IN_PROGRESS):
            self.prompt.render_success_message(_('The Pulp Manifest was downloaded successfully.'),
                                               tag='manifest_downloaded')

    def _display_publish_report(self, publish_report):
        """
        Display the publishing step.
        """
        # Skip if the publish state hasn't begun
        if publish_report.state == publish_report.STATE_NOT_STARTED:
            return

        if publish_report.state == publish_report.STATE_FAILED:
            self.prompt.render_failure_message(_('Publishing failed.'), tag='publish_failed')
            self.prompt.write('\t%s'%publish_report.error_message, tag='error_message')
            return

        if publish_report.state == publish_report.STATE_COMPLETE:
            msg = _('The repository was successfully published.')
            self.prompt.render_success_message(msg, tag='publish_success')


def human_readable_bytes(num):
    """
    This handy snippet was retrieved from
    http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
    It takes a size in Bytes, and converts it to a nice human readable form.
    """
    for x in ['B','kB','MB','GB']:
        if num < 1024.0:
            if x == 'B':
                return '%s %s' % (num, x)
            else:
                return "%3.1f %s" % (num, x)
        num /= 1024.0
    return "%3.1f %s" % (num, 'TB')
