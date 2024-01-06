import time
from time import sleep

from pylgbst.hub import RemoteHandset
from pylgbst.peripherals import RemoteButton

import uuid_definitions

import track
from train import SmartTrain

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

    This class creates a remote handset instance that allows the operator to
    control one or two trains with one handset.

    The class was last used to control two instances of SmartTrain in a
    self-driving setup. Other configurations (such as CompoundTrain) may
    not work without some additional work).

    '''
    def __init__(self, train1, train2=None, handset_address=uuid_definitions.HANDSET_TEST):
        self.train1 = train1
        self.train2 = train2
        self.handset_address = handset_address

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
                RemoteButton.MINUS: self.train1.down_speed
            },
            RemoteButton.RIGHT:
            {
                RemoteButton.PLUS: self.train2.up_speed,
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

        # actions associated with long and dual red button actions
        self.red_button_actions = {
            DUAL: self._restart,
            LONG: self._reset_all
        }

    def connect(self):
        # Subscribe callbacks with train actions to handset button gestures.
        # We can either have one single callback and handle the button set choice
        # in the callback, or have two separate callbacks, one associated with
        # each button set from the start. Since we may be handling two trains
        # identically, each one on one side of the handset, the one-callback
        # approach seems better at preventing code duplication.
        self.handset_handler.handset.port_A.subscribe(self.handset_handler.callback_from_button, mode=2)
        self.handset_handler.handset.port_B.subscribe(self.handset_handler.callback_from_button)

    def _handle_red_button(self, mode):
        # mode can be "dual" or "long"
        self.red_button_actions[mode]()

    def _reset_all(self):
        self.train1.stop()
        self.train2.stop()

        # both trains should be conducted from now on just in manual mode
        if isinstance(self.train1, SmartTrain) and isinstance(self.train2, SmartTrain):
            self.train1.auto = False
            self.train2.auto = False

            self.train1.initialize_sectors()
            self.train2.initialize_sectors()

    def _restart(self):
        # this method assumes the trains are stopped at they designated stations,
        # after manual mode was entered, and they were driven manually to there.

        track.clear_track()

        if isinstance(self.train1, SmartTrain) and isinstance(self.train2, SmartTrain):
            self.train1.auto = True
            self.train2.auto = True

            self.train1.initialize_sectors()
            self.train2.initialize_sectors()

            self.train1.timed_stop_at_station()
            # time.sleep(1.0)
            self.train2.timed_stop_at_station()



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

                # fallback: responds to a short single press of either RED button
                if button in [RemoteButton.RED]:
                    self.controller.handset_short_red_actions[button_set]()

        # Not a button that needs special handling. Just process it by
        # calling the controller method that process it.
        else:
            self.controller.handset_actions[button_set][button]()

