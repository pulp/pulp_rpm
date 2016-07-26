# -*- coding: utf-8 -*-

from gettext import gettext as _
import os
from urlparse import urlparse

from pulp.client import arg_utils
from pulp.client.arg_utils import InvalidConfig
from pulp.client.commands import options as std_options
from pulp.client.commands.repo.cudl import CreateRepositoryCommand, UpdateRepositoryCommand
from pulp.client.commands.repo.importer_config import (OptionsBundle, ImporterConfigMixin,
                                                       safe_parse)
from pulp.common import constants as pulp_constants
from pulp.common.plugins import importer_constants
from pulp.common.util import encode_unicode

from pulp_rpm.extensions.admin import repo_options
from pulp_rpm.common import constants, ids


CONFIG_KEY_SKIP = 'type_skip_list'

YUM_DISTRIBUTOR_CONFIG_KEYS = [
    ('relative_url', 'relative_url'),
    ('http', 'serve_http'),
    ('https', 'serve_https'),
    ('generate_sqlite', 'generate_sqlite'),
    ('gpgkey', 'gpg_key'),
    ('checksum_type', 'checksum_type'),
    ('auth_ca', 'auth_ca'),
    ('auth_cert', 'auth_cert'),
    ('https_ca', 'host_ca'),
    ('generate_metadata', 'regenerate_metadata'),
    ('skip', 'skip'),
    ('repoview', 'repoview'),
]

EXPORT_DISTRIBUTOR_CONFIG_KEYS = [
    ('http', 'serve_http'),
    ('https', 'serve_https'),
    ('relative_url', 'relative_url'),
    ('generate_sqlite', 'generate_sqlite'),
    ('skip', 'skip'),
    ('checksum_type', 'checksum_type'),
]


class RpmRepoOptionsBundle(OptionsBundle):
    """
    Contains small modifications to the default option descriptions.
    """

    def __init__(self):
        super(RpmRepoOptionsBundle, self).__init__()
        self.opt_remove_missing.description += _('; defaults to false')


class RpmRepoCreateCommand(CreateRepositoryCommand, ImporterConfigMixin):
    def __init__(self, context):

        # Adds things like name, description
        CreateRepositoryCommand.__init__(self, context)

        # Adds all downloader-related importer config options
        ImporterConfigMixin.__init__(self,
                                     options_bundle=RpmRepoOptionsBundle(),
                                     include_sync=True,
                                     include_ssl=True,
                                     include_proxy=True,
                                     include_basic_auth=True,
                                     include_throttling=True,
                                     include_unit_policy=True,
                                     include_download_policy=True)

        # Adds all distributor config options
        repo_options.add_distributor_config_to_command(self)

    # -- importer config mixin overrides --------------------------------------

    def populate_sync_group(self):
        """
        Overridden from ImporterConfigMixin to add in the skip option.
        """
        super(RpmRepoCreateCommand, self).populate_sync_group()
        self.sync_group.add_option(repo_options.OPT_SKIP)

    def parse_sync_group(self, user_input):
        config = ImporterConfigMixin.parse_sync_group(self, user_input)
        safe_parse(user_input, config, repo_options.OPT_SKIP.keyword, CONFIG_KEY_SKIP)
        return config

    # -- create repository command overrides ----------------------------------

    def run(self, **kwargs):

        # Remove any entries that weren't set by the user and translate those that are
        # explicitly empty to None
        arg_utils.convert_removed_options(kwargs)

        # Gather data
        repo_id = kwargs.pop(std_options.OPTION_REPO_ID.keyword)
        description = kwargs.pop(std_options.OPTION_DESCRIPTION.keyword, None)
        display_name = kwargs.pop(std_options.OPTION_NAME.keyword, None)
        notes = kwargs.pop(std_options.OPTION_NOTES.keyword, None) or {}

        # Add a note to indicate this is an RPM repository
        notes[pulp_constants.REPO_NOTE_TYPE_KEY] = constants.REPO_NOTE_RPM

        # Generate the appropriate plugin configs
        try:
            importer_config = self.parse_user_input(kwargs)
            yum_distributor_config = args_to_yum_distributor_config(kwargs)
            export_distributor_config = args_to_export_distributor_config(kwargs)
        except InvalidConfig, e:
            self.prompt.render_failure_message(str(e))
            return os.EX_DATAERR

        # Special (temporary until we fix the distributor) distributor config handling
        self.process_relative_url(repo_id, importer_config, yum_distributor_config)
        self.process_relative_url(repo_id, importer_config, export_distributor_config)
        self.process_yum_distributor_serve_protocol(yum_distributor_config)
        self.process_export_distributor_serve_protocol(export_distributor_config)

        # Create the repository; let exceptions bubble up to the framework exception handler
        distributors = self.package_distributors(yum_distributor_config, export_distributor_config)
        self.context.server.repo.create_and_configure(
            repo_id, display_name, description, notes,
            ids.TYPE_ID_IMPORTER_YUM, importer_config, distributors
        )

        msg = _('Successfully created repository [%(r)s]')
        self.prompt.render_success_message(msg % {'r': repo_id})

    def package_distributors(self, yum_distributor_config, export_distributor_config):
        """
        Creates the tuple structure for adding multiple distributors during the create call.
        :return: value to pass the bindings describing the distributors being added
        :rtype:  tuple
        """
        distributors = [
            dict(distributor_type_id=ids.TYPE_ID_DISTRIBUTOR_YUM,
                 distributor_config=yum_distributor_config,
                 auto_publish=True, distributor_id=ids.YUM_DISTRIBUTOR_ID),
            dict(distributor_type_id=ids.TYPE_ID_DISTRIBUTOR_EXPORT,
                 distributor_config=export_distributor_config,
                 auto_publish=False, distributor_id=ids.EXPORT_DISTRIBUTOR_ID)
        ]
        return distributors

    # -- distributor config odditity handling ---------------------------------

    def process_relative_url(self, repo_id, importer_config, distributor_config):
        """
        During create (but not update), if the relative path isn't specified it is derived
        from the feed_url.

        Ultimately, this belongs in the distributor itself. When we rewrite the yum distributor,
        we'll remove this entirely from the client. jdob, May 10, 2013
        """
        if 'relative_url' not in distributor_config:
            if importer_constants.KEY_FEED in importer_config:
                if importer_config[importer_constants.KEY_FEED] is None:
                    self.prompt.render_failure_message(_('Given repository feed URL is invalid.'))
                    return
                url_parse = urlparse(encode_unicode(importer_config[importer_constants.KEY_FEED]))

                if url_parse[2] in ('', '/'):
                    relative_path = '/' + repo_id
                else:
                    # make the path relative
                    relative_path = url_parse[2][1:]
                distributor_config['relative_url'] = relative_path
            else:
                distributor_config['relative_url'] = repo_id

    def process_yum_distributor_serve_protocol(self, yum_distributor_config):
        """
        Both http and https must be specified in the distributor config, so make sure they are
        initially set here (default to only https).
        """
        yum_distributor_config['https'] = yum_distributor_config.get('https', True)
        yum_distributor_config['http'] = yum_distributor_config.get('http', False)

    def process_export_distributor_serve_protocol(self, export_distributor_config):
        """
        Ensure default values for http and https for export distributor if they are not set.
        """
        export_distributor_config['https'] = export_distributor_config.get('https', True)
        export_distributor_config['http'] = export_distributor_config.get('http', False)


class RpmRepoUpdateCommand(UpdateRepositoryCommand, ImporterConfigMixin):
    def __init__(self, context):
        super(RpmRepoUpdateCommand, self).__init__(context)

        # The built-in options will be reorganized under a group to keep the
        # help text from being unwieldly. The base class will add them by
        # default, so remove them here before they are readded under a group.
        # self.options = []

        # Adds all downloader-related importer config options
        ImporterConfigMixin.__init__(self,
                                     options_bundle=RpmRepoOptionsBundle(),
                                     include_sync=True,
                                     include_ssl=True,
                                     include_proxy=True,
                                     include_basic_auth=True,
                                     include_throttling=True,
                                     include_unit_policy=True,
                                     include_download_policy=True)

        # Adds all distributor config options
        repo_options.add_distributor_config_to_command(self)

    def populate_sync_group(self):
        """
        Overridden from ImporterConfigMixin to add in the skip option.
        """
        super(RpmRepoUpdateCommand, self).populate_sync_group()
        self.sync_group.add_option(repo_options.OPT_SKIP)

    def parse_sync_group(self, user_input):
        """
        Overridden from ImporterConfigMixin to add the skip option

        :param user_input: keyword arguments from the CLI framework containing user input
        :type  user_input: dict

        :return: suitable representation of the config that can be stored on the repo
        :rtype:  dict
        """
        config = super(RpmRepoUpdateCommand, self).parse_sync_group(user_input)
        safe_parse(user_input, config, repo_options.OPT_SKIP.keyword, CONFIG_KEY_SKIP)
        return config

    def run(self, **kwargs):

        # Remove any entries that weren't set by the user and translate those that are
        # explicitly empty to None
        arg_utils.convert_removed_options(kwargs)

        # Gather data
        repo_id = kwargs.pop(std_options.OPTION_REPO_ID.keyword)
        description = kwargs.pop(std_options.OPTION_DESCRIPTION.keyword, None)
        display_name = kwargs.pop(std_options.OPTION_NAME.keyword, None)
        notes = kwargs.pop(std_options.OPTION_NOTES.keyword, None)

        try:
            importer_config = self.parse_user_input(kwargs)
            yum_distributor_config = args_to_yum_distributor_config(kwargs)
            export_distributor_config = args_to_export_distributor_config(kwargs)
        except InvalidConfig, e:
            self.prompt.render_failure_message(str(e))
            return

        # only add distributors if they actually have changes
        distributor_configs = {}
        if yum_distributor_config:
            distributor_configs[ids.TYPE_ID_DISTRIBUTOR_YUM] = yum_distributor_config
        if export_distributor_config:
            distributor_configs[ids.TYPE_ID_DISTRIBUTOR_EXPORT] = export_distributor_config

        response = self.context.server.repo.update_repo_and_plugins(
            repo_id, display_name, description, notes,
            importer_config, distributor_configs
        )

        if not response.is_async():
            msg = _('Repository [%(r)s] successfully updated')
            self.prompt.render_success_message(msg % {'r': repo_id})
        else:
            self.poll([response.response_body], kwargs)


# -- utilities ----------------------------------------------------------------

def args_to_yum_distributor_config(kwargs):
    """
    Takes the arguments read from the CLI and converts the client-side input
    to the server-side expectations. The supplied dict will not be modified.

    @return: config to pass into the add/update distributor calls
    @raise InvalidConfig: if one or more arguments is not valid for the distributor
    """
    distributor_config = _prep_config(kwargs, YUM_DISTRIBUTOR_CONFIG_KEYS)

    # Read in the contents of any files that were specified
    file_arguments = ('auth_cert', 'auth_ca', 'https_ca', 'gpgkey')
    arg_utils.convert_file_contents(file_arguments, distributor_config)

    # There is an explicit flag for enabling/disabling repository protection.
    # This may be useful to expose to the user to quickly turn on/off repo
    # auth for debugging purposes. For now, if the user has specified an auth
    # CA, assume they also want to flip that protection flag to true.
    if 'auth_ca' in distributor_config:
        if distributor_config['auth_ca'] is None:
            # This would occur if the user requested to remove the CA (as
            # compared to not mentioning it at all, which is the outer if statement.
            distributor_config['protected'] = False
        else:
            # If there is something in the CA, assume it's turning on auth and
            # flip the flag to true.
            distributor_config['protected'] = True

    # Repoview tool uses sqlite files, thus we enable generation of the latter.
    if distributor_config.get('repoview', False):
        distributor_config['generate_sqlite'] = True

    return distributor_config


def args_to_export_distributor_config(kwargs):
    """
    Takes the arguments read from the CLI and converts the client-side input
    to the server-side expectations. The supplied dict will not be modified.

    @return: config to pass into the add/update distributor calls
    @raise InvalidConfig: if one or more arguments is not valid for the distributor
    """
    distributor_config = _prep_config(kwargs, EXPORT_DISTRIBUTOR_CONFIG_KEYS)

    # Read in the contents of any files that were specified
    file_arguments = ('https_ca',)
    arg_utils.convert_file_contents(file_arguments, distributor_config)

    return distributor_config


def _prep_config(kwargs, plugin_config_keys):
    """
    Performs common initialization for both importer and distributor config
    parsing. The common conversion includes:

    * Create a base config dict pulling the given plugin_config_keys from the
      user-specified arguments
    * Translate the client-side argument names into the plugin expected keys
    * Strip out any None values which means the user did not specify the
      argument in the call
    * Convert any empty strings into None which represents the user removing
      the config value

    @param plugin_config_keys: one of the *_CONFIG_KEYS constants
    @return: dictionary to use as the basis for the config
    """

    # User-specified flags use hyphens but the importer/distributor want
    # underscores, so do a quick translation here before anything else.
    for k in kwargs.keys():
        val = kwargs.pop(k)
        new_key = k.replace('-', '_')
        kwargs[new_key] = val

    # Populate the plugin config with the plugin-relevant keys in the user args
    user_arg_keys = [k[1] for k in plugin_config_keys]
    plugin_config = dict([(k, v) for k, v in kwargs.items() if k in user_arg_keys])

    # Simple name translations
    for plugin_key, cli_key in plugin_config_keys:
        if cli_key in plugin_config:
            plugin_config[plugin_key] = plugin_config.pop(cli_key, None)

    return plugin_config
