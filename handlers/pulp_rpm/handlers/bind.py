# -*- coding: utf-8 -*-

import os
from logging import getLogger

from pulp.agent.lib.handler import BindHandler
from pulp.agent.lib.report import BindReport, CleanReport

from pulp_rpm.handlers import repolib


log = getLogger(__name__)


class RepoHandler(BindHandler):
    """
    A yum repository bind request handler.
    Manages the /etc/yum.repos.d/pulp.repo based on bind requests.
    """

    def bind(self, conduit, binding, options):
        """
        Bind a repository.
        @param conduit: A handler conduit.
        @type conduit: L{pulp.agent.lib.conduit.Conduit}
        @param binding: A binding to add/update.
          A binding is: {type_id:<str>, repo_id:<str>, details:<dict>}
        @type binding: dict
        @param options: Bind options.
        @type options: dict
        @return: A bind report.
        @rtype: L{BindReport}
        """
        log.info('bind: %s, options:%s', binding, options)
        cfg = conduit.get_consumer_config().graph()
        details = binding['details']
        repo_id = binding['repo_id']
        repo_name = details['repo_name']
        urls = self.__urls(details)
        report = BindReport(repo_id)
        verify_ssl = cfg.server.verify_ssl.lower() != 'false'
        repolib.bind(
            cfg.filesystem.repo_file,
            os.path.join(cfg.filesystem.mirror_list_dir, repo_id),
            cfg.filesystem.gpg_keys_dir,
            cfg.filesystem.cert_dir,
            repo_id,
            repo_name,
            urls,
            details.get('gpg_keys', {}),
            details.get('client_cert'),
            len(urls) > 0,
            verify_ssl=verify_ssl,
            ca_path=cfg.server.ca_path)
        report.set_succeeded()
        return report

    def unbind(self, conduit, repo_id, options):
        """
        Bind a repository.
            @param conduit: A handler conduit.
        @type conduit: L{pulp.agent.lib.conduit.Conduit}
        @param repo_id: A repository ID.
        @type repo_id: str
        @param options: Unbind options.
        @type options: dict
        @return: An unbind report.
        @rtype: L{BindReport}
        """
        log.info('unbind: %s, options:%s', repo_id, options)
        cfg = conduit.get_consumer_config().graph()
        report = BindReport(repo_id)
        repolib.unbind(
            cfg.filesystem.repo_file,
            os.path.join(cfg.filesystem.mirror_list_dir, repo_id),
            cfg.filesystem.gpg_keys_dir,
            cfg.filesystem.cert_dir,
            repo_id)
        report.set_succeeded()
        return report

    def clean(self, conduit):
        """
        Clean up artifacts associated with the handler.
        @param conduit: A handler conduit.
        @type conduit: L{pulp.agent.lib.conduit.Conduit}
        @return: A clean report.
        @rtype: L{CleanReport}
        """
        log.info('clean')
        report = CleanReport()
        cfg = conduit.get_consumer_config().graph()
        repolib.delete_repo_file(cfg.filesystem.repo_file)
        report.set_succeeded()
        return report

    def __urls(self, details):
        """
        Construct a list of URLs.
        @param details: The bind details (payload).
        @type details: dict
        @return: A list of URLs.
        @rtype: list
        """
        urls = []
        protocol = self.__protocol(details)
        if not protocol:
            # not enabled
            return urls
        hosts = details['server_name']
        if not isinstance(hosts, list):
            hosts = [hosts,]
        path = details['relative_path']
        for host in hosts:
            url = '://'.join((protocol, host))
            urls.append(url+path)
        return urls

    def __protocol(self, details):
        """
        Select the protcol based on preferences.
        @param details: The bind details (payload).
        @type details: dict
        @return: The selected protocol.
        @rtype: str
        """
        ordering = ('https', 'http')
        selected = details['protocols']
        for p in ordering:
            if p.lower() in selected:
                return p
