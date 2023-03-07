from time import sleep
from threading import Thread
from pylgbst.peripherals import RemoteButton, COLOR_BLUE, COLOR_RED
from pylgbst.hub import SmartHub, RemoteHandset


def swap_led_color(led, c1, c2):
    while True:
        sleep(1)
        led.set_color(c1)
        sleep(1)
        led.set_color(c2)

hub = SmartHub(address='F88800F6-F39B-4FD2-AFAA-DD93DA2945A6')
motor = hub.port_A

def plus():
    print("blinking_led_test.py 18:  plus button pressed")
    motor.power(param=0.3)
def minus():
    print("blinking_led_test.py 21:  minus button pressed")
    motor.power(param=-0.3)
def red():
    print("blinking_led_test.py 24:  red button pressed")
    motor.power(param=0)

handset = RemoteHandset(address='5D319849-7D59-4EBB-A561-0C37C5EF8DCD')

button_actions = {
    RemoteButton.PLUS: plus,
    RemoteButton.RED: red,
    RemoteButton.MINUS: minus
}

def handset_callback(button, set):
    if set == RemoteButton.RIGHT or button == RemoteButton.RELEASE:
        return

    button_actions[button]()

handset.port_A.subscribe(handset_callback)
handset.port_B.subscribe(handset_callback)

led_thread = Thread(target=swap_led_color, args=(hub.led, COLOR_BLUE, COLOR_RED))
led_thread.start()

