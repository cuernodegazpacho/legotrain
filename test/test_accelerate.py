''' Script to verify that power index sequences are correctly generated
    given the index limiting values and the sense of movement. 
'''

sign = lambda x: x and (1, -1)[x<0]

# class that provides dummy methods to test train acceleration algorithm
class _TestTrain():
    def __init__(self, power_index):
        self.power_index = power_index

    def _slowdown(self, new_power_index=1, time=1.0):

        # new power index must have same sign as current power index

        current_power_index_sign = sign(self.power_index)
        new_power_index_sign = sign(new_power_index)

        print(current_power_index_sign, new_power_index_sign)


        if self.power_index != 0 and new_power_index != 0 and \
            new_power_index_sign != current_power_index_sign:
            raise RuntimeError("error in power index signs")

        current_power_index_abs_value = abs(self.power_index)
        new_power_index_abs_value = abs(new_power_index)

        # generate downward sequence of power index values. We subtract 1
        # to account for the way the range function works.
        power_index_step = -1
        power_index_range = list(range(current_power_index_abs_value,
                                       new_power_index_abs_value - 1,
                                       power_index_step))

        # accelerate needs the time between each speed setting in the ramp
        sleep_time = time / len(power_index_range)

        self.accelerate(power_index_range, current_power_index_sign, sleep_time=sleep_time)

    def accelerate(self, power_index_values, power_index_signal, sleep_time=0.3):

        power_index_values = [x * power_index_signal for x in power_index_values]

        print("values: ", power_index_values, "  signal: ", power_index_signal)


# descending sequence from large power to small power, direct sense
train = _TestTrain(6)
train._slowdown(new_power_index=1)

# descending sequence from large power to small power, reverse sense
train = _TestTrain(-6)
train._slowdown(new_power_index=-1)

# descending sequence from large power to zero power, direct sense
train = _TestTrain(6)
train._slowdown(new_power_index=0)

# descending sequence from large power to zero power, reverse sense
train = _TestTrain(-6)
train._slowdown(new_power_index=0)
