"""
As part of our applicability work, consumer profiles now have a new "hash" value. These get
generated whenever the consumers report their profile, and this migration goes ahead and
precalculates them for all existing consumer profiles.
"""

from pulp.server.db.connection import get_collection
from pulp.server.db.model import consumer

from pulp_rpm.plugins.profilers import yum


def migrate(*args, **kwargs):
    """
    For each RPM consumer profile, calculate and add a 'hash' attribute.
    """
    profiler = yum.YumProfiler()
    consumer_unit_profiles_collection = get_collection('consumer_unit_profiles')
    # For each RPM profile, let's add a profile hash
    rpm_content_type = 'rpm'
    for consumer_unit_profile in consumer_unit_profiles_collection.find(
            {'content_type': rpm_content_type}):
        if 'profile_hash' not in consumer_unit_profile:
            profile = consumer_unit_profile['profile']
            # The update_profile() method does not use the three arguments passed here as None. This
            # method will sort the profile so we can get a repeatable hash
            profile = profiler.update_profile(consumer=None, content_type=rpm_content_type,
                                              profile=profile, config=None)
            profile_hash = consumer.UnitProfile.calculate_hash(profile)

            # Now let's update the consumer_unit_profile with the hash
            consumer_unit_profiles_collection.update(
                {'_id': consumer_unit_profile['_id']},
                {'$set': {'profile_hash': profile_hash}}, safe=True)
