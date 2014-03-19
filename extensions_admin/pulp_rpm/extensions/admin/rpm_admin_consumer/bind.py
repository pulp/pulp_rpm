from pulp.client.commands.consumer.bind import (
    ConsumerBindCommand, ConsumerUnbindCommand)


YUM_DISTRIBUTOR_ID = 'yum_distributor'


class YumConsumerBindCommand(ConsumerBindCommand):

    def add_distributor_option(self):
        pass

    def get_distributor_id(self, kwargs):
        return YUM_DISTRIBUTOR_ID


class YumConsumerUnbindCommand(ConsumerUnbindCommand):

    def add_distributor_option(self):
        pass

    def get_distributor_id(self, kwargs):
        return YUM_DISTRIBUTOR_ID

