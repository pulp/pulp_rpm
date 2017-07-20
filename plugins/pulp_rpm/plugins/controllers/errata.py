import mongoengine

from pulp_rpm.plugins.db.models import Errata, ErratumPkglist


def create_or_update_pkglist(erratum, repo_id):
    """
    Create or update erratum pkglist and save it to DB.
    Also make pkglist on Errata instance empty (in memory, not saved to DB yet).

    :param erratum: An erratum unit being imported
    :type erratum: pulp_rpm.plugins.db.models.Errata
    :param repo_id: An id of repository into which the erratum unit is being imported
    :type repo_id: str
    """
    new_pkglist = ErratumPkglist(errata_id=erratum.errata_id,
                                 repo_id=repo_id,
                                 collections=erratum.pkglist)
    try:
        new_pkglist.save()
    except mongoengine.NotUniqueError:
        # check if erratum unit exists or should be updated, if so - update its pkglist
        existing_erratum = Errata.objects.filter(**erratum.unit_key).first()
        new_erratum = erratum
        if not existing_erratum or existing_erratum.update_needed(new_erratum):
            existing_pkglist = ErratumPkglist.objects.filter(**new_pkglist.model_key).first()
            existing_pkglist.collections = new_pkglist.collections
            existing_pkglist.save()
    # pkglist is saved to a separate collection, we no longer need it in the erratum unit itself
    erratum.pkglist = []
