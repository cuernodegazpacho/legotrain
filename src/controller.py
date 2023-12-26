import time
from time import sleep

from pylgbst.hub import RemoteHandset
from pylgbst.peripherals import RemoteButton, COLOR_PURPLE

import uuid_definitions

DUAL = "dual"
LONG = "long"

# class that provides dummy methods to be used in case train2 is None
class _DummyTrain():
    def up_speed(self):
        return
    def stop(self):
        return
    def down_speed(self):
        return


class Controller:
    '''
    Main controller class.

    It accepts initialized instances of subclasses of Train.

    This class creates a remote handset instance that allows the operator to control one
    or two trains with one handset.
    '''
    def __init__(self, train1, train2=None, handset_address=uuid_definitions.HANDSET_TEST):
        self.train1 = train1
        self.train2 = train2
        self.handset_address = handset_address

        # these hold return values from a handset callback. The time
        # stamp is used to support a long button press gesture.
        # self.button = None
        # self.set = None
        # self.time = None

        sleep(5)
        self.handset = RemoteHandset(address=self.handset_address)
        self.handset_handler = HandsetHandler(self)

        # define sensible handset actions for a dummy train2 object
        if self.train2 is None:
            self.train2 = _DummyTrain()

        # actions associated with each handset button. Note that
        # the red buttons require special handling thus their
        # events are processed elsewhere.
        self.handset_actions = {
            RemoteButton.LEFT:
            {
                RemoteButton.PLUS: self.train1.up_speed,
                # RemoteButton.RED: self._handle_red_button,
                RemoteButton.MINUS: self.train1.down_speed
            },
            RemoteButton.RIGHT:
            {
                RemoteButton.PLUS: self.train2.up_speed,
                # RemoteButton.RED: self._handle_red_button,
                RemoteButton.MINUS: self.train2.down_speed
                # RemoteButton.PLUS: self.train1.switch_semaphore,
                # RemoteButton.RED: self.train1.switch_semaphore,
                # RemoteButton.MINUS: self.train1.switch_semaphore
            },
        }

        # actions associated with a short RED button press
        self.handset_short_red_actions = {
            RemoteButton.LEFT: self.train1.stop,
            RemoteButton.RIGHT: self.train2.stop
        }

        # actions associated with red buttons
        self.red_button_actions = {
            DUAL: self._restart,
            LONG: self._reset_all
        }

    def connect(self):
        # Subscribe callbacks with train actions to handset button gestures.
        # We can either have one single callback and handle the button set choice in the
        # callback, or have two separate callbacks, one associated with each button set
        # from the start. Since we may be handling two trains identically, each one on one
        # side of the handset, the one-callback approach seems better at preventing code
        # duplication.

        # self.handset.port_A.subscribe(self._handset_callback)
        # self.handset.port_B.subscribe(self._handset_callback)

        self.handset_handler.handset.port_A.subscribe(self.handset_handler.callback_from_button, mode=2)
        self.handset_handler.handset.port_B.subscribe(self.handset_handler.callback_from_button)

    # # handset callback handles most of the interactive logic associated with the buttons
    # #TODO move this to handset handler class
    # def _handset_callback(self, button, set):
    #
    #     # button release gesture clears memory of last gesture.
    #     # This results in no callback call, just a silent return.
    #     if self.button == RemoteButton.RELEASE:
    #         self.button = None
    #         self.set = None
    #         return
    #
    #     # store values from most recent handset action
    #     self.button = button
    #     self.set = set
    #     self.time = None
    #
    #     # select action on train speed based on which button was pressed
    #     self.handset_actions[self.set][self.button]()

    def _handle_red_button(self, mode):
        # mode can be "dual" or "long"
        self.red_button_actions[mode]()

    def _reset_all(self):
        self.train1.stop()
        self.train2.stop()

        #TODO reset track; reset trains, keep trains on manual mode; turn off signals

        print("RESET_ALL: Long RED button press")

    def _restart(self):
        #TODO turn on signals, start each train in turn

        print("RESTART: Dual RED button press")



class HandsetEvent:
    def __init__(self, button):
        self.button = button
        self.timestamp = time.time()


class HandsetHandler:
    def __init__(self, controller):
        self.handset = controller.handset
        self.controller = controller

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
                try:
                    button_0 = self.buffer[i].button
                    button_1 = self.buffer[i+1].button
                    timestamp_0 = self.buffer[i].timestamp
                    timestamp_1 = self.buffer[i+1].timestamp
                # get rid of harmless error message
                except IndexError:
                    pass

                # a double button press is indicated by two consecutive
                # appearances of the same button, with a minimal time
                # difference between the button presses.
                if button_0 is RemoteButton.RED and button_1 is RemoteButton.RED and \
                    abs(timestamp_0 - timestamp_1) < 0.5:
                    self.controller._handle_red_button(DUAL)
                    self.buffer = []
                    break

                # a long button press is indicated by a button press followed by a
                # button release, with a significant time delay between them.
                if button_0 is RemoteButton.RED and button_1 is RemoteButton.RELEASE and \
                    abs(timestamp_0 - timestamp_1) > 1.:
                    self.controller._handle_red_button(LONG)
                    self.buffer = []
                    break

                # short single press of either RED button should cause
                # a train stop.
                if button in [RemoteButton.RED]:
                    self.controller.handset_short_red_actions[button_set]()

        # Not a button that needs special handling. Just process it by
        # calling the controller method that process it.
        else:
            self.controller.handset_actions[button_set][button]()

