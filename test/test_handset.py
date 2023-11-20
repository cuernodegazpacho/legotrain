import logging
import time

from pylgbst.hub import RemoteHandset, MsgHubAttachedIO

logging.basicConfig(level=logging.DEBUG)


remote1 = RemoteHandset(address='C8DEE900-B1ED-F26B-7992-6DC06438ADB5')  # train handset
remote2 = RemoteHandset(address='CA1ADD7D-6619-B0DF-5D02-99B731959396')  # test handset

print(remote1)
print(remote2)

# def callback1(value):
#     print("Voltage granularity=4: %s", value)
# remote.voltage.subscribe(callback1, mode=Voltage.VOLTAGE_L, granularity=4)
# time.sleep(10)
# remote.voltage.unsubscribe(callback1)

# def demo_led_colors(remote):
#     # LED colors demo
#     print("LED colors demo")
#
#     # We get a response with payload and port, not x and y here...
#     def colour_callback(named):
#         print("LED Color callback: %s", named)
#
#     remote.led.subscribe(colour_callback)
#     for color in list(COLORS.keys())[1:] + [COLOR_BLACK, COLOR_GREEN]:
#         print("Setting LED color to: %s", COLORS[color])
#         remote.led.set_color(color)
#         time.sleep(1)
#
# demo_led_colors(remote)


def callback_from_button_1(button, button_set):
    print("value from callback (1): ", button, button_set)

def callback_from_button_2(button, button_set):
    print("value from callback (2): ", button, button_set)

remote1.port_A.subscribe(callback_from_button_1, mode=2)
remote1.port_B.subscribe(callback_from_button_1)
time.sleep(60)
remote1.port_A.unsubscribe(callback_from_button_1)
remote1.port_A.unsubscribe(callback_from_button_1)

remote2.port_A.subscribe(callback_from_button_2, mode=2)
remote2.port_B.subscribe(callback_from_button_2)
time.sleep(60)
remote2.port_A.unsubscribe(callback_from_button_2)
remote2.port_A.unsubscribe(callback_from_button_2)

