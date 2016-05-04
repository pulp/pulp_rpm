import sys

from StringIO import StringIO
from subprocess import PIPE
from unittest import TestCase

from mock import patch, Mock, call as Call

from pulp.common.compat import json
from pulp_rpm.handlers.lib import facade


MODULE = 'pulp_rpm.handlers.lib.facade'


class TestDecorators(TestCase):

    @patch(MODULE + '.Call')
    def test_request(self, call):
        @facade.request
        def hello():
            return 18

        # test
        inst = Mock()
        returned = hello(inst, 1, 2)

        # validation
        call.return_value.assert_called_once_with(1, 2)
        self.assertEqual(returned, call.return_value.return_value)

    def test_report(self):
        @facade.report
        def hello():
            pass
        inst = Mock(writer=Mock())
        args = (1, 2)

        # test
        hello(inst, *args)

        # validation
        inst.writer.send_progress.assert_called_once_with({
            facade.Request.METHOD: 'hello',
            facade.Request.ARGS: args})


class TestPackage(TestCase):

    @patch(MODULE + '.Call')
    def test_install(self, call):
        names = (1, 2, 3)

        # test
        package = facade.Package()
        package.install(names)

        # validation
        call.return_value.assert_called_once_with(names)

    @patch(MODULE + '.Call')
    def test_update(self, call):
        names = (1, 2, 3)

        # test
        package = facade.Package()
        package.update(names)

        # validation
        call.return_value.assert_called_once_with(names)

    @patch(MODULE + '.Call')
    def test_uninstall(self, call):
        names = [1, 2, 3]

        # test
        package = facade.Package()
        package.uninstall(names)

        # validation
        call.return_value.assert_called_once_with(names)

    @patch(MODULE + '.Call')
    def test_options(self, call):
        # test
        package = facade.Package()
        options = package.options()

        # validation
        self.assertEqual(options, dict(apply=package.apply, importkeys=package.importkeys))


class TestPackageGroup(TestCase):

    @patch(MODULE + '.Call')
    def test_install(self, call):
        names = [1, 2, 3]

        # test
        group = facade.PackageGroup()
        group.install(names)

        # validation
        call.return_value.assert_called_once_with(names)

    @patch(MODULE + '.Call')
    def test_uninstall(self, call):
        names = [1, 2, 3]

        # test
        package = facade.PackageGroup()
        package.uninstall(names)

        # validation
        call.return_value.assert_called_once_with(names)

    @patch(MODULE + '.Call')
    def test_options(self, call):
        # test
        package = facade.PackageGroup()
        options = package.options()

        # validation
        self.assertEqual(options, dict(apply=package.apply, importkeys=package.importkeys))


class TestEnd(TestCase):

    def test_init(self):
        result = 123
        end = facade.End(result)
        self.assertEqual(end.result, result)


class TestCall(TestCase):

    def test_init(self):
        inst = Mock()
        method = Mock()

        # test
        call = facade.Call(inst, method)

        # validation
        self.assertEqual(call.inst, inst)
        self.assertEqual(call.method, method)

    @patch(MODULE + '.Popen')
    @patch(MODULE + '.Call.read')
    @patch(MODULE + '.Call.send_request')
    def test_call(self, send_request, read, popen):
        child = Mock()
        popen.return_value = child
        inst = Mock()
        method = Mock()
        args = (1, 2)

        # test
        call = facade.Call(inst, method)
        call(*args)

        # validation
        popen.assert_called_once_with([sys.executable, facade.__file__], stdin=PIPE, stdout=PIPE)
        send_request.assert_called_once_with(child, args)
        read.assert_called_once_with(child)
        child.stdin.close.assert_called_once_with()
        child.stdout.close.assert_called_once_with()
        child.wait.assert_called_once_with()

    def test_send_request(self):
        child = Mock()
        inst = Mock()
        inst.options.return_value = {'A': 1}
        method = Mock(__name__='hello')
        args = (1, 2)

        # test
        call = facade.Call(inst, method)
        call.send_request(child, args)

        # validation
        self.assertEqual(
            child.stdin.write.call_args_list,
            [
                Call(json.dumps({
                    facade.Request.OPTIONS: inst.options.return_value,
                    facade.Request.CLASS: inst.__class__.__name__,
                    facade.Request.METHOD: method.__name__,
                    facade.Request.ARGS: args,
                })),
                Call('\n')
            ])
        child.stdin.flush.assert_called_once_with()

    def test_on_progress(self):
        inst = Mock(progress=Mock())
        method = Mock()
        args = (1, 2)
        payload = {
            facade.Request.METHOD: 'hello',
            facade.Request.ARGS: args
        }

        # test
        call = facade.Call(inst, method)
        call.on_progress(payload)

        # validation
        inst.progress.hello.assert_called_once_with(*args)

    def test_on_progress_not_report(self):
        inst = Mock(progress=None)
        method = Mock()
        args = (1, 2)
        payload = {
            facade.Request.METHOD: 'hello',
            facade.Request.ARGS: args
        }

        # test
        call = facade.Call(inst, method)
        call.on_progress(payload)

    def test_on_error(self):
        description = 'Something bad happened'
        payload = {
            facade.ReplyWriter.DESCRIPTION: description
        }

        # test
        call = facade.Call(Mock(), Mock())
        try:
            call.on_error(payload)
            self.fail(msg='Exception not raised.')
        except Exception as e:
            self.assertEqual(e.args, (description,))

    def test_on_result(self):
        payload = 'done!'

        # test
        call = facade.Call(Mock(), Mock())
        try:
            call.on_result(payload)
            self.fail(msg='End not raised.')
        except facade.End as e:
            self.assertEqual(e.result, payload)

    @patch(MODULE + '.Call.on_progress')
    def test_on_reply_progress(self, on_progress):
        payload = Mock()
        reply = {
            facade.ReplyWriter.CODE: facade.ReplyWriter.PROGRESS,
            facade.ReplyWriter.PAYLOAD: payload
        }

        # test
        call = facade.Call(Mock(), Mock())
        call.on_reply(reply)

        # validation
        on_progress.assert_called_once_with(payload)

    @patch(MODULE + '.Call.on_error')
    def test_on_reply_error(self, on_error):
        payload = Mock()
        reply = {
            facade.ReplyWriter.CODE: facade.ReplyWriter.ERROR,
            facade.ReplyWriter.PAYLOAD: payload
        }

        # test
        call = facade.Call(Mock(), Mock())
        call.on_reply(reply)

        # validation
        on_error.assert_called_once_with(payload)

    @patch(MODULE + '.Call.on_result')
    def test_on_reply_result(self, on_result):
        payload = Mock()
        reply = {
            facade.ReplyWriter.CODE: facade.ReplyWriter.RESULT,
            facade.ReplyWriter.PAYLOAD: payload
        }

        # test
        call = facade.Call(Mock(), Mock())
        call.on_reply(reply)

        # validation
        on_result.assert_called_once_with(payload)

    @patch(MODULE + '.log')
    def test_on_reply_unknown(self, log):
        payload = Mock()
        reply = {
            facade.ReplyWriter.CODE: 'unknown',
            facade.ReplyWriter.PAYLOAD: payload
        }

        # test
        call = facade.Call(Mock(), Mock())
        call.on_reply(reply)

        # validation
        self.assertTrue(log.debug.called)

    @patch(MODULE + '.Call.on_reply')
    def test_read(self, on_reply):
        child = Mock()
        replies = [
            {facade.ReplyWriter.CODE: facade.ReplyWriter.PROGRESS},
            {facade.ReplyWriter.CODE: facade.ReplyWriter.RESULT},
        ]
        lines = [
            json.dumps(r) + '\n' for r in replies
        ]
        lines.append('This is just noise to be ignored\n')
        lines.append('')  # EOF
        child.stdout.readline.side_effect = lines

        # test
        call = facade.Call(Mock(), Mock())
        call.read(child)

        # validation
        self.assertEqual(on_reply.call_args_list, [Call(r) for r in replies])

    @patch(MODULE + '.Call.on_reply')
    def test_read_with_result(self, on_reply):
        end = facade.End(18)
        on_reply.side_effect = end

        child = Mock()
        replies = [
            {facade.ReplyWriter.CODE: facade.ReplyWriter.RESULT},
            'The End'
        ]
        child.stdout.readline.side_effect = [
            json.dumps(r) + '\n' for r in replies
        ] + ['']

        # test
        call = facade.Call(Mock(), Mock())
        result = call.read(child)

        # validation
        self.assertEqual(on_reply.call_args_list, [Call(r) for r in replies[:-1]])
        self.assertEqual(result, end.result)


class TestProgressReport(TestCase):

    def test_push_step(self):
        name = 'started'
        writer = Mock()

        # test
        report = facade.ProgressReport(writer)
        report.push_step(name)

        # validation
        writer.send_progress.assert_called_once_with({
            facade.Request.METHOD: 'push_step',
            facade.Request.ARGS: (name,)})

    def test_set_status(self):
        status = True
        writer = Mock()

        # test
        report = facade.ProgressReport(writer)
        report.set_status(status)

        # validation
        writer.send_progress.assert_called_once_with({
            facade.Request.METHOD: 'set_status',
            facade.Request.ARGS: (status,)})

    def test_set_action(self):
        action = 'downloading'
        package = 'tiger-1.0-1'
        writer = Mock()

        # test
        report = facade.ProgressReport(writer)
        report.set_action(action, package)

        # validation
        writer.send_progress.assert_called_once_with({
            facade.Request.METHOD: 'set_action',
            facade.Request.ARGS: (action, package)})

    def test_error(self):
        description = 'This failed'
        writer = Mock()

        # test
        report = facade.ProgressReport(writer)
        report.error(description)

        # validation
        writer.send_progress.assert_called_once_with({
            facade.Request.METHOD: 'error',
            facade.Request.ARGS: (description,)})


class TestReplyWriter(TestCase):

    @patch(MODULE + '.ReplyWriter.send')
    def test_send_progress(self, send):
        payload = {'A': 1}

        # test
        writer = facade.ReplyWriter(None)
        writer.send_progress(payload)

        # validation
        send.assert_called_once_with(facade.ReplyWriter.PROGRESS, payload)

    @patch(MODULE + '.ReplyWriter.send')
    def test_send_result(self, send):
        payload = {'A': 1}

        # test
        writer = facade.ReplyWriter(None)
        writer.send_result(payload)

        # validation
        send.assert_called_once_with(facade.ReplyWriter.RESULT, payload)

    @patch(MODULE + '.ReplyWriter.send')
    def test_send_error(self, send):
        payload = {'A': 1}

        # test
        writer = facade.ReplyWriter(None)
        writer.send_error(payload)

        # validation
        send.assert_called_once_with(
            facade.ReplyWriter.ERROR, {facade.ReplyWriter.DESCRIPTION: payload})

    def test_send(self):
        pipe = Mock()
        code = facade.ReplyWriter.RESULT
        payload = {'A': 1}
        message = {
            facade.ReplyWriter.CODE: code,
            facade.ReplyWriter.PAYLOAD: payload
        }

        # test
        writer = facade.ReplyWriter(pipe)
        writer.send(code, payload)

        # validation
        self.assertEqual(
            pipe.write.call_args_list,
            [
                Call(json.dumps(message)),
                Call('\n')
            ])
        pipe.flush.assert_called_once_with()


class TestRequest(TestCase):

    @patch(MODULE + '.ReplyWriter')
    def test_init(self, writer):
        _output = StringIO()
        _input = StringIO('{}')

        # test
        request = facade.Request(_input=_input, _output=_output)

        # validation
        writer.assert_called_once_with(_output)
        self.assertEqual(request.document, {})
        self.assertEqual(request.writer, writer.return_value)

    @patch(MODULE + '.rpmtools')
    def test_get_object(self, rpmtools):
        rpmtools.Dog = Mock(__name__='Dog')
        options = {
            'A': 1,
            'B': 2
        }
        _input = StringIO(
            json.dumps(
                {
                    facade.Request.OPTIONS: options,
                    facade.Request.CLASS: rpmtools.Dog.__name__
                }))

        # test
        request = facade.Request(_input=_input, _output=StringIO())
        inst = request.get_object()

        # validation
        rpmtools.Dog.assert_called_once_with(**options)
        self.assertEqual(inst, rpmtools.Dog.return_value)

    @patch(MODULE + '.rpmtools', None)
    def test_get_object_not_found(self):
        _input = StringIO(
            json.dumps(
                {
                    facade.Request.OPTIONS: {},
                    facade.Request.CLASS: 'Invalid'
                }))

        # test
        request = facade.Request(_input=_input, _output=StringIO())
        self.assertRaises(ValueError, request.get_object)

    def test_get_method(self):
        dog = Mock(__name__='Dog')
        _input = StringIO(
            json.dumps(
                {
                    facade.Request.METHOD: 'bark'
                }))

        # test
        request = facade.Request(_input=_input, _output=StringIO())
        method = request.get_method(dog)

        # validation
        self.assertEqual(method, dog.bark)

    def test_get_method_not_found(self):
        _input = StringIO(
            json.dumps(
                {
                    facade.Request.METHOD: 'bark'
                }))

        # test
        request = facade.Request(_input=_input, _output=StringIO())
        self.assertRaises(ValueError, request.get_method, None)

    @patch(MODULE + '.ReplyWriter.send')
    @patch(MODULE + '.rpmtools')
    def test_call(self, rpmtools, send):
        dog = Mock(__name__='Dog')
        dog.bark.return_value = 18
        rpmtools.Dog = Mock(__name__='Dog', return_value=dog)
        _output = StringIO()
        _input = StringIO(
            json.dumps(
                {
                    facade.Request.OPTIONS: {},
                    facade.Request.CLASS: rpmtools.Dog.__name__,
                    facade.Request.METHOD: 'bark',
                    facade.Request.ARGS: [1, 2]
                }))

        # test
        request = facade.Request(_input=_input, _output=_output)
        request()

        # validation
        send.assert_called_once_with(facade.ReplyWriter.RESULT, dog.bark.return_value)

    @patch(MODULE + '.ReplyWriter.send')
    @patch(MODULE + '.rpmtools')
    def test_call_exception(self, rpmtools, send):
        raised = ValueError('This Failed')
        dog = Mock(__name__='Dog')
        dog.bark.side_effect = raised
        rpmtools.Dog = Mock(__name__='Dog', return_value=dog)
        _output = StringIO()
        _input = StringIO(
            json.dumps(
                {
                    facade.Request.OPTIONS: {},
                    facade.Request.CLASS: rpmtools.Dog.__name__,
                    facade.Request.METHOD: 'bark',
                    facade.Request.ARGS: [1, 2]
                }))

        # test
        request = facade.Request(_input=_input, _output=_output)
        request()

        # validation
        send.assert_called_once_with(facade.ReplyWriter.ERROR, dict(description=str(raised)))


class TestMain(TestCase):

    @patch(MODULE + '.Request')
    def test_main(self, request):
        facade.main()
        request.assert_called_once_with()
        request.return_value.assert_called_once_with()
