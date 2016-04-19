from gettext import gettext as _
import glob
import os
import shutil
import subprocess

from pulp.plugins.util.publish_step import PublishStep
from pulp.server.util import copytree

class CopySelectedStep(PublishStep):
    """
    Copy a directory from another directory

    :param source_dir: The directory to copy
    :type source_dir: str
    :param target_dir: Fully qualified name of the final location to copy to
    :type target_dir: str
    :param step_type: The id of the step, so that this step can be used with custom names.
    :type step_type: str
    :param delete_before_copy: Whether or not the contents of the target_dir should be cleared
                              before copying from source_dir
    :type delete_before_copy: bool
    :param preserve_symlinks: Whether or not the symlinks in the original source directory should
                              be copied as symlinks or as the content of the linked files.
                              Defaults to False.
    :type preserve_symlinks: bool
    """
    def __init__(self, source_dir, target_dir, step_type=None, delete_before_copy=True,
                 globs=["*"]):
        step_type = step_type if step_type else reporting_constants.PUBLISH_STEP_TAR
        super(CopySelectedStep, self).__init__(step_type)
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.delete_before_copy = delete_before_copy
        self.description = _('Copying selected files')
        self.globs = globs

    def process_main(self):
        """
        Copy one directory to another.
        """
        if self.delete_before_copy:
            shutil.rmtree(self.target_dir, ignore_errors=True)
        files = []
        for glob_expr in self.globs:
            matched = glob.glob(os.path.join(self.source_dir, glob_expr))
            files.extend([os.path.join(self.source_dir, fn) for fn in matched])
        for f in files:
            if os.path.isdir(f):
                copytree(os.path.join(f),
                         os.path.join(self.target_dir, os.path.basename(f)))
            else:
                shutil.copy(f, self.target_dir)

class Lazy(object):
    overwrite = ("__str__",)
    def __new__(cls, _type, caller, *args, **kwargs):
        lazy = super(Lazy, cls).__new__(cls, *args, **kwargs)
        lazy.caller = caller
        lazy._type = _type
        lazy.real_object = None
        #setattr(cls, '_invoke_method', invoke_method)

        for (name, member) in inspect.getmembers(_type):
            if (hasattr(cls, name) and name not in lazy.overwrite)\
               or not inspect.ismethoddescriptor(member):
                continue
            setattr(cls, name, lazy._partialmethod('_invoke_method', name))
            #setattr(cls, name, functools.partial(cls._invoke_method, name))
        return lazy

    def _invoke_method(self, method_name, *args, **keywords):
        if not self.real_object:
            self.real_object = self._type(self.caller())
        method = getattr(self.real_object, method_name)
        return method(*args, **keywords)

    def _partialmethod(cls, method, *args, **kw):
        def call(obj, *more_args, **more_kw):
            call_kw = kw.copy()
            call_kw.update(more_kw)
            return getattr(obj, method)(*(args+more_args), **call_kw)
        return call

def run(cmd, stdin=None, stdout=None, stderr=None, cwd=None, env=None, bufsize=None):
    ret = subprocess.Popen(cmd, stdin=stdin, stdout=stdout, stderr=stderr, env=env,
                           bufsize=bufsize)
    for x in ("stdin", "stdout", "stderr"):
        locals()[x] = subprocess.PIPE if locals()[x] else None

    ret.wait()
    return (ret.returncode, ret.stdout.read())


def common_path(dirs):
    _common_path = os.path.commonprefix(dirs)
    if not _common_path.endswith("/"):
        _common_path = os.path.dirname(_common_path)
    return _common_path
