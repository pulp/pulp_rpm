from pulp_rpm.common import constants, models

type_done_map = {
    models.RPM: 'rpm_done',
    models.SRPM: 'srpm_done',
    models.DRPM: 'drpm_done',
}

class ContentReport(dict):
    def __init__(self):
        self['error_details'] = []
        self['items_total'] = items_total
        self['items_left'] = items_total
        self['size_total'] = size_total
        self['size_left'] = size_total
        self['state'] = constants.STATE_NOT_STARTED
        self['details'] = {
            'rpm_done' : 0,
            'rpm_total': 0,
            'srpm_done' : 0,
            'srpm_total': 0,
            'drpm_done' : 0,
            'drpm_total': 0,
            'tree_done' : 0,
            'tree_total': 0,
        }

    def set_initial_values(self, counts, total_size):
        self['size_total'] = total_size
        self['items_total'] = sum(counts.values())

    def success(self, model):
        self['items_left'] -= 1
        self['size_left'] -= model.metadata['size']
        done_attribute = type_done_map[model.TYPE]
        self['details'][done_attribute] += 1

    def failure(self, model, error_report):
        self['items_left'] -= 1
        self['size_left'] -= model.metadata['size']
        done_attribute = type_done_map[model.TYPE]
        self['details'][done_attribute] += 1
        self['error_details'].append(error_report)
