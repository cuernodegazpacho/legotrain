import logging
import time

from pylgbst.hub import RemoteHandset, RemoteButton, MsgHubAttachedIO

# logging.basicConfig(level=logging.DEBUG)


remote1 = RemoteHandset(address='CA1ADD7D-6619-B0DF-5D02-99B731959396')  # test handset
# time.sleep(4)
# remote2 = RemoteHandset(address='C8DEE900-B1ED-F26B-7992-6DC06438ADB5')  # train handset

print(remote1)
# print(remote2)

class HandsetEvent:
    def __init__(self, button, button_set):
        self.button = button
        self.button_set = button_set
        self.timestamp = time.time()


class HandsetHandler:
    def __init__(self, handset):
        self.handset = handset

        # self.buffer = []
        # helper variables for handling more complex gestures
        self.previous_red_event = None
        self.events_to_skip = 0

    def callback_from_button(self, button, button_set):
        # print("value from callback: ", button, button_set)

        if self.events_to_skip > 0:
            print(self.events_to_skip)
            self.events_to_skip -= 1
            return

        event = HandsetEvent(button, button_set)

        # if self.previous_red_event is not None:
        #     print("previous: ", self.previous_red_event, self.previous_red_event.button)
        #     print("current: ", event, event.button)
        # else:
        #     print("previous: None")
        #     print("current: ", event, event.button)

        # keep buffer small
        # if len(self.buffer) > 3:
        #     self.buffer.pop(0)

        # here we handle each one of the supported actions on
        # a RED button:
        # - single button quick press - RED and RELEASE with short time interval
        # - dual button simultaneous quick press - RED and RED with short time interval
        # - long press - RED and RELEASE with long time interval

        # if no valid previous event is know, store current event and
        # return without doing anything else
        if event.button in [RemoteButton.RED] and self.previous_red_event is None:
            self.previous_red_event = event
            return

        # got a RELEASE event. Compare timestamps with previous RED event
        # and take appropriate action
        if event.button in [RemoteButton.RELEASE]:
            d_timestamp = event.timestamp - self.previous_red_event.timestamp

            if d_timestamp < 1.:
                print("SHORT RED button press")
            else:
                print("LONG RED button press")

            return

        if event.button in [RemoteButton.RED]:
            d_timestamp = event.timestamp - self.previous_red_event.timestamp

            # current event becomes previous event
            self.previous_red_event = event

            if d_timestamp < 0.3:
                # the two RELEASE events associated with these two RED events
                # must be ignored. This forces the next two calls to this method
                # to be skipped.
                self.events_to_skip = 2

                print("DUAL RED button press")

            return




        # # store button actions of interest
        # if button in [RemoteButton.RED, RemoteButton.RELEASE]:
        #     self.buffer.append(event)
        #
        # # check that an event of interest happened
        # if len(self.buffer) > 3:
        #
        #     for e in self.buffer:
        #         print("element in buffer: ", e.button, e)
        #
        #
        #     for i in range(len(self.buffer)-1):
        #
        #         # retrieve properties of two consecutive events
        #         button_0 = self.buffer[i].button
        #         button_1 = self.buffer[i+1].button
        #         timestamp_0 = self.buffer[i].timestamp
        #         timestamp_1 = self.buffer[i+1].timestamp
        #
        #         # a double button press is indicated by two consecutive
        #         # appearances of the same button, with a minimal time
        #         # difference between the button presses.
        #         if button_0 is RemoteButton.RED and button_1 is RemoteButton.RED and \
        #             abs(timestamp_0 - timestamp_1) < 0.5:
        #             # print("Dual RED button press", self.handset)
        #             # self.buffer = []
        #             # while (len(self.buffer) > 0):
        #             #     a = self.buffer.pop()
        #             #     print("@@@  ", a)
        #             break
        #
        #         # a long button press is indicated by a button press followed by a
        #         # button release, with a significant time delay between them.
        #         elif button_0 is RemoteButton.RED and button_1 is RemoteButton.RELEASE and \
        #             abs(timestamp_0 - timestamp_1) > 2.:
        #             print("Long RED button press", self.handset)
        #             self.buffer = []
        #             print("initialize buffer")
        #             # while (len(self.buffer) > 0):
        #             #     self.buffer.pop()
        #             break
        #
        #         # fallback: responds to a short single press of either RED button
        #         elif button_0 is RemoteButton.RED and button_1 is RemoteButton.RELEASE:
        #             print("Single button press: ", button, self.handset)
        #             self.buffer = []
        #             print("initialize buffer")
        #         #     # while (len(self.buffer) > 0):
        #         #     #     self.buffer.pop()
        #             break
        #
        #     # Not a button that needs special handling. Just process it by
        #     # calling the controller method that process it.
        #     else:
        #         print("other type of button: ", button, button_set)
        #         self.buffer = []
        #         # self.controller.handset_actions[button_set][button]()


remote_handler_1 = HandsetHandler(remote1)
# remote_handler_2 = HandsetHandler(remote2)

remote_handler_1.handset.port_A.subscribe(remote_handler_1.callback_from_button, mode=2)
remote_handler_1.handset.port_B.subscribe(remote_handler_1.callback_from_button)
# remote_handler_2.handset.port_A.subscribe(remote_handler_2.callback_from_button, mode=2)
# remote_handler_2.handset.port_B.subscribe(remote_handler_2.callback_from_button)

time.sleep(120)

remote_handler_1.handset.port_A.unsubscribe(remote_handler_1.callback_from_button)
remote_handler_1.handset.port_B.unsubscribe(remote_handler_1.callback_from_button)
# remote_handler_2.handset.port_A.unsubscribe(remote_handler_2.callback_from_button)
# remote_handler_2.handset.port_B.unsubscribe(remote_handler_2.callback_from_button)

