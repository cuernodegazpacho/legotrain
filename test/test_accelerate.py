''' Unit test that verifies if power index sequences are correctly generated,
    given the index limiting values and the sense of movement. 
'''
import unittest

sign = lambda x: x and (1, -1)[x<0]

class _TestTrain():
    '''
    This class contains the generator code for the power sequences that are
    used by the train acceleration algorithm. The generator code outputs the
    sequence in a form suitable for use in unit tests.
    '''
    def __init__(self):
        self.power_index = 0

    # This method generates the power index values for an
    # acceleration/deceleration ramp.
    def accelerate(self, new_power_index=1, time=1.0):

        # new power index must have same sign as current power index
        current_power_index_sign = sign(self.power_index)
        new_power_index_sign = sign(new_power_index)

        # only check if non-zero
        if self.power_index != 0 and new_power_index != 0 and \
            new_power_index_sign != current_power_index_sign:
            raise RuntimeError("error in power index signs")

        current_power_index_abs_value = abs(self.power_index)
        new_power_index_abs_value = abs(new_power_index)

        # find sense of required sequence
        downward = new_power_index_abs_value < current_power_index_abs_value
        if downward:
            power_index_step = -1
        else:
            power_index_step = 1

        # find sign of power indices
        power_index_sign = new_power_index_sign
        if power_index_sign == 0:
            power_index_sign = current_power_index_sign

        # generate sequence of power index values. We add +-1 to account for the
        # way the range function works.
        power_index_range = list(range(current_power_index_abs_value,
                                       new_power_index_abs_value + power_index_step,
                                       power_index_step))

        # accelerate needs the time between each speed setting in the ramp
        sleep_time = time / len(power_index_range)

        return self.accelerate_in_threasd(power_index_range, power_index_sign, sleep_time=sleep_time)

    # dummy method that just return the sequence of values. In the real application,
    # it should call the appropriate method in the train instance that would ultimately
    # access the train motor via a thread.
    def accelerate_in_threasd(self, power_index_values, power_index_signal, sleep_time=0.3):
        return [x * power_index_signal for x in power_index_values]


class TestListElements(unittest.TestCase):
    def setUp(self):
        self.train = _TestTrain()

    # descending sequence from large power to small power, direct sense
    def test_1(self):
        self.train.power_index = 6
        result = self.train.accelerate(new_power_index=1)
        self.assertListEqual(result, [6,5,4,3,2,1])

    # descending sequence from large power to small power, reverse sense
    def test_2(self):
        self.train.power_index = -6
        result = self.train.accelerate(new_power_index=-1)
        self.assertListEqual(result, [-6,-5,-4,-3,-2,-1])

    # descending sequence from large power to zero power, direct sense
    def test_3(self):
        self.train.power_index = 6
        result = self.train.accelerate(new_power_index=0)
        self.assertListEqual(result, [6,5,4,3,2,1,0])

    # descending sequence from large power to zero power, reverse sense
    def test_4(self):
        self.train.power_index = -6
        result = self.train.accelerate(new_power_index=0)
        self.assertListEqual(result, [-6,-5,-4,-3,-2,-1,0])

    # ascending sequence from small power to large power, direct sense
    def test_5(self):
        self.train.power_index = 1
        result = self.train.accelerate(new_power_index=6)
        self.assertListEqual(result, [1,2,3,4,5,6])

    # ascending sequence from small power to large power, reverse sense
    def test_6(self):
        self.train.power_index = -1
        result = self.train.accelerate(new_power_index=-6)
        self.assertListEqual(result, [-1,-2,-3,-4,-5,-6])

    # ascending sequence from zero power to large power, direct sense
    def test_7(self):
        self.train.power_index = 0
        result = self.train.accelerate(new_power_index=6)
        self.assertListEqual(result, [0,1,2,3,4,5,6])

    # ascending sequence from zero power to large power, reverse sense
    def test_8(self):
        self.train.power_index = 0
        result = self.train.accelerate(new_power_index=-6)
        self.assertListEqual(result, [0,-1,-2,-3,-4,-5,-6])

    # degenerate sequence
    def test_9(self):
        self.train.power_index = 3
        result = self.train.accelerate(new_power_index=3)
        self.assertListEqual(result, [3])

    # degenerate sequence with zero
    def test_10(self):
        self.train.power_index = 0
        result = self.train.accelerate(new_power_index=0)
        self.assertListEqual(result, [0])


if __name__ == "__main__":
    unittest.main()
