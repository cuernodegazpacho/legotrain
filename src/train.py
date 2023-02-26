import sys
import time
from time import sleep
from threading import Thread, Timer

import pylgbst.peripherals as peripherals
from pylgbst.peripherals import COLOR_BLUE, COLOR_RED, Voltage, Current
from pylgbst.hub import SmartHub
from pylgbst.peripherals import Voltage, Current, LEDLight


class Train:
    '''
    Encapsulates details of a Train, such as motor power, led, sensor, headlight,
    voltage, current.

    The train LED can be set to any color. A different color can be used on each
    train initialization. This is useful for visually keeping track of two trains
    simultaneously moving on the track (the handset LED will remain white throughout).

    This class reports voltage and current at stdout.

    :param name: train name, used in the report
    :param led_color: primary LED color used in this train instance
    :param report: if True, report voltage and current
    :param address: UUID of the train's internal hub

    :ivar hub: the train's internal hub
    :ivar motor: references the train's motor
    :ivar power_index: motor power level
    :ivar voltage: populated only when report=True
    :ivar current: populated only when report=True
    :ivar led_color: LED color, defined at init time
    '''
    def __init__(self, name, report=False, led_color=COLOR_BLUE,
                 address='86996732-BF5A-433D-AACE-5611D4C6271D'): # test hub by default

        self.name = name
        self.hub = SmartHub(address=address)
        self.current = 0.
        self.voltage = 0.
        self.led_color = led_color

        # motor
        self.power_index = 0
        self.motor_power = MotorPower()
        self.motor = self.hub.port_A

        # led
        self.set_status_led()

        # threads
        # self.led_thread = None
        # self.led_thread_run = False

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
        # self.set_status_led()

    def down_speed(self):
        self._bump_motor_power(-1)
        # self.set_status_led()

    def stop(self):
        self.power_index = 0
        self.motor.power(param=0.)
        # self.set_status_led()

    def _bump_motor_power(self, step):
        self.power_index = max(min(self.power_index + step, 10), -10)
        duty_cycle = self.motor_power.get_power(self.power_index)
        self.motor.power(param=duty_cycle)

    def set_status_led(self):
        self.hub.led.set_color(self.led_color)


        # self._cancel_led_thread()

        # if self.power_index != 0:
        #     try:
        #         self.hub.led.set_color(self.led_color)
        #     except AssertionError as e:
        #         # TODO eventually supress error message after some more testing
        #         print("Harmless error when setting LED:", e)
        # else:
        #     self.led_thread = Thread(target=self._swap_led_color, args=(self.led_color, COLOR_RED))
        #     self.led_thread_run = True
        #     self.led_thread.start()

    # def _swap_led_color(self, c1, c2):
    #     while self.led_thread_run:
    #         try:
    #             self.hub.led.set_color(c2)
    #             sleep(1)
    #             self.hub.led.set_color(c1)
    #             sleep(1)
    #         except AssertionError as e:
    #             # TODO eventually supress error message after some more testing
    #             print("harmless error when blinking LED:", e)

    # def _cancel_led_thread(self):
    #     if self.led_thread is not None:
    #         self.led_thread_run = False
    #         self.led_thread = None
    #         sleep(0.3)


class SimpleTrain(Train):
    '''
    A SimpleTrain is a Train *not* equipped with a sensor. It may or may not have a
    headlight. If it does, the headlight brightness is controlled by the motor power
    setting. A SimpleTrain without a headlight behaves as a Train.

    Current behavior calls for the headlight to be at maximum brightness for all motor
    power settings, except for zero power. In that case, the brightness is dropped to
    10% of maximum. This value is set in the headlight after a few seconds delay from
    the moment the motor stops. Details of this are handled by an instance of class
    HeadlightHamdler.

    :param name: train name, used in the report
    :param led_color: primary LED color used in this train instance
    :param report: if True, report voltage and current
    :param address: UUID of the train's internal hub

    :ivar hub: the train's internal hub
    :ivar headlight: reference to the hub's port B device
    :ivar headlight_brightness: reference to the hub `headlight.brightness` value
    '''
    def __init__(self, name, report=False, led_color=COLOR_BLUE,
                 address='86996732-BF5A-433D-AACE-5611D4C6271D'): # test hub

        super(SimpleTrain, self).__init__(name, report=report, led_color=led_color, address=address)

        self.headlight = None

        if isinstance(self.hub.port_B, LEDLight):
            self.headlight = self.hub.port_B
            self.headlight_brightness = self.headlight.brightness

    def up_speed(self):
        super(SimpleTrain, self).up_speed()
        self._set_headlight_brightness()

    def down_speed(self):
        super(SimpleTrain, self).down_speed()
        self._set_headlight_brightness()

    def stop(self):
        super(SimpleTrain, self).stop()
        self._set_headlight_brightness()


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


class HeadlightHandler:
    '''
    A Handler class is used to send/receive messages to/from a train hub, minimizing
    the number of actual Bluetooth messages. This helps in shielding the BT environment
    from a flurry of unecessary messages.
    '''


    # thread control
    headlight_thread = None

    def _set_headlight_brightness(self):
        if self.headlight is not None:
            brightness = 10
            self._cancel_headlight_thread()
            if self.power_index != 0:
                brightness = 100
                self.headlight.set_brightness(brightness)
            else:
                # dim headlight after delay
                self.headlight_thread = Timer(5, self.headlight.set_brightness, [brightness])
                self.headlight_thread.start()

    def _cancel_headlight_thread(self):
        if self.headlight_thread is not None:
            self.headlight_thread.cancel()
            self.headlight_thread = None
            sleep(0.2)



