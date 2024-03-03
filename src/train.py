import sys
import time, datetime
import random
from time import sleep
from threading import Thread, Timer, RLock
from colorsys import rgb_to_hsv

from pylgbst.hub import SmartHub
from pylgbst.peripherals import Voltage, Current, LEDLight
from pylgbst.peripherals import COLOR_BLUE, COLOR_ORANGE, COLOR_GREEN, COLOR_RED

import uuid_definitions
from track import CLOCKWISE, TIME_BLIND, MINIMUM_TIME_STATION, MAXIMUM_TIME_STATION
from track import sectors, station_sector_names, clear_track, DEFAULT_SPEED
from signal import INTER_SECTOR
from event import EventProcessor, DummyEventProcessor, SensorEventFilter
from signal import HUE, SATURATION, RGB_MINIMUM, V_MINIMUM
from signal import RED, GREEN, BLUE, YELLOW
from gui import tkinter_output_queue, tk_color, ASTATION, SECTOR

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

    This class can report voltage and current at stdout and the GUI. It can also record these
    measurements in a text file that is named as the train instance, with suffix ".txt". If a
    file of the same name already exists, it will be appended with data from the current run.

    A thread lock mechanism is used to prevent collisions in the thread-unsafe pylgbst
    environment. A per-hub lock is provided by default, a global lock can be provided by the
    caller when the need arises to synchronize among multiple instances of Train.

    :param name: train name, used in the report
    :param gui_id: str used by the GUI to direct report to appropriate field
    :param ncars: int number of cars; used to normalize speed settings
    :param lock: global lock used for threading access
    :param gui: instance of GUI, used to report status info
    :param led_color: primary LED color used in this train instance
    :param led_secondary_color: secondary LED color used to signal a stopped train
    :param report: if True, report voltage and current
    :param record: if True, record voltage and current in file (only if report=True)
    :param linear: if True, use motor's linear duty cycle curve
    :param address: UUID of the train's internal hub
    :param direction: direction of movement on the track
    '''
    def __init__(self, name, gui_id="0", ncars=2, lock=None, report=False, record=False, linear=False,
                 gui=None, led_color=COLOR_BLUE, led_secondary_color=COLOR_ORANGE,
                 direction=CLOCKWISE, address=uuid_definitions.HUB_TEST):

        self.name = name
        self.gui_id = gui_id
        self.ncars = ncars
        self.hub = SmartHub(address=address)
        self.current = 0.
        self.voltage = 0.
        self.led_color = led_color
        self.led_secondary_color = led_secondary_color
        self.astation = 0

        # dispatcher allows system-wide communications
        self.dispatcher = None

        # In this current implementation, these attributes are only used
        # by subclasses or events that should be aware of the sector
        # structure of the track.
        self.direction = direction

        # timer used for safety check, to prevent spurious end-of-sector detection.
        self.time_in_sector = None
        self.just_entered_sector = False
        # timer used for speed control
        self.speedup_timer = None
        # timer used to temporarily blind the train against signals
        self.signal_blind_timer = None
        self.signal_blind = False

        # another train instance can register here in order to receive
        # actions generated by this class.
        self.secondary_train = None

        # subclasses may want/need to implement event processing, such
        # as when dealing with sensors.
        self.event_processor = None

        # subclasses may implement automatic control modes (self-driving);
        # this flag can be used to toggle between that, and manual mode.
        self.auto = False

        # lock to control threaded access to hub functions
        self.lock = lock
        if self.lock is None:
            self.lock = RLock()

        # motor
        self.motor = self.hub.port_A
        self.motor_handler = MotorHandler(self.motor, self.ncars, self.lock, linear)
        self.power_index = 0

        # led control. Set initial status to current power index
        self.led_handler = LEDHandler(self, self.lock)
        self.led_handler.set_status_led(self.power_index)

        # Thread control: threads are used to hold the train at a
        # station for a timed interval, and to accelerate a train
        # gradually between two power settings.
        # These threads must be checked and eventually cancelled whenever
        # an up_speed, down_speed, or stop command is issued by either the
        # user or the controlling script.
        self.timer_station = None
        self.acceleration_thread = None
        self.stop_acceleration_thread = False

        # GUI access
        self.gui = gui
        if report:
            fp = None
            if record:
                fp = open(self.name + ".txt", "a")
            self._start_reporting(fp)

    def _start_reporting(self, fp):
        def _print_values():
            # print("\r%s  voltage %5.2f  current %5.2f  speed %i  power %4.2f" %
            #       (self.name, self.voltage, self.current, self.power_index, self.motor_handler.power), end='')
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

        self.hub.voltage.subscribe(_report_voltage, mode=Voltage.VOLTAGE_L, granularity=5)
        self.hub.current.subscribe(_report_current, mode=Current.CURRENT_L, granularity=7)

    def report_astation(self):
        # update GUI with @station value
        if self.gui is not None:
            output_buffer = self.gui.encode_int_variable(ASTATION, self.name, self.gui_id, self.astation)
            tkinter_output_queue.put(output_buffer)

    def report_sector(self, tkcolor, subtext=""):
        if self.gui is not None:
            output_buffer = self.gui.encode_str_variable(SECTOR, self.name, self.gui_id,
                                                         tkcolor, subtext=subtext)
            tkinter_output_queue.put(output_buffer)

    # up_speed and down_speed are used only by handset actions. They should
    # kill both the station wait and the accelerate threads; that way, the
    # state the train is after the user input is defined solely by that input.
    def up_speed(self):
        self._bump_motor_power(1)

    def down_speed(self):
        self._bump_motor_power(-1)

    def _bump_motor_power(self, step):
        self.cancel_station_timer()
        self.cancel_acceleration_thread()

        power_index = max(min(self.power_index + step, 10), -10)
        self.set_power(power_index)

    # stop is used by both handset and script in auto mode. It should behave like
    # up_speed and down_speed when activated by a handset call, but should not cancel
    # control threads when called by the script in auto mode.
    def stop(self, from_handset=True):
        if from_handset:
            self.cancel_station_timer()
            self.cancel_acceleration_thread()
            self.astation = 0
            self.report_astation()

        self.set_power(0, force_led_blink=True)

    def set_power(self, power_index, force_led_blink=False):
        self.power_index = power_index
        self.motor_handler.set_motor_power(self.power_index, self.voltage)
        self.led_handler.set_status_led(self.power_index, force_blink=force_led_blink)

    def cancel_station_timer(self):
        if self.timer_station is not None:
            self.timer_station.cancel()
            self.timer_station = None

    def cancel_acceleration_thread(self):
        if self.acceleration_thread is not None:
            self.stop_acceleration_thread = True
            self.acceleration_thread = None

    def cancel_speedup_timer(self):
        if self.speedup_timer is not None:
            self.speedup_timer.cancel()
            self.speedup_timer = None

    # The `accelerate` method has to be run in a thread, and stopped whenever a
    # set_power call takes place coming, typically, from the up_speed, dow_speed,
    # or stop methods initiated by either the user remote, or the controlling script
    # itself, as for instance in response from a sensor signal.
    def accelerate(self, power_index_values, power_index_signal, sleep_time=0.3):
        # if already running, stop it before starting a new acceleration ramp
        self.cancel_acceleration_thread()

        self.acceleration_thread = Thread(target=self._accelerate,
                                          args=(power_index_values,
                                                power_index_signal,
                                                sleep_time))
        self.stop_acceleration_thread = False
        self.acceleration_thread.start()

    def _accelerate(self, power_index_values, power_index_signal, sleep_time):
        for k in power_index_values:
            if self.stop_acceleration_thread:
                break
            self.set_power(k * power_index_signal)
            if self.secondary_train is not None:
                # secondary train runs in opposite direction as this train
                self.secondary_train.set_power(- k * power_index_signal)
            sleep(sleep_time)
        self.stop_acceleration_thread = False
        self.acceleration_thread = None


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
        1:  0.30, -1: -0.30,
        2:  0.42, -2: -0.42,
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

    # experimental correction for number of cars. The correction should
    # be unity for default number of cars (2), and decrease voltage with one
    # or zero cars.
    ncars_correction = [0.85, 0.92, 1.]

    def __init__(self, motor, ncars, lock, linear=False):
        self.motor = motor
        self.ncars = ncars
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
        voltage_corrected = self.voltage_slope * voltage + self.voltage_zero
        voltage_corrected *= self.ncars_correction[self.ncars]
        return (voltage_corrected)

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
    :param ncars: int number of cars; used to normalize speed settings
    :param lock: lock used for threading access
    :param gui: instance of GUI, used to report status info
    :param led_color: primary LED color used in this train instance
    :param led_secondary_color: secondary LED color used to signal a stopped train
    :param report: if True, report voltage and current
    :param record: if True, record voltage and current in file (only if report=True)
    :param linear: if True, use motor's linear duty cycle curve
    :param address: UUID of the train's internal hub
    :param direction: direction of movement on the track
    '''
    def __init__(self, name, gui_id="0", ncars=2, lock=None, report=False, record=False, linear=False,
                 gui=None, led_color=COLOR_BLUE, led_secondary_color=COLOR_ORANGE,
                 direction=CLOCKWISE,
                 address=uuid_definitions.HUB_TEST): # test hub

        super(SimpleTrain, self).__init__(name, gui_id, ncars=ncars, lock=lock,
                                          report=report, record=record, linear=linear,
                                          gui=gui, led_color=led_color,
                                          led_secondary_color=led_secondary_color,
                                          direction=direction,
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

    def stop(self, from_handset=True):
        super(SimpleTrain, self).stop(from_handset=from_handset)
        if self.headlight_handler is not None:
            self.headlight_handler.set_headlight_brightness(self.power_index)

    def set_power(self, power_index, force_led_blink=False):
        super(SimpleTrain, self).set_power(power_index, force_led_blink=force_led_blink)
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
    :param ncars: int number of cars; used to normalize speed settings
    :param lock: lock used for threading access
    :param gui: instance of GUI, used to report status info
    :param led_color: primary LED color used in this train instance
    :param led_secondary_color: secondary LED color used to signal a stopped train
    :param report: if True, report voltage and current
    :param record: if True, record voltage and current in file (only if report=True)
    :param linear: if True, use motor's linear duty cycle curve
    :param address: UUID of the train's internal hub
    :param direction: direction of movement on the track
    '''
    def __init__(self, name, gui_id="0", ncars=2, lock=None, report=False, record=False, linear=False,
                 gui=None, led_color=COLOR_BLUE, led_secondary_color=COLOR_ORANGE,
                 direction=CLOCKWISE, address=uuid_definitions.HUB_TEST): # test hub

        super(SmartTrain, self).__init__(name, gui_id, ncars=ncars, lock=lock,
                                         report=report, record=record, linear=linear,
                                          gui=gui, led_color=led_color,
                                          led_secondary_color=led_secondary_color,
                                          direction=direction,
                                          address=address)

        self.hub.vision_sensor.subscribe(self._vision_sensor_callback, granularity=4, mode=6)

        # events coming from the vision sensor need to be pre-processed in order
        # to filter out multiple detections, before being handled.
        self.sensor_event_filter = SensorEventFilter(self)
        self.event_processor = EventProcessor(self)
        # self.event_processor = DummyEventProcessor(self) # for debugging only

        self.initialize_sectors()
        clear_track()

    def initialize_sectors(self):
        '''
        When departing from a station, or when any situation requires a full
        reset, re-initialize train sector tracking. This means:
        1 - set current sector in train to None (train will formally be in the
            inter-sector zone)
        2 - set previous sector in train to the corresponding station
            sector from which it will depart.
        Note that the train will be put immediately in the state represented
        by this method, even though it is still stopped at the station, under
        control of the timing thread set by method timed_stop_at_station
        '''

        # assume train is departing from station; initialize its sector reference
        # to the inter-sector zone.
        self.sector = None
        self.previous_sector = sectors[station_sector_names[self.direction]]

        # train is initialized as if it were in the inter-sector zone right after
        # the station. To prevent confusion, we report sector as based instead on
        # the previous sector color.
        self.report_sector(tk_color[self.previous_sector.color])

    def timed_stop_at_station(self):
        # this only happens in auto mode
        if not self.auto:
            return

        self.cancel_station_timer()

        # start a timed wait interval at a station
        time_station = random.uniform(MINIMUM_TIME_STATION, MAXIMUM_TIME_STATION)
        self.timer_station = Timer(time_station, self.restart_movement)
        self.timer_station.start()

        self.astation = time_station
        self.report_astation()

    def restart_movement(self):
        self.astation = 0
        self.report_astation()

        # Check occupancy status of next sector. Note that restart_movement
        # is always called immediately *after* the train is internally set to
        # indicate it left a sector. Thus, train.sector was set to None, and
        # train.previous_sector was set to the sector the train is departing
        # from.
        self.led_handler.set_solid(COLOR_RED)
        next_sector = self.previous_sector.next[self.direction]
        while next_sector.occupier is not None and \
              next_sector.occupier != self.name:
            time.sleep(0.5)

        # immediately occupy next sector
        next_sector.occupier = self.name

        # train is departing from station, so gui displays inter-sector color
        self.report_sector(tk_color[INTER_SECTOR])

        self.led_handler.set_solid(COLOR_GREEN)
        if self.secondary_train is not None:
            self.secondary_train.led_handler.set_solid(COLOR_GREEN)
        sleep(1.0)

        # need to find out if this train is running forward or reverse
        # Cannot use self.power_index since it is set to zero when train is
        # stopped. We use the existence of a secondary train to figure
        # out the sense of movement.
        if self.secondary_train is None:
            power_index_signal = 1
        else:
            power_index_signal = -1

        # start timer to hold up the signal-blind flag. While this flag
        # is up, the vision sensor logic won't respond to signals. This
        # is used to prevent a false signal to be sensed when the train is
        # stopped right over a signal on the track. In that situation, as
        # soon as the movement starts, a false signal can be issued.
        self.signal_blind = True
        self.signal_blind_timer = Timer(TIME_BLIND, self.activate_signals)
        self.signal_blind_timer.start()

        # accelerate just to move train out of station area into inter-sector
        # zone. Train will regain full speed when crossing sector signal.
        self.accelerate(list(range(1, 4)), power_index_signal, sleep_time=0.5)

    def _vision_sensor_callback(self, *args, **kwargs):
        # use HSV as criterion for mapping colors
        r = args[0]
        g = args[1]
        b = args[2]
        h, s, v = rgb_to_hsv(r, g, b)

        if h >= 1. or h <= 0.:
            return

        # RED hue flips back to zero when crossing 1. We add 1. here
        # so the comparison logic downstream works.
        if h > 0. and h <= 0.05:
            h += 1.

        # ignore events with low signal-to-noise ratio
        if min(r, g, b) >= RGB_MINIMUM and v >= V_MINIMUM:

            # find matching color. Here we call the color detection criteria
            # in order of priority. That is, YELLOW is checked first, RED, last.
            # This is because the YELLOW signal needs faster response (train is
            # moving faster), and RED can wait a bit (train is moving slower). This
            # is related to one particular track layout tough. For other layouts,
            # maybe a different sequence would be better. We don't know if this is
            # relevant tough. It might have no importance whatsoever since the computer
            # should be much faster than the speed that events happen in the physical
            # train set.
            for color in [YELLOW, BLUE, GREEN, RED]:

                if (h >= HUE[color][0] and h <= HUE[color][1]) and \
                   (s >= SATURATION[color][0] and s <= SATURATION[color][1]):

                    self.sensor_event_filter.filter_event(color)
                    return

    # this method will set a flag that tells that it's safe now to get an
    # end-of-sector signal. The flag is managed by a timer and is used
    # to prevent spurious premature end-of-sector detections.
    def mark_exit_valid(self):
        self.just_entered_sector = False

    # make train sensitive to vison sensor signals
    def activate_signals(self):
        self.signal_blind = False

    def switch_semaphore(self):
        # this method is used only to debug the sector enter-exit logic.
        # It should be called by a handset right button when in 1-train
        # configuration. That way, pressing the button causes the sector
        # to open and close.
        if sectors[GREEN].occupier is None:
            sectors[GREEN].occupier = "AAAA"
            print("GREEN sector OCCUPIED")
        else:
            sectors[GREEN].occupier = None
            print("GREEN sector OPEN")



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

    def stop(self, from_handset=True):
        self.train_front.stop(from_handset=from_handset)
        self.train_rear.stop(from_handset=from_handset)


class LEDHandler:
    '''
    Handler for controlling the hub's LED. Current implementation blinks the LED
    when motor power is zero (train stopped).

    A Handler class is used to send/receive messages to/from a train hub, minimizing
    the number of actual Bluetooth messages. This helps in shielding the BLE environment
    from a flurry of unecessary messages. It also uses a lock to set hub parameters,
    preventing collisions in pylgbst.
    '''
    STATIC = 0
    BLINKING = 1

    # blinking should be fast to minimize latency in handset response time
    BLINK_TIME = 0.3 # seconds

    def __init__(self, train, lock):
        self.train = train
        self.lock = lock
        self.led = train.hub.led
        self.led_color = train.led_color
        self.led_secondary_color = train.led_secondary_color
        self.previous_power_index = 0

        # we require a quite complex thread control mechanism to implement
        # a blinking LED that starts with a delay when the motor stops. The
        # delay is necessary to minimize latency when operating train with
        # the handset buttons.
        self.led_thread = None
        self.delay_timer = None
        self.led_thread_stop_switch = False
        self.led_thread_is_running = False

        self.set_status_led(1)

    def set_solid(self, color):
        self._cancel_led_thread()
        self._cancel_delay_timer()

        self.lock.acquire()
        self.led.set_color(color)
        self.lock.release()

    def set_status_led(self, new_power_index, force_blink=False):
        # here is the logic that prevents redundant BLE messages to be sent to the train hub
        if (self._led_desired_mode(new_power_index) != self._led_desired_mode(self.previous_power_index)) \
                or force_blink:

            self._cancel_led_thread()
            self._cancel_delay_timer()

            if self._led_desired_mode(new_power_index) == self.STATIC:
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

    def _led_desired_mode(self, power_index):
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
