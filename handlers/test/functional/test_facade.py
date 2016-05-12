from logging import basicConfig, DEBUG

from pulp_rpm.handlers.lib.facade import Package
from pulp_rpm.handlers.lib.rpmtools import ProgressReport


def install_package(names):
    package = Package(progress=ProgressReport())
    details = package.install(names)
    print '{} installed'.format(names)
    print package.progress.steps
    print package.progress.details
    print details


def uninstall_package(names):
    package = Package(progress=ProgressReport())
    details = package.uninstall(names)
    print '{} uninstalled'.format(names)
    print package.progress.steps
    print package.progress.details
    print details

if __name__ == '__main__':
    basicConfig(level=DEBUG)
    uninstall_package(['zsh'])
    install_package(['zsh'])
