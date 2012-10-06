# Please keep the following in alphabetical order so it's easier to determine
# if something is in the list

# Server Code
PACKAGES="pulp_rpm"

# RPM Support
PACKAGES="$PACKAGES,rpm_admin_consumer"
PACKAGES="$PACKAGES,rpm_repo"
PACKAGES="$PACKAGES,rpm_sync"
PACKAGES="$PACKAGES,rpm_units_copy"
PACKAGES="$PACKAGES,rpm_units_search"
PACKAGES="$PACKAGES,rpm_upload"
PACKAGES="$PACKAGES,yum_distributor"
PACKAGES="$PACKAGES,yum_importer"

# Test Directories
TESTS="pulp_rpm/test/unit "

nosetests --with-coverage --cover-html --cover-erase --cover-package $PACKAGES $TESTS
