# Facade used to execute rpmtools class methods in child process.
#
# Protocol
#
# --> {"class": "", "options": {}, "method": "", "args": []}
# <-- {"code": "P", "payload": {"args": [], "method": ""}}
# <-- {"code": "R", "payload": {}}
# <-- {"code": "E", "description": ""}
#

import re
import sys

from gettext import gettext as _
from logging import getLogger
from subprocess import Popen, PIPE
from threading import RLock

from pulp.common.compat import json
from pulp_rpm.handlers.lib import rpmtools


log = getLogger(__file__)


def request(fn):
    """
    Decorator used to execute method in the child process.

    :param fn: A method function.
    """
    def inner(inst, *args):
        call = Call(inst, fn)
        return call(*args)
    return inner


def report(fn):
    """
    Decorator used to report progress to the parent process.

    :param fn: A method function.
    """
    def inner(inst, *args):
        payload = {
            Request.METHOD: fn.__name__,
            Request.ARGS: args
        }
        inst.writer.send_progress(payload)
    return inner


class Package(rpmtools.Package):
    """
    Package management facade.

    Returned *Package* NEVRA+ objects:
      - qname   : qualified name
      - repoid  : repository id
      - name    : package name
      - epoch   : package epoch
      - version : package version
      - release : package release
      - arch    : package arch
    """

    @request
    def install(self, names):
        """
        Install packages by name.

        :param names: A list of package names.
        :type names: [str,]
        :return: Packages installed.
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

    @request
    def update(self, names=()):
        """
        Update installed packages.

        When (names) is not specified, all packages are updated.
        :param names: A list of package names.
        :type names: [str,]
        :return: Packages installed (updated).
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

    @request
    def uninstall(self, names):
        """
        Uninstall (erase) packages by name.
        :param names: A list of package names to be removed.
        :type names: list
        :return: Packages uninstalled (erased).
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

    def options(self):
        """
        Get the options passed to __init__().

        :return: Options used for initialization.
        :rtype: dict
        """
        options = dict(self.__dict__)
        options.pop('progress', None)
        return options


class PackageGroup(rpmtools.PackageGroup):
    """
    PackageGroup management facade.
    """

    @request
    def install(self, names):
        """
        Install package groups by name.

        :param names: A list of package group names.
        :type names: list
        :return: Packages installed.
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

    @request
    def uninstall(self, names):
        """
        Uninstall package groups by name.

        :param names: A list of package group names.
        :type names: [str,]
        :return: Packages uninstalled.
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

    def options(self):
        """
        Get the options passed to __init__().

        :return: Options used for initialization.
        :rtype: dict
        """
        options = dict(self.__dict__)
        options.pop('progress', None)
        return options


class End(Exception):
    """
    Signals the end of communication between the parent and child.
    """

    def __init__(self, result=None):
        """
        :param result: The result of a request executed in the child process.
        :type result: object
        """
        super(End, self).__init__()
        self.result = result


class Call(object):
    """
    A method "call" that is executed in the child process.

    :type REPLY_PATTERN: re.Pattern
    :ivar inst: An object.
    :type inst: (Package|PackageGroup)
    :ivar method: An instance method to be executed.
    :type method: str
    """

    REPLY_PATTERN = re.compile(r'^\{.+\}\n$')

    def __init__(self, inst, method):
        """
        :param inst: An object.
        :type inst: (Package|PackageGroup)
        :param method: An instance method to be executed.
        :type method: str
        """
        self.inst = inst
        self.method = method

    def __call__(self, *args):
        """
        Invoke the method in a child process.

        :param args: Arguments passed to the method.
        :param args: tuple
        :return: The value returned by the method.
        :rtype: object
        """
        child = Popen([sys.executable, __file__], stdin=PIPE, stdout=PIPE)
        try:
            self.send_request(child, args)
            result = self.read(child)
            return result
        finally:
            child.stdin.close()
            child.stdout.close()
            child.wait()

    def send_request(self, child, args):
        """
        Write the RMI request to the child stdin.

        :param child: A child process.
        :type child: Popen
        :param args: Arguments passed to the method.
        :type args: tuple
        """
        message = {
            Request.OPTIONS: self.inst.options(),
            Request.CLASS: self.inst.__class__.__name__,
            Request.METHOD: self.method.__name__,
            Request.ARGS: args
        }
        message = json.dumps(message)
        child.stdin.write(message)
        child.stdin.write('\n')
        child.stdin.flush()
        log.debug(_('Request sent: %(m)s'), dict(m=message))

    def on_progress(self, payload):
        """
        Process a progress report message from the child.
        Invokes the specified method on the local progress reporting object.

        :param payload: The message payload { method: '', args: (,)}.
        :type payload: dict
        """
        progress = self.inst.progress
        if not progress:
            return
        method = payload[Request.METHOD]
        args = payload[Request.ARGS]
        method = getattr(progress, method)
        method(*args)

    def on_error(self, payload):
        """
        Process an error message from the child.
        The error is propagated by raising an Exception.

        :param payload: The message payload { description: ''}.
        :type payload: dict
        :raises Exception: always.
        """
        description = payload[ReplyWriter.DESCRIPTION]
        raise Exception(description)

    def on_result(self, payload):
        """
        Process the RMI result message from the child.

        :param payload: The message payload.
        :type payload: dict
        :raises End: always
        """
        raise End(payload)

    def on_reply(self, reply):
        """
        A reply message has been received from the child process.
        Dispatched to the on_ method based on *code* included in the message.

        :param reply: A message (reply) from the child process.
        :type reply: dict
        """
        code = reply[ReplyWriter.CODE]
        payload = reply[ReplyWriter.PAYLOAD]
        methods = {
            ReplyWriter.RESULT: self.on_result,
            ReplyWriter.PROGRESS: self.on_progress,
            ReplyWriter.ERROR: self.on_error,
        }
        method = methods.get(code)
        if method:
            method(payload)
        else:
            log.debug(_('Reply code: %(c)s not-valid'), dict(c=code))

    def read(self, child):
        """
        Read replies from the child process and dispatch them.

        :param child: A child process.
        :type child: Popen
        """
        while True:
            try:
                reply = child.stdout.readline()
                if not reply:
                    raise End()
                if not Call.REPLY_PATTERN.match(reply):
                    continue
                log.debug(_('Reply received: %(m)s'), dict(m=reply))
                reply = json.loads(reply)
                self.on_reply(reply)
            except End, e:
                return e.result


class ProgressReport(rpmtools.ProgressReport):
    """
    A facade for the Progress report instance in the parent process.
    Method invocation sends messages to the parent.

    :ivar writer: Writer used to send messages to the parent process.
    :type writer: ReplyWriter
    """

    def __init__(self, writer):
        """
        :param writer: Used to send messages to the parent process.
        :type writer: ReplyWriter
        """
        super(ProgressReport, self).__init__()
        self.writer = writer

    @report
    def push_step(self, name):
        """
        Push the specified step.
        First, update the last status to SUCCEEDED.

        :param name: The step name to push.
        :type name: str
        """

    @report
    def set_status(self, status):
        """
        Update the status of the current step.

        :param status: A status.
        :type status: bool
        """

    @report
    def set_action(self, action, package):
        """
        Set the specified package action for the current step.

        :param action: The action being performed.
        :type action: str
        :param package: A package description
        :type package: str
        """

    @report
    def error(self, msg):
        """
        Report an error on the current step.

        :param msg: The error message to report.
        :type msg: str
        """


class ReplyWriter(object):
    """
    Writes replies to the parent process.
    """

    # properties
    CODE = 'code'
    PAYLOAD = 'payload'

    # codes
    ERROR = 'E'
    PROGRESS = 'P'
    RESULT = 'R'

    # properties
    DESCRIPTION = 'description'

    _mutex = RLock()

    def __init__(self, pipe):
        """
        :param pipe: Communications pipe to parent process.
        :type pipe: file-like
        """
        self.pipe = pipe

    def send_progress(self, payload):
        """
        Send a progress report.

        :param payload: The actual progress report.
        :type payload: dict
        """
        self.send(ReplyWriter.PROGRESS, payload)

    def send_result(self, payload):
        """
        Send the RMI result.

        :param payload: The actual progress report.
        :type payload: dict
        """
        self.send(ReplyWriter.RESULT, payload)

    def send_error(self, payload):
        """
        Send an error report.

        :param payload: The error description.
        :type payload: str
        """
        self.send(ReplyWriter.ERROR, {ReplyWriter.DESCRIPTION: payload})

    def send(self, code, payload):
        """
        Write a message to the parent process using the pipe.

        :param code: A message code (ERROR|PROGRESS|REPORT).
        :type code: str
        :param payload: A payload to send.
        :type payload: (str|dict)
        """
        message = {
            ReplyWriter.CODE: code,
            ReplyWriter.PAYLOAD: payload
        }
        ReplyWriter._mutex.acquire()
        try:
            self.pipe.write(json.dumps(message))
            self.pipe.write('\n')
            self.pipe.flush()
        finally:
            ReplyWriter._mutex.release()


class Request(object):
    """
    Request handler that runs in the child process.
    """

    # properties
    OPTIONS = 'options'
    CLASS = 'class'
    METHOD = 'method'
    ARGS = 'args'

    def __init__(self, _input=sys.stdin, _output=sys.stdout):
        """
        :param _input: Input (pipe) to the child.
        :type _input: file-like
        :param _output: Output (pipe) to the parent.
        :type _output: file-like
        """
        self.document = json.loads(_input.readline())
        self.writer = ReplyWriter(_output)

    def get_object(self):
        """
        Build a target class instance.

        :return: A class instance.
        :rtype: object
        """
        name = self.document[Request.CLASS]
        try:
            options = self.document[Request.OPTIONS]
            cls = getattr(rpmtools, name)
            inst = cls(**options)
            inst.progress = ProgressReport(self.writer)
            return inst
        except AttributeError:
            raise ValueError('Class "%s" not found' % name)

    def get_method(self, inst):
        """
        Get the target instance method.

        :param inst: A target object.
        :type inst: object
        :return: The target instance method.
        :rtype: method
        """
        method = self.document[Request.METHOD]
        try:
            return getattr(inst, method)
        except AttributeError:
            raise ValueError('Method "%s" not found' % method)

    def __call__(self):
        """
        Execute the RMI request.
        """
        try:
            _object = self.get_object()
            method = self.get_method(_object)
            args = self.document.get(Request.ARGS)
            details = method(*args)
            self.writer.send_result(details)
        except Exception, e:
            description = str(e)
            log.exception(description)
            self.writer.send_error(description)


def main():
    _request = Request()
    _request()


if __name__ == '__main__':
    main()
