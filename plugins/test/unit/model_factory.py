# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import functools
from itertools import count

from pulp.plugins.model import Unit

from pulp_rpm.common import models

_rpm_counter = count()
_srpm_counter = count()
_drpm_counter = count()
_yum_md_file_counter = count()


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


def yum_md_file():
    return models.YumMetadataFile(models.YumMetadataFile.TYPE,
                                  'repo-%d' % _yum_md_file_counter.next(), {})
