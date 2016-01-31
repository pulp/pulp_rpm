import mock
from pulp.plugins.model import Unit
from pulp.plugins.conduits.profiler import ProfilerConduit


def get_repo(repo_id):
    class Repo(object):
        def __init__(self, repo_id):
            self.id = repo_id

    return Repo(repo_id)


def get_profiler_conduit(type_id=None, existing_units=None, repo_bindings=[], repo_units=[],
                         errata_rpms=[]):
    def get_bindings(consumer_id=None):
        return repo_bindings

    def get_units(repo_id, criteria=None):
        ret_val = []
        if existing_units:
            for u in existing_units:
                if criteria:
                    if u.type_id in criteria.type_ids:
                        if u.unit_key == criteria.unit_filters:
                            ret_val.insert(0, u)
                        else:
                            ret_val.append(u)
                else:
                    ret_val.append(u)
        return ret_val

    def get_repo_units(repo_id, content_type_id, additional_unit_fields=[]):
        ret_val = []
        for u in repo_units:
            if u.type_id != content_type_id:
                continue
            metadata = {}
            metadata['unit_id'] = u.id
            for f in additional_unit_fields:
                if f == 'pkglist':
                    metadata[f] = [{'packages': errata_rpms}]
                else:
                    metadata[f] = 'test-additional-field'
            ret_val.append(Unit(content_type_id, u.unit_key, metadata, None))
        return ret_val

    sync_conduit = mock.Mock(spec=ProfilerConduit)
    sync_conduit.get_units.side_effect = get_units
    sync_conduit.get_repo_units.side_effect = get_repo_units
    sync_conduit.get_bindings.side_effect = get_bindings
    return sync_conduit
