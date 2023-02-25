import sys
import time
import logging
from threading import Timer
from time import sleep
from pynput import keyboard

from pylgbst.hub import SmartHub, RemoteHandset
from pylgbst.peripherals import Voltage, Current, LEDLight, RemoteButton

# logging.basicConfig(level=logging.DEBUG)


class SimpleTrain:
    '''
    Encapsulates details of a Train. A simple train is a train *not* equipped
    with a sensor. It may or may not have a headlight. If it does, the headlight
    brightness is controlled by the motor power setting.

    For now, an instance of this class keeps tabs on the motor power setting, as
    well as battery and headlights status (if so equipped).

    This class also reports voltage and current at stdout.

    :param name: train name, used in the report
    :param report: if True, report voltage and current
    :param address: UUID of the train's internal hub

    :ivar hub: the train's internal hub
    :ivar motor: references the train's motor
    :ivar power_index: motor power level
    :ivar voltage: populated only when report=True
    :ivar current: populated only when report=True
    '''
    def __init__(self, name, report=False, address='86996732-BF5A-433D-AACE-5611D4C6271D'): # test hub

        self.hub = SmartHub(address=address)

        self.motor_power = MotorPower()
        self.power_index = 0

        self.name = name
        self.voltage = 0.
        self.current = 0.
        self.motor = self.hub.port_A
        self.headlight = None
        self.headlight_thread = None

        if isinstance(self.hub.port_B, LEDLight):
            self.headlight = self.hub.port_B
            self.headlight_brightness = self.headlight.brightness

        if report:
            self._start_report()

    def _start_report(self):
        def _print_values():
            print("\r%s  voltage %5.2f  current %6.3f" % (self.name, self.voltage, self.current), end='')
            sys.stdout.flush()

        def _report_voltage(value):
            self.voltage = value
            _print_values()

        def _report_current(value):
            self.current = value
            _print_values()

        self.hub.voltage.subscribe(_report_voltage, mode=Voltage.VOLTAGE_L, granularity=6)
        self.hub.current.subscribe(_report_current, mode=Current.CURRENT_L, granularity=15)

    def up_speed(self):
        self._bump_motor_power(1)
        self._set_headlight_brightness()

    def down_speed(self):
        self._bump_motor_power(-1)
        self._set_headlight_brightness()

    def stop(self):
        self.power_index = 0
        self.motor.power(param=0.)
        self._set_headlight_brightness()

    def _bump_motor_power(self, step):
        self.power_index = max(min(self.power_index + step, 10), -10)
        duty_cycle = self.motor_power.get_power(self.power_index)
        self.motor.power(param=duty_cycle)

    def _set_headlight_brightness(self):
        if self.headlight is not None:
            brightness = 10
            self._cancel_headlight_thread()
            if self.power_index != 0:
                brightness = 100
                self.headlight.set_brightness(brightness)
            else:
                # dim headlight after delay
                self.headlight_thread = Timer(10, self.headlight.set_brightness, [brightness])
                self.headlight_thread.start()

    def _cancel_headlight_thread(self):
        if self.headlight_thread is not None:
            self.headlight_thread.cancel()
            self.headlight_thread = None


class MotorPower:
    '''
    Translator between handset button clicks and actual motor power settings.

    The DC train motor seems to have some non-linearities in between its duty
    cycle (aka "power") and actual power, measured by its capacity to move the
    train at a given speed. This class translates the stepwise linear sequence
    of handset button presses to useful duty cycle values, using a lookup table.
    '''
    duty = {
        0: 0.0,  1: 0.3,  2: 0.35,  3: 0.4,  4: 0.45,  5: 0.5,
        6: 0.6,  7: 0.7,  8: 0.8,  9: 0.9, 10: 1.0,
        -1: -0.3, -2: -0.35, -3: -0.4, -4: -0.45, -5: -0.5,
        -6: -0.6, -7: -0.7,  -8: -0.8, -9: -0.9, -10: -1.0,
    }

    def get_power(self, index):
        return self.duty[index]

# default UUID address references the test hub
# train = SimpleTrain("Train 2", report=True)

# train hub allows control over the LED headlight.
train = SimpleTrain("Train 1", report=True, address='F88800F6-F39B-4FD2-AFAA-DD93DA2945A6')

# Correct startup sequence requires that the train hub be connected first.
# Wait a few seconds until the train hub connects. As soon as it connects, press
# the green button on the remote handset. As soon as it connects, the control
# loop starts running. Notice that the LEDs on both train and handset will go
# solid white, and won't change color (channel) by pressing the green button.
sleep(5)
handset = RemoteHandset(address='5D319849-7D59-4EBB-A561-0C37C5EF8DCD')  # train handset

# actions associated with each handset button
speed_actions = {
    RemoteButton.PLUS: train.up_speed,
    RemoteButton.RED: train.stop,
    RemoteButton.MINUS: train.down_speed
}

# handset callback handles most of the interactive logic associated with the buttons
def handset_callback(button, set):

    # for now, ignore the right side buttons, and all button release actions.
    # This will change when we implement support for a second train.
    if set == RemoteButton.RIGHT or button == RemoteButton.RELEASE:
        return

    # select action on train speed based on which button was pressed
    speed_actions[button]()


# we can either have one single callback and handle the button set choice in the
# callback, or have two separate callbacks, one associated with each button set
# from the start. Since we are handling two trains identically, each one on one
# side of the handset, the one-callback approach prevents code duplication.
handset.port_A.subscribe(handset_callback)
handset.port_B.subscribe(handset_callback)

# Dummy main execution thread. All actions take place in the event thread instead.
while True:
    pass

# since this is an infinite loop, we don't care about unsubscribing from anything

