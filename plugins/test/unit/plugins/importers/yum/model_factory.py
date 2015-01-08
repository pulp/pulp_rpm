import functools
from itertools import count

from pulp.plugins.model import Unit

from pulp_rpm.plugins.db import models


_rpm_counter = count()
_srpm_counter = count()
_drpm_counter = count()
_group_counter = count()
_category_counter = count()
_environment_counter = count()
_yum_md_file_counter = count()
_errata_counter = count()


def as_units(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        models = f(*args, **kwargs)
        return [Unit(model.TYPE, model.unit_key, model.metadata, '') for model in models]
    return wrapper


def rpm_models(num, same_name_and_arch=False):
    ret = []
    count = _rpm_counter.next()
    name = 'name-%d' % count
    for i in range(num):
        if not same_name_and_arch:
            name = 'name-%d' % count
        ret.append(models.RPM(
            name,
            '0',
            '2.1.%d' % count,
            '1-1',
            'x86_64',
            'sha256',
            'somehash-%d' % count,
            {}
        ))
        count = _rpm_counter.next()
    return ret


@as_units
def rpm_units(num, same_name_and_arch=False):
    return rpm_models(num, same_name_and_arch)


def srpm_models(num, same_name_and_arch=False):
    ret = []
    count = _srpm_counter.next()
    name = 'name-%d' % count
    for i in range(num):
        if not same_name_and_arch:
            name = 'name-%d' % count
        ret.append(models.SRPM(
            name,
            '0',
            '2.1.%d' % count,
            '1-1',
            'x86_64',
            'sha256',
            'somehash-%d' % count,
            {}
        ))
        count = _srpm_counter.next()
    return ret


@as_units
def srpm_units(num, same_name_and_arch=False):
    return srpm_models(num, same_name_and_arch)


def drpm_models(num, same_filename_and_arch=False):
    ret = []
    count = _drpm_counter.next()
    filename = 'filename-%d' % count
    for i in range(num):
        if not same_filename_and_arch:
            filename = 'filename-%d' % count
        ret.append(models.DRPM(
            '0',
            '2.1.%d' % count,
            '1-1',
            filename,
            'sha256',
            'somehash-%d' % count,
            {}
        ))
        count = _drpm_counter.next()
    return ret


@as_units
def drpm_units(num, same_filename_and_arch=False):
    return drpm_models(num, same_filename_and_arch)


def group_models(num, same_repo=True):
    ret = []
    count = _group_counter.next()
    repo_id = 'repo-%d' % count
    for i in range(num):
        if not same_repo:
            repo_id = 'repo-%d' % count
        ret.append(models.PackageGroup(
            'name-%d' % count,
            repo_id,
            {'default_package_names':['abc%d' % count, 'xyz%d' % count]}
        ))
        count = _group_counter.next()
    return ret


@as_units
def group_units(num, same_repo=True):
    return group_models(num, same_repo)


def category_models(num, same_repo=True):
    ret = []
    count = _category_counter.next()
    repo_id = 'repo-%d' % count
    for i in range(num):
        if not same_repo:
            repo_id = 'repo-%d' % count
        ret.append(models.PackageCategory(
            'name-%d' % count,
            repo_id,
            {'packagegroupids':['abc%d' % count, 'xyz%d' % count]}
        ))
        count = _category_counter.next()
    return ret


@as_units
def category_units(num, same_repo=True):
    return category_models(num, same_repo)


def environment_models(num, same_repo=True):
    ret = []
    count = _environment_counter.next()
    repo_id = 'repo-%d' % count
    for i in range(num):
        if not same_repo:
            repo_id = 'repo-%d' % count
        ret.append(models.PackageEnvironment(
            'name-%d' % count,
            repo_id,
            {'group_ids': ['abc%d' % count, 'xyz%d' % count],
             'options': [{'default': False, 'group': 'op%d' % count},
                         {'default': True, 'group': 'bz%d' % count}]
            }
        ))
        count = _environment_counter.next()
    return ret


@as_units
def environment_units(num, same_repo=True):
    return environment_models(num, same_repo)


def yum_md_file():
    return models.YumMetadataFile(models.YumMetadataFile.TYPE,
                                  'repo-%d' % _yum_md_file_counter.next(), {})


def errata_models(num):
    ret = []
    count = _errata_counter.next()
    for i in range(num):
        rpms = [r.unit_key for r in rpm_models(2)]
        for r in rpms:
            del r['checksum']
            del r['checksumtype']
        ret.append(models.Errata(
            'name-%d' % count,
            {'pkglist': [{'packages': rpms, 'name': 'somerepo-%d' % count}]}
        ))
        count = _errata_counter.next()
    return ret


@as_units
def errata_units(num):
    return errata_models(num)
