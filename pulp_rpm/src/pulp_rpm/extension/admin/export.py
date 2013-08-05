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

from gettext import gettext as _

from pulp.bindings import exceptions
from pulp.client.commands import options
from pulp.client.commands.repo.sync_publish import RunPublishRepositoryCommand
from pulp.client.commands.repo.status import tasks, status
from pulp.client import parsers, validators
from pulp.client.extensions.extensions import PulpCliOption, PulpCliCommand
from pulp.common import tags as tag_utils

from pulp_rpm.common import ids, constants
from pulp_rpm.extension.admin.status import RpmExportStatusRenderer

# -- commands -----------------------------------------------------------------

DESC_EXPORT_RUN = _('triggers an immediate export of a repository')
DESC_GROUP_EXPORT_RUN = _('triggers an immediate export of a repository group')
DESC_GROUP_EXPORT_STATUS = _('displays the status of a repository group\'s export task')

DESC_ISO_PREFIX = _('prefix to use in the generated ISO name, default: <repo-id>-<current_date>.iso')
DESC_START_DATE = _('start date for an incremental export; only content associated with a repository'
                    ' on or after the given value will be included in the exported repository; dates '
                    'should be in standard ISO8601 format: "1970-01-01T00:00:00"')
DESC_END_DATE = _('end date for an incremental export; only content associated with a repository '
                  'on or before the given value will be included in the exported repository; dates '
                  'should be in standard ISO8601 format: "1970-01-01T00:00:00"')
DESC_EXPORT_DIR = _('the full path to a directory; if specified, the repository will be exported '
                    'to the given directory instead of being placed in ISOs and published via '
                    'HTTP or HTTPS')
DESC_ISO_SIZE = _('the maximum size, in megabytes, of the exported ISOs; if this is not '
                  'specified, single layer DVD-sized ISOs are created')
DESC_BACKGROUND = _('if specified, the CLI process will end but the process will continue on '
                    'the server; the progress can be later displayed using the status command')
# These two flags exist because there is currently no place to configure group publishes
DESC_SERVE_HTTP = _('if this flag is used, the ISO images will be served over HTTP; if '
                    'this export is to a directory, this has no effect.')
DESC_SERVE_HTTPS = _('if this flag is used, the ISO images will be served over HTTPS; if '
                     'this export is to a directory, this has no effect.')

# Flag names, which are also the kwarg keywords
SERVE_HTTP = 'serve-http'
SERVE_HTTPS = 'serve-https'
BACKGROUND = 'bg'

# The iso prefix is restricted to the same character set as an id, so we use the id_validator
OPTION_ISO_PREFIX = PulpCliOption('--iso-prefix', DESC_ISO_PREFIX, required=False,
                                  validate_func=validators.id_validator)
OPTION_START_DATE = PulpCliOption('--start-date', DESC_START_DATE, required=False,
                                  validate_func=validators.iso8601_datetime_validator)
OPTION_END_DATE = PulpCliOption('--end-date', DESC_END_DATE, required=False,
                                validate_func=validators.iso8601_datetime_validator)
OPTION_EXPORT_DIR = PulpCliOption('--export-dir', DESC_EXPORT_DIR, required=False)
OPTION_ISO_SIZE = PulpCliOption('--iso-size', DESC_ISO_SIZE, required=False,
                                parse_func=parsers.parse_optional_non_negative_int)


class RpmExportCommand(RunPublishRepositoryCommand):
    """
    The 'pulp-admin rpm repo export run' command
    """
    def __init__(self, context):
        override_config_options = [OPTION_EXPORT_DIR, OPTION_ISO_PREFIX, OPTION_ISO_SIZE,
                                   OPTION_START_DATE, OPTION_END_DATE]

        super(RpmExportCommand, self).__init__(context=context,
                                               renderer=RpmExportStatusRenderer(context),
                                               distributor_id=ids.TYPE_ID_DISTRIBUTOR_EXPORT,
                                               description=DESC_EXPORT_RUN,
                                               override_config_options=override_config_options)


class RpmGroupExportCommand(PulpCliCommand):
    """
    The 'pulp-admin rpm repo group export run' command.
    """
    def __init__(self, context, renderer, distributor_id, name='run', description=DESC_GROUP_EXPORT_RUN):
        super(RpmGroupExportCommand, self).__init__(name, description, self.run)

        self.context = context
        self.prompt = context.prompt
        self.renderer = renderer
        self.distributor_id = distributor_id

        self.add_option(options.OPTION_GROUP_ID)
        self.add_option(OPTION_ISO_PREFIX)
        self.add_option(OPTION_ISO_SIZE)
        self.add_option(OPTION_START_DATE)
        self.add_option(OPTION_END_DATE)
        self.add_option(OPTION_EXPORT_DIR)

        self.create_flag('--' + SERVE_HTTP, DESC_SERVE_HTTP)
        self.create_flag('--' + SERVE_HTTPS, DESC_SERVE_HTTPS)
        self.create_flag('--' + BACKGROUND, DESC_BACKGROUND)

    def run(self, **kwargs):
        # Grab all the configuration options
        group_id = kwargs[options.OPTION_GROUP_ID.keyword]
        iso_prefix = kwargs[OPTION_ISO_PREFIX.keyword]
        iso_size = kwargs[OPTION_ISO_SIZE.keyword]
        start_date = kwargs[OPTION_START_DATE.keyword]
        end_date = kwargs[OPTION_END_DATE.keyword]
        export_dir = kwargs[OPTION_EXPORT_DIR.keyword]
        serve_http = kwargs[SERVE_HTTP]
        serve_https = kwargs[SERVE_HTTPS]
        background = kwargs[BACKGROUND]

        # Since the export distributor is not added to a repository group on creation, add it here
        # if it is not already associated with the group id
        try:
            self.context.server.repo_group_distributor.distributor(group_id, self.distributor_id)
        except exceptions.NotFoundException:
            distributor_config = {
                constants.PUBLISH_HTTP_KEYWORD: serve_http,
                constants.PUBLISH_HTTPS_KEYWORD: serve_https,
            }
            self.context.server.repo_group_distributor.create(group_id,
                                                              ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT,
                                                              distributor_config, self.distributor_id)

        publish_config = {
            constants.PUBLISH_HTTP_KEYWORD: serve_http,
            constants.PUBLISH_HTTPS_KEYWORD: serve_https,
            constants.ISO_PREFIX_KEYWORD: iso_prefix,
            constants.ISO_SIZE_KEYWORD: iso_size,
            constants.START_DATE_KEYWORD: start_date,
            constants.END_DATE_KEYWORD: end_date,
            constants.EXPORT_DIRECTORY_KEYWORD: export_dir,
        }

        self.prompt.render_title(_('Exporting Repository Group [%s]' % group_id))

        # Retrieve all publish tasks for this repository group
        tags = [tag_utils.resource_tag('repository_group', group_id),
                tag_utils.action_tag(tag_utils.ACTION_PUBLISH_TYPE)]
        existing_tasks = self.context.server.tasks.get_all_tasks(tags)
        task_id = tasks.relevant_existing_task_id(existing_tasks.response_body)

        if task_id is not None:
            msg = _('A publish task is already in progress for this repository. ')
            if not background:
                msg += _('Its progress will be tracked below.')
            self.context.prompt.render_paragraph(msg, tag='in-progress')
        else:
            # If there is no existing publish for this repo group, start one
            response = self.context.server.repo_group_actions.publish(group_id, self.distributor_id,
                                                                      publish_config)
            task_id = response.response_body.task_id

        if not background:
            # Show the task status
            status.display_task_status(self.context, self.renderer, task_id)
        else:
            msg = _('The status of this publish can be displayed using the status command.')
            self.context.prompt.render_paragraph(msg, 'background')


class ExportGroupStatusCommand(PulpCliCommand):
    def __init__(self, context, renderer, name='status', description=DESC_GROUP_EXPORT_STATUS):
        super(ExportGroupStatusCommand, self).__init__(name, description, self.run)

        self.context = context
        self.prompt = context.prompt
        self.renderer = renderer

        self.add_option(options.OPTION_GROUP_ID)

    def run(self, **kwargs):
        group_id = kwargs[options.OPTION_GROUP_ID.keyword]
        self.prompt.render_title(_('Repository Group [%s] Export Status' % group_id))

        # Retrieve the task id, if it exists
        tags = [tag_utils.resource_tag('repository_group', group_id),
                tag_utils.action_tag(tag_utils.ACTION_PUBLISH_TYPE)]
        response = self.context.server.tasks.get_all_tasks(tags)
        task_id = tasks.relevant_existing_task_id(response.response_body)

        if task_id is None:
            msg = _('The repository group is not performing any operations')
            self.prompt.render_paragraph(msg, tag='no-tasks')
        else:
            status.display_task_status(self.context, self.renderer, task_id)