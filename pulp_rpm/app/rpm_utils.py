from pulp_rpm.app.constants import PULP_PACKAGE_ATTRS


def nevra(name):
    """
    Parse NEVRA.

    inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA
    Args:
        name: NEVRA (jay-3:3.10-4.fc3.x86_64)
    Return:
        parsed NEVRA (name, epoch, version, release, architecture)
                      str    int     str      str         str
    """
    if name.count(".") < 1:
        msg = "failed to parse nevra {} not a valid nevra".format(name)
        raise ValueError(msg)

    arch_dot_pos = name.rfind(".")
    arch = name[arch_dot_pos + 1:]

    ret = nevr(name[:arch_dot_pos])
    ret[PULP_PACKAGE_ATTRS.ARCH] = arch
    return ret


def nevr(name):
    """
    Parse NEVR.

    inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA
    Args:
        name: NEVR (jay-3:3.10-4.fc3.x86_64)
    Return:
        parsed NEVR (name, epoch, version, release)
                     str    int     str      str
    """
    if name.count("-") < 2:  # release or name is missing
        msg = "failed to parse nevr {} not a valid nevr".format(name)
        raise ValueError(msg)

    release_dash_pos = name.rfind("-")
    release = name[release_dash_pos + 1:]
    name_epoch_version = name[:release_dash_pos]
    name_dash_pos = name_epoch_version.rfind("-")
    package_name = name_epoch_version[:name_dash_pos]

    epoch_version = name_epoch_version[name_dash_pos + 1:].split(":")
    if len(epoch_version) == 1:
        epoch = 0
        version = epoch_version[0]
    elif len(epoch_version) == 2:
        epoch = int(epoch_version[0])
        version = epoch_version[1]
    else:
        # more than one ':'
        msg = "failed to parse nevr {} not a valid nevr".format(name)
        raise ValueError(msg)

    return {
        PULP_PACKAGE_ATTRS.NAME: package_name,
        PULP_PACKAGE_ATTRS.EPOCH: epoch,
        PULP_PACKAGE_ATTRS.VERSION: version,
        PULP_PACKAGE_ATTRS.RELEASE: release
    }
