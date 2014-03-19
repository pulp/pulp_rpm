import os
import sys
import traceback

from pulp_rpm.plugins.distributors.yum import metadata
from pulp_rpm.plugins.importers.yum.repomd import packages, updateinfo


def main():
    try:
        update_info_file_path = sys.argv[1]
        output_directory = sys.argv[2]

    except IndexError:
        print 'Usage: %s <update info file path> <output directory>'
        return os.EX_NOINPUT

    update_info_file_handle = open(update_info_file_path, 'r')
    package_list_generator = packages.package_list_generator(update_info_file_handle, 'update', updateinfo.process_package_element)

    with metadata.UpdateinfoXMLFileContext(output_directory) as update_info_file_context:

        try:
            for erratum_unit in package_list_generator:
                #pprint(erratum_unit.metadata)
                update_info_file_context.add_unit_metadata(erratum_unit)

        except:
            traceback.print_exc(file=sys.stderr)
            return os.EX_SOFTWARE

    return os.EX_OK

# -- main ----------------------------------------------------------------------

if __name__ == '__main__':
    sys.exit(main())
