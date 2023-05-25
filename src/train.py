import sys
import datetime
import random
from time import sleep
from threading import Thread, Timer, RLock
from colorsys import rgb_to_hsv

from pylgbst.hub import SmartHub
from pylgbst.peripherals import Voltage, Current, LEDLight
from pylgbst.peripherals import COLOR_BLUE, COLOR_ORANGE, COLOR_GREEN

import track
from event import SensorEventFilter, RED_EVENT, LB_EVENT
from gui import tkinter_output_queue

sign = lambda x: x and (1, -1)[x<0]


class Train:
    '''
    Encapsulates details of a Train, such as motor power, led, vision sensor, headlight,
    voltage, current.

    The hub LED can be set to any supported color. A different color can be used on
    each train initialization. This is useful for visually keeping track of multiple trains
    simultaneously moving on the track (the handset LED will remain white throughout). The
    LED will blink between the chosen color and a secondary color, whenever the motor power
    is set to zero (train is stopped). The original blinking with red color signaling low
    battery remains unchanged.

    This class can report voltage and current at stdout. It can also record these measurements
    in a text file that is named as the train instance, with suffix ".txt". If a file of the
    same name already exists, it will be appended with data from the current run.

    A thread lock mechanism is used to prevent collisions in the thread-unsafe pylgbst
    environment. A per-hub lock is provided by default, a global lock can be provided by the
    caller when the need arises to synchronize among multiple instances of Train.

    :param name: train name, used in the report
    :param gui_id: str used by the GUI to direct report to appropriate field
    :param lock: global lock used for threading access
    :param gui: instance of GUI, used to report status info
    :param led_color: primary LED color used in this train instance
    :param led_secondary_color: secondary LED color used to signal a stopped train
    :param report: if True, report voltage and current
    :param record: if True, record voltage and current in file (only if report=True)
    :param linear: if True, use motor's linear duty cycle curve
    :param address: UUID of the train's internal hub
    '''
    def __init__(self, name, gui_id="0", lock=None, report=False, record=False, linear=False,
                 gui=None, led_color=COLOR_BLUE, led_secondary_color=COLOR_ORANGE,
                 address='86996732-BF5A-433D-AACE-5611D4C6271D'): # test hub by default

        self.name = name
        self.gui_id = gui_id
        self.hub = SmartHub(address=address)
        self.current = 0.
        self.voltage = 0.
        self.led_color = led_color
        self.led_secondary_color = led_secondary_color

        # lock to control threaded access to hub functions
        self.lock = lock
        if self.lock is None:
            self.lock = RLock()

        # motor
        self.motor = self.hub.port_A
        self.motor_handler = MotorHandler(self.motor, self.lock, linear)
        self.power_index = 0

        # led
        self.led_handler = LEDHandler(self, self.lock)

        # this is a timer thread used to hold the train at a station for a
        # given amount of time. This thread must be checked and eventually
        # cancelled whenever a up_speed, down_speed, or stop command is
        # issued by either the user or the controlling script. It is not
        # used by the base class.
        self.timer_station = None

        self.gui = gui
        if report:
            fp = None
            if record:
                fp = open(self.name + ".txt", "a")
            self._start_reporting(fp)

    def _start_reporting(self, fp):
        def _print_values():
            print("\r%s  voltage %5.2f  current %5.2f  speed %i  power %4.2f" %
                  (self.name, self.voltage, self.current, self.power_index, self.motor_handler.power), end='')
            sys.stdout.flush()
            if fp is not None:
                ct = datetime.datetime.now()
                fp.write("\r%s  %s   voltage: %5.2f  current: %5.3f  speed: %i  power %4.2f" %
                         (self.name, ct, self.voltage, self.current, self.power_index, self.motor_handler.power))
                fp.flush()
            if self.gui is not None and self.gui_id != "0":
                # use gui-specific code to encode variables. Actual data passing must
                # be done via a queue, since tkinter is not thread-safe and can't be
                # updated directly from here.
                output_buffer = self.gui.encode_basic_variables(self.name, self.gui_id, self.voltage,
                                                                self.current, self.power_index,
                                                                self.motor_handler.power)
                tkinter_output_queue.put(output_buffer)

        def _report_voltage(value):
            self.voltage = value
            _print_values()

        def _report_current(value):
            self.current = value
            _print_values()

        self.hub.voltage.subscribe(_report_voltage, mode=Voltage.VOLTAGE_L, granularity=20)
        self.hub.current.subscribe(_report_current, mode=Current.CURRENT_L, granularity=20)

    # In the most basic application, these speed controls are to be used
    # by the controlling script to respond to key presses in the handset.
    def up_speed(self):
        self._bump_motor_power(1)

    def down_speed(self):
        self._bump_motor_power(-1)

    def stop(self):
        self.set_power(0)

    def _bump_motor_power(self, step):
        power_index = max(min(self.power_index + step, 10), -10)
        self.set_power(power_index)

    def set_power(self, power_index):
        self._check_timer_station()
        self.power_index = power_index
        self.motor_handler.set_motor_power(self.power_index, self.voltage)
        self.led_handler.set_status_led(self.power_index)

    def _check_timer_station(self):
        if self.timer_station is not None:
            self.timer_station.cancel()
            self.timer_station = None
            self.led_handler.set_solid(self.led_color)

class MotorHandler:
    '''
    Translator between handset button clicks and actual motor power settings.

    The DC train motor has a substantial non-linearity in between its duty cycle
    (aka "power") and actual power, measured by its capacity to move the train at
    a given speed. More evident at lower power settings. This class translates the
    stepwise linear sequence of handset button presses to duty cycle values that
    result in a more linearized response from the train.

    A correction factor related to the battery voltage drop that happens during
    use is also handled by this class.
    '''
    NOMINAL_VOLTAGE = 8.3  # Volts (6 AAA Ni-MH batteries in hub)
    MINIMUM_VOLTAGE = 6.0
    MAXIMUM_FACTOR = 1.40  # minimum factor is 1., corresponding to fresh batteries

    # non-linear duty cycle, appropriate for a heavy train
    duty = {
        0:  0.0,
        1:  0.35, -1: -0.35,
        2:  0.43, -2: -0.43,
        3:  0.48, -3: -0.48,
        4:  0.52, -4: -0.52,
        5:  0.56, -5: -0.56,
        6:  0.6,  -6: -0.6,
        7:  0.7,  -7: -0.7,
        8:  0.8,  -8: -0.8,
        9:  0.9,  -9: -0.9,
       10:  1.0, -10: -1.0,
    }

    # linear duty cycle, appropriate for a light test rig
    duty_linear = {
        0:  0.0,
        1:  0.1,  -1: -0.1,
        2:  0.2,  -2: -0.2,
        3:  0.3,  -3: -0.3,
        4:  0.4,  -4: -0.4,
        5:  0.5,  -5: -0.5,
        6:  0.6,  -6: -0.6,
        7:  0.7,  -7: -0.7,
        8:  0.8,  -8: -0.8,
        9:  0.9,  -9: -0.9,
       10:  1.0, -10: -1.0,
    }

    def __init__(self, motor, lock, linear=False):
        self.motor = motor
        self.power = 0.
        self.lock = lock
        self.linear = linear

        # linear voltage correction
        self.voltage_slope = (self.MAXIMUM_FACTOR - 1.0) / (self.MINIMUM_VOLTAGE - self.NOMINAL_VOLTAGE)
        self.voltage_zero = 1.0  - self.voltage_slope * self.NOMINAL_VOLTAGE

    def set_motor_power(self, index, voltage):
        power = self._compute_power(index, voltage)
        self.lock.acquire()
        self.motor.power(param=power)
        self.lock.release()
        self.power = power

    def _compute_power(self, index, voltage):
        duty = self.duty[index]
        if self.linear:
            duty =  self.duty_linear[index]
        power = min(duty * self._voltage_correcion(voltage), 1.)
        return power

    # compute power correction factor based on voltage drop from nominal value
    def _voltage_correcion(self, voltage):
        return self.voltage_slope * voltage + self.voltage_zero

    @property
    def get_power(self):
        return self.power


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
    :param gui_id: str used by the GUI to direct report to appropriate field
    :param lock: lock used for threading access
    :param gui: instance of GUI, used to report status info
    :param led_color: primary LED color used in this train instance
    :param led_secondary_color: secondary LED color used to signal a stopped train
    :param report: if True, report voltage and current
    :param record: if True, record voltage and current in file (only if report=True)
    :param linear: if True, use motor's linear duty cycle curve
    :param address: UUID of the train's internal hub
    '''
    def __init__(self, name, gui_id="0", lock=None, report=False, record=False, linear=False,
                 gui=None, led_color=COLOR_BLUE, led_secondary_color=COLOR_ORANGE,
                 address='86996732-BF5A-433D-AACE-5611D4C6271D'): # test hub

        super(SimpleTrain, self).__init__(name, gui_id, lock, report=report, record=record, linear=linear,
                                          gui=gui, led_color=led_color,
                                          led_secondary_color=led_secondary_color,
                                          address=address)

        self.headlight_handler = None

        if isinstance(self.hub.port_B, LEDLight):
            self.headlight_handler = HeadlightHandler(self, self.lock)

    # in the methods that increase or decrease motor power, one has to
    # always call the headlight brightness control, since the power can
    # go from some given setting to zero by either pressing the plus/minus
    # buttons, or the red button. The headlight handler sorts out between
    # these cases and only issues an actual command to the headlight when
    # needed. This minimizes BLE traffic.
    def up_speed(self):
        super(SimpleTrain, self).up_speed()
        if self.headlight_handler is not None:
            self.headlight_handler.set_headlight_brightness(self.power_index)

    def down_speed(self):
        super(SimpleTrain, self).down_speed()
        if self.headlight_handler is not None:
            self.headlight_handler.set_headlight_brightness(self.power_index)

    def stop(self):
        super(SimpleTrain, self).stop()
        if self.headlight_handler is not None:
            self.headlight_handler.set_headlight_brightness(self.power_index)

    def set_power(self, power_index):
        super(SimpleTrain, self).set_power(power_index)
        if self.headlight_handler is not None:
            self.headlight_handler.set_headlight_brightness(self.power_index)


class SmartTrain(Train):
    '''
    A SmartTrain is a Train equipped with a color/distance sensor pointing downwards.

    Since a sensor and a headlight cannot coexist (hub has only 2 ports), this class
    can inherit straight from Train.

    A SmartTRain must be able to propagate its sensor-driven actions to other trains that
    are registered with it.

    :param name: train name, used in the report
    :param gui_id: str used by the GUI to direct report to appropriate field
    :param lock: lock used for threading access
    :param gui: instance of GUI, used to report status info
    :param led_color: primary LED color used in this train instance
    :param led_secondary_color: secondary LED color used to signal a stopped train
    :param report: if True, report voltage and current
    :param record: if True, record voltage and current in file (only if report=True)
    :param linear: if True, use motor's linear duty cycle curve
    :param address: UUID of the train's internal hub
    '''
    def __init__(self, name, gui_id="0", lock=None, report=False, record=False, linear=False,
                 gui=None, led_color=COLOR_BLUE, led_secondary_color=COLOR_ORANGE,
                 address='86996732-BF5A-433D-AACE-5611D4C6271D'): # test hub

        super(SmartTrain, self).__init__(name, gui_id, lock, report=report, record=record, linear=linear,
                                          gui=gui, led_color=led_color,
                                          led_secondary_color=led_secondary_color,
                                          address=address)

        self.hub.vision_sensor.subscribe(self._vision_sensor_callback, granularity=5, mode=6)

        # another train instance can register here in order to receive
        # actions generated by this class.
        self.secondary_train = None

        # events coming from the vision sensor need to be pre-processed in order
        # to filter out multiple detections.
        self.sensor_event_filter = SensorEventFilter(self)

    def process_event(self, event):
        '''
        Processes events pre-filtered by SensorEventFilter
        '''
        # red signal means stop at station
        if event in ["RED"]:

            action = track.segments[event]

            sleep(0.01)
            self.stop()

            # after stopping at station, execute a Timer delay followed by a re-start
            self.timed_stop_at_station()

            # if a secondary train instance is registered, call its stop
            # method. But *do not* call its timed delay routine, since this
            # functionality must be commanded by the current train only.
            if self.secondary_train is not None:
                self.secondary_train.stop()

        # light blue signal causes power to be dropped to level 1
        elif event in ["LIGHT BLUE"]:
            new_power_index = 1
            new_power_index = new_power_index * sign(self.power_index)
            self.set_power(new_power_index)

            # if a train instance is registered, call its set_power method.
            # Note that it's power index must be reversed.
            if self.secondary_train is not None:
                self.secondary_train.set_power(-new_power_index)

    # start a timed wait interval at a station, and
    # handle the hub's LED behavior.
    def timed_stop_at_station(self):
        time_station = random.uniform(10., 30.)
        self.timer_station = Timer(time_station, self.restart_from_station)
        self.timer_station.start()

    def restart_from_station(self):
        self.led_handler.set_solid(COLOR_GREEN)
        if self.secondary_train is not None:
            self.secondary_train.led_handler.set_solid(COLOR_GREEN)
        sleep(3)

        # need to find out if this train is running forward or reverse
        # Cannot use self.power_index since it is set to zero when train is
        # stopped. We use the existence of a secondary train to figure
        # out the sense of movement.
        if self.secondary_train is None:
            power_index_signal = 1
        else:
            power_index_signal = -1

        # the acceleration sequence below is somewhat dependent on the fact
        # that an instance of SmartTrain is going to be used as the back
        # (rear facing) engine in a CompoundTrain object.
        # TODO A more generic solution is desirable here.
        for k in range(1,7):
            self.set_power(k * power_index_signal)
            if self.secondary_train is not None:
                # secondary train runs in opposite direction as this train
                self.secondary_train.set_power(- k * power_index_signal)
            sleep(0.5)

    def _vision_sensor_callback(self, *args, **kwargs):
        # use HSV as criterion for mapping colors
        r = args[0]
        g = args[1]
        b = args[2]
        h, s, v = rgb_to_hsv(r, g, b)

        if h >= 1. or h <= 0.:
            return

        if min(r, g, b) > 10.0 and v > 20.0:
            bg = b / g
            gr = g / r

            #TODO these values are still preliminary and require a lot of testing

            if (h > 0.90 or h < 0.05) and (s > 0.55 and s < 0.82):
                # print(args, kwargs, h, s, v, bg, gr, "RED")
                # print("RED")
                self.sensor_event_filter.filter_event(RED_EVENT)

            #TODO use most recent values from colorimetry notebook
            if (h > 0.55 and h < 0.63) and (s > 0.50 and s < 0.73):
                print("\n", args, kwargs, h, s, v, bg, gr, "LIGHT BLUE")
                # print("LIGHT BLUE")
                self.sensor_event_filter.filter_event(LB_EVENT)

            if (h > 0.40 and h < 0.60) and (s > 0.25 and s < 0.60):
                print("\n", args, kwargs, h, s, v, bg, gr, "GREEN")
                # print("GREEN")

            if (h > 0.15 and h < 0.30) and (s > 0.23 and s < 0.55):
                print("\n", args, kwargs, h, s, v, bg, gr, "LIGHT GREEN")
                # print("LIGHT GREEN")


class CompoundTrain():
    '''
    A CompoundTrain is a compound entity that encapsulates two instances of Train:
    a front engine, and a rear engine running backwards. The front engine is an instance
    of SimpleTrain (because the headlight must be at the front) and the rear engine is an
    instance of SmartTrain (to carry the vision sensor).

    We use a delegation approach instead of subclassing due to the complex interactions
    that take place in a compound train with two reversed engines.

    :param name: name of the compound train
    :param train_front: instance of SingleTrain
    :param train_rear: instance of SmartTrain
    '''
    def __init__(self, name, train_front, train_rear):
        self.name = name
        self.train_front = train_front
        self.train_rear = train_rear

        # the rear train passes its sensor-derived actions
        # to the front train via its secondary_train reference.
        self.train_rear.secondary_train = self.train_front

    # train_rear must move backwards
    def up_speed(self):
        self.train_rear.down_speed()
        self.train_front.up_speed()

    def down_speed(self):
        self.train_front.down_speed()
        self.train_rear.up_speed()

    def stop(self):
        self.train_front.stop()
        self.train_rear.stop()


class LEDHandler:
    '''
    Handler for controlling the hub's LED. Current implementation blinks the LED
    when motor power is zero (train stopped).

    A Handler class is used to send/receive messages to/from a train hub, minimizing
    the number of actual Bluetooth messages. This helps in shielding the BLE environment
    from a flurry of unecessary messages. It also uses a lock to set hub parameters, preventing
    collisions in pylgbst.
    '''
    STATIC = 0
    BLINKING = 1

    # blinking should be fast to minimize latency in handset response time
    BLINK_TIME = 0.1 # seconds

    def __init__(self, train, lock):
        self.lock = lock
        self.led = train.hub.led
        self.led_color = train.led_color
        self.led_secondary_color = train.led_secondary_color
        self.previous_power_index = 0

        # we require a quite complex thread control mechanism to implement
        # a blinking LED that starts with a delay when the motor stops. The
        # delay is necessary to minimize latency when operating train with
        # the headset buttons.
        self.led_thread = None
        self.delay_timer = None
        self.led_thread_stop_switch = False
        self.led_thread_is_running = False

        self.set_status_led(1)

    def set_solid(self, color):
        self._cancel_led_thread()
        self._cancel_delay_timer()
        self.led.set_color(color)

    def set_status_led(self, new_power_index):
        # here is the logic that prevents redundant BLE messages to be sent to the train hub
        if self._led_desired_status(new_power_index) != self._led_desired_status(self.previous_power_index):
            self._cancel_led_thread()
            self._cancel_delay_timer()

            if self._led_desired_status(new_power_index) == self.STATIC:
                self.lock.acquire()
                self.led.set_color(self.led_color)
                self.lock.release()
            else: # BLINKING
                self.delay_timer = Timer(2., self._start_led_thread, [])
                self.delay_timer.start()

            self.previous_power_index = new_power_index

    def _start_led_thread(self):
        self.led_thread = Thread(target=self._swap_led_color, args=(self.led_color, self.led_secondary_color))
        self.led_thread_stop_switch = False
        self.led_thread_is_running = True
        self.led_thread.start()

    def _led_desired_status(self, power_index):
        return self.BLINKING if power_index == 0 else self.STATIC

    def _swap_led_color(self, c1, c2):
        while not self.led_thread_stop_switch:
            self.lock.acquire()
            self.led.set_color(c1)
            self.lock.release()
            sleep(self.BLINK_TIME)
            self.lock.acquire()
            self.led.set_color(c2)
            self.lock.release()
            sleep(self.BLINK_TIME)

        self.led_thread_is_running = False

    def _cancel_led_thread(self):
        if self.led_thread is not None:
            self.led_thread_stop_switch = True
            while self.led_thread_is_running:
                sleep(self.BLINK_TIME / 10)
            self.led_thread = None

    def _cancel_delay_timer(self):
        if self.delay_timer is not None:
            self.delay_timer.cancel()
            self.delay_timer = None


class HeadlightHandler:
    '''
    Handler for controlling the headlight. Current implementation dims the headlight after
    a few seconds have elapsed since the motor stopped. When motor starts, the headlight is
    set back to maximum brightness.

    A Handler class is used to send/receive messages to/from a train hub, minimizing
    the number of actual Bluetooth messages. This helps in shielding the BLE environment
    from a flurry of unecessary messages. It also uses a lock to set hub parameters,
    preventing collisions in pylgbst.
    '''
    def __init__(self, train, lock):
        self.lock = lock
        self.headlight = train.hub.port_B
        self.lock.acquire()
        self.headlight_brightness = self.headlight.brightness
        self.lock.release()

    # thread control
    headlight_timer = None

    def set_headlight_brightness(self, power_index):
        # here is the logic that prevents redundant BLE
        # messages to be sent to the train hub
        if self.headlight is not None:
            brightness = 10

            if power_index != 0:
                brightness = 100
                if brightness != self.headlight_brightness:
                    self._cancel_headlight_thread()
                    self._set_brightness(brightness, self.lock)
                    self.headlight_brightness = brightness
            else:
                # dim headlight after delay
                if brightness != self.headlight_brightness:
                    self._cancel_headlight_thread()
                    self.headlight_timer = Timer(3, self._set_brightness, [brightness, self.lock])
                    self.headlight_timer.start()
                    self.headlight_brightness = brightness

    # wrapper to allow locking
    def _set_brightness(self, brightness, lock):
        lock.acquire()
        self.headlight.set_brightness(brightness)
        lock.release()

    def _cancel_headlight_thread(self):
        if self.headlight_timer is not None:
            self.headlight_timer.cancel()
            self.headlight_timer = None
            sleep(0.1)
