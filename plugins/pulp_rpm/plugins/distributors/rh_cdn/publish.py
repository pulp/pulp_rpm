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
import time
from pprint import pformat
import subprocess

from pulp.plugins.model import PublishReport
from pulp.server.exceptions import MissingResource

from pulp_rpm.yum_plugin import util

from . import configuration

_LOG = util.getLogger(__name__)


class Publisher(object):
    """
    Yum CDN publisher class that is responsible for the actual publishing
    of a yum repository to CDN.
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

        self.progress_report = PublishReport(False, [], [])
        self.canceled = False

        self.timestamp = str(time.time())

    def publish(self):
        """
        Publish the contents of the repository and their metadata via HTTP/HTTPS.

        :return: report describing the publication
        :rtype:  pulp.plugins.model.PublishReport
        """
        _LOG.debug('Starting Yum CDN publish for repository: %s' % self.repo.id)
        (is_successful, error) = self.copy()
        _LOG.debug('Publish completed with progress:\n%s' % pformat(self.progress_report))
        if is_successful:
            self.success()
        else:
            self.fail(error)
        return self.build_report()

    def copy(self):
        """
        Copy using rsync

        # TODO (ctang) copying to cdn still needs to be matured.
        #   1. the specific location on cdn to copy things to is still unclear
        #   2. authentication to cdn is still assuming things
        """
        self.progress('Init the copy',
            {'repo': self.repo.id, 'config': self.config.flatten()})
        repo_dir = configuration.get_repo_dir(self.repo, self.config)
        self.progress('Start copying', {'repo': self.repo.id, 'repo_dir': repo_dir})

        handler_type = self.config.get('handler_type')
        handler_cls = CopyHandler.get_handler_with_name(handler_type)
        handler = handler_cls(repo_dir, None, self.config)
        return handler.handle()

    def success(self):
        _LOG.debug('Successfully published for repository: %s' % self.repo.id)
        self.progress_report.success_flag = True

    def cancel(self):
        """
        Cancel an in-progress publication.
        """
        _LOG.debug('Canceling publish for repository: %s' % self.repo.id)

        if self.canceled:
            return

        self.canceled = True
        self.progress_report.canceled_flag = self.canceled

    def fail(self, reason):
        _LOG.debug('Failed publishing for repository: %s on reason "%s"'
            % (self.repo.id, reason))
        self.progress_report.success_flag = False
        self.progress("Failed copying", reason)

    def progress(self, summary=None, details=None):
        report = self.progress_report
        report.summary.append(summary)
        report.details.append((summary, details))

    def build_report(self):
        """
        Build a PublishReport instance for publish() to return.

        :return: report describing the publication
        :rtype:  pulp.plugins.model.PublishReport
        """
        report = self.progress_report
        if report.success_flag:
            report_builder = self.conduit.build_success_report
        elif report.canceled_flag:
            report_builder = self.conduit.build_cancel_report
        else: # failed in this case
            report_builder = self.conduit.build_failure_report
        return report_builder(report.summary, report.details)


class TypeCopyHandler(type):
    """
    A metaclass to rule all CopyHandler classes. Used as a
    plugin container.
    """

    def __init__(cls, name, bases, attrs):

        if not hasattr(cls, 'handlers'):
            setattr(cls, 'handlers', {})
        else:
            cls.handlers[cls.handler_name] = cls


class CopyHandler(object):

    __metaclass__ = TypeCopyHandler

    def __init__(self, src=None, dest=None, config=None):

        self.src = src
        self.dest = dest
        self.config = config

    @classmethod
    def get_handler_with_name(cls, name):
        """
        Public class method to get a registered handler with name.

        :param: name copy handler name, should be configured for a repo
            and its distributor.
        :type:  str lowercased
        """
        try:
            return cls.handlers[name]
        except KeyError:
            raise MissingResource(copy_handler_type=name)

    def handle(self):
        """
        Public method to call for any subclass of CopyHandler

        :return: Result and error message describing the error, if any.
        :rtype:  tupe of (bool, str)
        """
        return self.copy()

    def copy(self):
        """
        Base class to implement the actual copying.

        :return: Result and error message describing the error, if any.
        :rtype:  tupe of (bool, str)
        """
        raise NotImplemented


class RsyncHandler(CopyHandler):

    handler_name = 'rsync'

    _CMD = "rsync"
    _ARGS = "-avz"

    def __init__(self, src=None, dest=None, config=None):
        """
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        self.dest = self.make_dest_name()
        super(RsyncHandler, self).__init__(src, dest, config)

    def make_dest_name(self):
        """
        Parse from self.config information
        to make up a hostname used in rsync command.

        :return: str of the combination of user, host, and dir.
        :rtype:  str
        """
        cdn = self.config.get('cdn', None)
        # TODO (ctang) if cdn is None: raise error
        user = cdn['user']
        host = cdn['host']
        dest_dir = cdn['dir']
        return '%s@%s:%s' % (user, host, dest_dir)


    def copy(self):
        return self.check_call()

    def check_call(self):
        """
        Basically a wrapper to call subprocess.check_call.
        """
        is_successful = False
        error_msg = None

        args = [self._CMD, self._ARGS, str(self.src), str(self.dest)]
        with open(os.devnull, 'w') as devnull:
            try:
                subprocess.check_call(
                    args, stdin=devnull, stdout=devnull, stderr=devnull,
                    shell=False # Never using shell=True here for security's sake
                    )
                is_successful = True
            except subprocess.CalledProcessError, msg:
                error_msg = str(msg)

        return (is_successful, error_msg)
