import decimal
from corelibs.statsd import Client
from corelibs.coreGrinder import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()

NUM_TYPES = int, long, float, decimal.Decimal

class Gauge(Client):
    '''Class to implement a statsd gauge

    '''
    def send(self, subname, value):
        '''Send the data to statsd via self.connection

        :keyword subname: The subname to report the data to (appended to the
            client name)
        :type subname: str
        :keyword value: The gauge value to send
        '''
        assert isinstance(value, NUM_TYPES)
        name = self._get_name(self.name, subname)
        if logger.isTraceEnabled():
            logger.trace('>>> SENDING: %s %s|g' % (name, value))

        return Client._send(self, {name: '%s|g' % value})