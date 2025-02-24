import random

import unittest

# time ranges for short and long stops
MINIMUM_TIME_STATION_SHORT = 1.5
MAXIMUM_TIME_STATION_SHORT = 11.
MINIMUM_TIME_STATION_LONG = 15.
MAXIMUM_TIME_STATION_LONG = 45.


class VariableTimerValue:
    """
    Class that provides random values for the time a train spends stopped at a station.
    The values come from two separate uniform distributions, one for short times, the other
    for longer ones. Successive calls to get_time_station() cyclically return values from
    the short distribution, then the long.
    TODO
    and then zero. The zero value must be handled by
    the caller; it's initial purpose is to signal the situation in which the train doesn't
    stop at all.
    """
    def __init__(self, short=True):
        self.short = short

    def get_time_station(self):
        if self.short:
            time_station = random.uniform(MINIMUM_TIME_STATION_SHORT, MAXIMUM_TIME_STATION_SHORT)
        else:
            time_station = random.uniform(MINIMUM_TIME_STATION_LONG, MAXIMUM_TIME_STATION_LONG)

        self.short = not self.short

        return time_station


####################  TEST   ##################################

class TestTimer(unittest.TestCase):
    def test_get_time_station(self):

        # need to construct here to preserve the sequence
        # with short and long values
        test_timer = VariableTimerValue()

        t1 = test_timer.get_time_station()
        t2 = test_timer.get_time_station()

        self.assertLessEqual(t1, MAXIMUM_TIME_STATION_SHORT)
        self.assertGreaterEqual(t1, MINIMUM_TIME_STATION_SHORT)

        self.assertLessEqual(t2, MAXIMUM_TIME_STATION_LONG)
        self.assertGreaterEqual(t2, MINIMUM_TIME_STATION_LONG)

if __name__ == '__main__':
    unittest.main()