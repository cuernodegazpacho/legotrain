import sys
from time import sleep
from threading import Thread, Timer, RLock

from pylgbst.hub import SmartHub
from pylgbst.peripherals import Voltage, Current, LEDLight
from pylgbst.peripherals import COLOR_BLUE, COLOR_RED, COLOR_YELLOW, COLOR_PURPLE, COLOR_ORANGE


class Train:
    '''
    Encapsulates details of a Train, such as motor power, led, sensor, headlight,
    voltage, current.

    The train LED can be set to any supported color. A different color can be used on
    each train initialization. This is useful for visually keeping track of multiple trains
    simultaneously moving on the track (the handset LED will remain white throughout).

    This class can report voltage and current at stdout.

    A thread lock mechanism is used to prevent collisions in the thread-unsafe
    pylgbst environment

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

        # global (per hub) lock to control threaded access to hub functions
        self.lock = RLock()

        # motor
        self.motor = self.hub.port_A
        self.motor_power = MotorHandler(self.motor, self.lock)
        self.power_index = 0

        # led
        self.led_handler = LEDHandler(self, self.lock)

        if report:
            self._start_reporting()

    def _start_reporting(self):
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

    # these speed controls are to be used by the controlling script
    # to respond to key presses in the handset
    def up_speed(self):
        self._bump_motor_power(1)

    def down_speed(self):
        self._bump_motor_power(-1)

    def stop(self):
        self.power_index = 0
        self._set_power()

    def _bump_motor_power(self, step):
        self.power_index = max(min(self.power_index + step, 10), -10)
        self._set_power()

    def _set_power(self):
        self.motor_power.set_motor_power(self.power_index)
        self.led_handler.set_status_led(self.power_index)


class MotorHandler:
    '''
    Translator between handset button clicks and actual motor power settings.

    The DC train motor appears to have a substantial non-linearities in between
    its duty cycle (aka "power") and actual power, measured by its capacity to move the
    train at a given speed. More evident at lower power settings. This class translates
    the stepwise linear sequence of handset button presses to duty cycle values that result
    in an apparent linear response from the train.
    '''
    duty = {
        0: 0.0,  1: 0.3,  2: 0.35,  3: 0.4,  4: 0.45,  5: 0.5,
        6: 0.6,  7: 0.7,  8: 0.8,  9: 0.9, 10: 1.0,
        -1: -0.3, -2: -0.35, -3: -0.4, -4: -0.45, -5: -0.5,
        -6: -0.6, -7: -0.7,  -8: -0.8, -9: -0.9, -10: -1.0,
    }

    def __init__(self, motor, lock):
        self.motor = motor
        self.lock = lock

    def set_motor_power(self, index):
        duty_cycle = self._get_power(index)
        self.lock.acquire()
        self.motor.power(param=duty_cycle)
        self.lock.release()

    def _get_power(self, index):
        return self.duty[index]


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

    # blinking should be fast to minimize latency is handset response time
    BLINK_TIME = 0.1 # seconds

    def __init__(self, train, lock):
        self.lock = lock
        self.led = train.hub.led
        self.led_color = train.led_color
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
        self.led_thread = Thread(target=self._swap_led_color, args=(self.led_color, COLOR_RED))
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
    from a flurry of unecessary messages. It also uses a lock to set hub parameters, preventing
    collisions in pylgbst.    '''
    def __init__(self, train, lock):
        self.lock = lock
        self.headlight = train.hub.port_B
        self.lock.acquire()
        self.headlight_brightness = self.headlight.brightness
        self.lock.release()

    # thread control
    headlight_timer = None

    def set_headlight_brightness(self, power_index):
        # here is the logic that prevents redundant BLE messages
        # to be sent to the train hub
        if self.headlight is not None:
            brightness = 10
            self._cancel_headlight_thread()

            if power_index != 0:
                brightness = 100
                if brightness != self.headlight_brightness:
                    self._set_brightness(brightness, self.lock)
                    self.headlight_brightness = brightness
            else:
                # dim headlight after delay
                if brightness != self.headlight_brightness:
                    self.headlight_timer = Timer(5, self._set_brightness, [brightness, self.lock])
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
