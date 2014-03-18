# -*- coding: utf-8 -*-

import os
from logging import getLogger

from pulp.agent.lib.handler import SystemHandler
from pulp.agent.lib.report import RebootReport


log = getLogger(__name__)


class LinuxHandler(SystemHandler):
    """
    Linux system handler
    """

    def reboot(self, conduit, options):
        """
        Schedule a system reboot.
        @param conduit: A handler conduit.
        @type conduit: L{pulp.agent.lib.conduit.Conduit}
        @param options: reboot options
            Supported:
                apply (bool): Actually schedule the reboot.
                minutes (int): Minutes to delay the reboot.
        @type options: dict
        """
        report = RebootReport()
        apply = options.get('apply', True)
        if apply:
            minutes = options.get('minutes', 1)
            command = 'shutdown -r +%d' % minutes
            log.info(command)
            os.system(command)
            details = dict(minutes=minutes)
            report.set_succeeded(details)
        else:
            report.succeeded()
        return report
