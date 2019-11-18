from collections import namedtuple
import psutil


START = 'START'
END = 'END'
ConsumedRamLogEntry = namedtuple('ConsumedRamLogEntry', ('nodeid', 'on', 'consumed_ram'))
consumed_ram_log = []


def get_consumed_ram():
    """Gets consumed ram."""
    info = {}
    for proc in psutil.process_iter():
        identifier = "PID: {} - Proccess: {}".format(proc.pid, proc.name())
        info.update({identifier: (proc.memory_info().rss, proc.memory_info().vms)})
    return info
