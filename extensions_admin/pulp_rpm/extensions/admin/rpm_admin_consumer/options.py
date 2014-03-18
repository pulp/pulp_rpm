from gettext import gettext as _

from pulp.client.extensions.extensions import PulpCliFlag


FLAG_NO_COMMIT = PulpCliFlag('--no-commit', _('test the transaction without committing it'))

FLAG_REBOOT = PulpCliFlag('--reboot', _('reboot after a successful transaction'))

FLAG_IMPORT_KEYS = PulpCliFlag('--import-keys', _('import GPG keys as needed'))

FLAG_ALL_CONTENT = PulpCliFlag('--all', _('update all content units'), ['-a'])
