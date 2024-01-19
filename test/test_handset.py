import logging
import time

from pylgbst.hub import RemoteHandset, RemoteButton, MsgHubAttachedIO

# logging.basicConfig(level=logging.DEBUG)


remote1 = RemoteHandset(address='CA1ADD7D-6619-B0DF-5D02-99B731959396')  # test handset
time.sleep(4)
remote2 = RemoteHandset(address='C8DEE900-B1ED-F26B-7992-6DC06438ADB5')  # train handset

print(remote1)
print(remote2)

class HandsetEvent:
    def __init__(self, button):
        self.button = button
        self.timestamp = time.time()


class HandsetHandler:
    def __init__(self, handset):
        self.handset = handset

        self.buffer = []

    def callback_from_button(self, button, button_set):
        print("value from callback: ", button, button_set)

        event = HandsetEvent(button)

        # keep buffer small
        if len(self.buffer) > 3:
            self.buffer.pop(0)

        # store button actions of interest
        if button in [RemoteButton.RED, RemoteButton.RELEASE]:
            self.buffer.append(event)

        # check that an event of interest happened
        for i in range(len(self.buffer)-1):

            # retrieve properties of two consecutive events
            button_0 = self.buffer[i].button
            button_1 = self.buffer[i+1].button
            timestamp_0 = self.buffer[i].timestamp
            timestamp_1 = self.buffer[i+1].timestamp

            # a double button press is indicated by two consecutive
            # appearances of the same button, with a minimal time
            # difference between the button presses.
            if button_0 is RemoteButton.RED and button_1 is RemoteButton.RED and \
                abs(timestamp_0 - timestamp_1) < 0.5:
                print("Dual RED button press", self.handset)
                self.buffer = []

            # a long button press is indicated by a button press followed by a
            # button release, with a significant time delay between them.
            if button_0 is RemoteButton.RED and button_1 is RemoteButton.RELEASE and \
                abs(timestamp_0 - timestamp_1) > 2.:
                print("Long RED button press", self.handset)
                self.buffer = []

            # fall thru


remote_handler_1 = HandsetHandler(remote1)
remote_handler_2 = HandsetHandler(remote2)

remote_handler_1.handset.port_A.subscribe(remote_handler_1.callback_from_button, mode=2)
remote_handler_1.handset.port_B.subscribe(remote_handler_1.callback_from_button)
remote_handler_2.handset.port_A.subscribe(remote_handler_2.callback_from_button, mode=2)
remote_handler_2.handset.port_B.subscribe(remote_handler_2.callback_from_button)

time.sleep(60)

remote_handler_1.handset.port_A.unsubscribe(remote_handler_1.callback_from_button)
remote_handler_1.handset.port_B.unsubscribe(remote_handler_1.callback_from_button)
remote_handler_2.handset.port_A.unsubscribe(remote_handler_2.callback_from_button)
remote_handler_2.handset.port_B.unsubscribe(remote_handler_2.callback_from_button)

