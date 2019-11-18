
from itertools import groupby
from pulp_rpm.tests.performance.utils import (
    ConsumedRamLogEntry,
    consumed_ram_log,
    get_consumed_ram,
    START,
    END,
)

LEAK_LIMIT = 10 * 1024 * 1024


def pytest_runtest_setup(item):
    """Starting to measure memory on setup."""
    log_entry = ConsumedRamLogEntry(item.nodeid, START, get_consumed_ram())
    consumed_ram_log.append(log_entry)


def pytest_runtest_teardown(item):
    """Logging memory consumption on teardown."""
    log_entry = ConsumedRamLogEntry(item.nodeid, END, get_consumed_ram())
    consumed_ram_log.append(log_entry)


def pytest_terminal_summary(terminalreporter):
    """Display memory consumption on terminal."""
    grouped = groupby(consumed_ram_log, lambda entry: entry.nodeid)
    for nodeid, (start_entries, end_entries) in grouped:
        for process_name, start_entry in start_entries.consumed_ram.items():
            end_entry = end_entries.consumed_ram.get(process_name)
            if not end_entry:
                continue
            leaked_rss = end_entry[0] - start_entry[0]
            leaked_vms = end_entry[1] - start_entry[1]
            leaked = leaked_rss + leaked_vms
            if leaked < LEAK_LIMIT:
                continue
            terminalreporter.write(
                '{} - LEAKED: {:.2f}MB rss | {:.2f}MB vms in {}\n'.format(
                    process_name, leaked_rss / 1024 / 1024, leaked_vms / 1024 / 1024, nodeid))
