import random

import unittest

MINIMUM_TIME_STATION = 2.
MAXIMUM_TIME_STATION = 12.


def get_time_station(train):
    time_station = random.uniform(MINIMUM_TIME_STATION, MAXIMUM_TIME_STATION)
    return time_station


####################  TEST   ##################################
class TestTimer(unittest.TestCase):
    def test_get_time_station(self):
        self.assertLessEqual(get_time_station(None), MAXIMUM_TIME_STATION)
        self.assertGreaterEqual(get_time_station(None), MINIMUM_TIME_STATION)

if __name__ == '__main__':
    unittest.main()