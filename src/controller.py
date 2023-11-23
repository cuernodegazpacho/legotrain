import time
from time import sleep

from pylgbst.hub import RemoteHandset
from pylgbst.peripherals import RemoteButton, COLOR_PURPLE

import uuid_definitions


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
        self.button = None
        self.set = None
        self.time = None

        sleep(5)
        self.handset = RemoteHandset(address=self.handset_address)

        # define sensible handset actions for a dummy train2 object
        if self.train2 is None:
            self.train2 = _DummyTrain()

        # actions associated with each handset button
        self.handset_actions = {
            RemoteButton.LEFT:
            {
                RemoteButton.PLUS: self.train1.up_speed,
                RemoteButton.RED: self._handle_red_button,
                RemoteButton.MINUS: self.train1.down_speed
            },
            RemoteButton.RIGHT:
            {
                RemoteButton.PLUS: self.train2.up_speed,
                RemoteButton.RED: self._handle_red_button,
                RemoteButton.MINUS: self.train2.down_speed
                # RemoteButton.PLUS: self.train1.switch_semaphore,
                # RemoteButton.RED: self.train1.switch_semaphore,
                # RemoteButton.MINUS: self.train1.switch_semaphore
            },
        }

    def connect(self):
        # Subscribe callbacks with train actions to handset button gestures.
        # We can either have one single callback and handle the button set choice in the
        # callback, or have two separate callbacks, one associated with each button set
        # from the start. Since we may be handling two trains identically, each one on one
        # side of the handset, the one-callback approach seems better at preventing code
        # duplication.
        self.handset.port_A.subscribe(self._handset_callback)
        self.handset.port_B.subscribe(self._handset_callback)

    # handset callback handles most of the interactive logic associated with the buttons
    def _handset_callback(self, button, set):

        # button release gesture clears memory of last gesture.
        # This results in no callback call, just a silent return.
        if self.button == RemoteButton.RELEASE:
            self.button = None
            self.set = None
            return

        # store values from most recent handset action
        self.button = button
        self.set = set
        self.time = None

        # select action on train speed based on which button was pressed
        self.handset_actions[self.set][self.button]()

    def _handle_red_button(self):

        #TODO compare timestamps to decide if it is a long red button press.

        if self.set == RemoteButton.LEFT:
            self.train1.stop()
        else:
            self.train2.stop()
