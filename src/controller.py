import time
from time import sleep

from pylgbst.hub import RemoteHandset
from pylgbst.peripherals import RemoteButton

import uuid_definitions

import track
from train import SmartTrain

DUAL = "dual"
LONG = "long"


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

        # Subscribe callbacks with train actions to handset button gestures.
        # We can either have one single callback and handle the button set choice
        # in the callback, or have two separate callbacks, one associated with
        # each button set from the start. Since we may be handling two trains
        # identically, each one on one side of the handset, the one-callback
        # approach seems better at preventing code duplication.
        self.handset_handler.handset.port_A.subscribe(self.handset_handler.callback_from_button)
        self.handset_handler.handset.port_B.subscribe(self.handset_handler.callback_from_button)

        # define sensible handset actions for a dummy train2 object
        if self.train2 is None:
            self.train2 = _DummyTrain()

        # enable system-wide communications
        self.dispatcher = Dispatcher(self)
        self.train1.dispatcher = self.dispatcher
        self.train2.dispatcher = self.dispatcher

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
            LONG: self.reset_all
        }

    # def connect_handset(self):
    #     # Subscribe callbacks with train actions to handset button gestures.
    #     # We can either have one single callback and handle the button set choice
    #     # in the callback, or have two separate callbacks, one associated with
    #     # each button set from the start. Since we may be handling two trains
    #     # identically, each one on one side of the handset, the one-callback
    #     # approach seems better at preventing code duplication.
    #     self.handset_handler.handset.port_A.subscribe(self.handset_handler.callback_from_button)
    #     self.handset_handler.handset.port_B.subscribe(self.handset_handler.callback_from_button)

    def _handle_red_button(self, mode):
        # mode can be "dual" or "long"
        self.red_button_actions[mode]()

    def reset_all(self):
        self.train1.stop()
        self.train2.stop()

        # both trains should be conducted in manual mode from now on
        if isinstance(self.train1, SmartTrain) and (isinstance(self.train2, SmartTrain) or
                isinstance(self.train2, _DummyTrain)):
            self.train1.auto = False
            self.train2.auto = False

            self.train1.initialize_sectors()
            self.train2.initialize_sectors()

    def _restart(self):
        # this method assumes the trains are stopped at they designated stations,
        # after manual mode was entered, and they were driven manually to there.

        track.clear_track()

        if isinstance(self.train1, SmartTrain) and (isinstance(self.train2, SmartTrain) or
                isinstance(self.train2, _DummyTrain)):
            self.train1.auto = True
            self.train2.auto = True

            self.train1.initialize_sectors()
            self.train2.initialize_sectors()

            self.train1.timed_stop_at_station()
            time.sleep(0.5)
            self.train2.timed_stop_at_station()



class HandsetEvent:
    def __init__(self, button):
        self.button = button
        self.timestamp = time.time()


class HandsetHandler:
    def __init__(self, controller):
        self.handset = controller.handset
        self.controller = controller

        # helper variables for handling more complex gestures
        self.previous_red_event = HandsetEvent(RemoteButton.RED)
        self.previous_event = HandsetEvent(RemoteButton.RELEASE)
        self.events_to_skip = 0

    def callback_from_button(self, button, button_set):

        if self.events_to_skip > 0:
            self.events_to_skip -= 1
            return

        event = HandsetEvent(button)

        # here we handle each one of the supported actions on
        # a RED button:
        # - single button quick press - RED and RELEASE with short time interval
        # - dual button simultaneous quick press - RED and RED with short time interval
        # - long press - RED and RELEASE with long time interval

        # if no valid previous RED event is know, store current RED event and
        # return without doing anything else
        if event.button in [RemoteButton.RED] and self.previous_red_event is None:
            self.previous_red_event = event
            return

        # store all non-RELEASE events, so we can know afterwards if a given RELEASE
        # event is associated with a previous RED event, or to another key event.
        if event.button not in [RemoteButton.RELEASE]:
            self.previous_event = event

        # got a RELEASE event. Compare timestamps with previous RED event
        # and take appropriate action
        if event.button in [RemoteButton.RELEASE] and self.previous_event.button in [RemoteButton.RED]:
            d_timestamp = event.timestamp - self.previous_red_event.timestamp

            if d_timestamp < 1.:
                self.controller.handset_short_red_actions[button_set]()
            else:
                self.controller._handle_red_button(LONG)

            return

        if event.button in [RemoteButton.RED]:
            d_timestamp = event.timestamp - self.previous_red_event.timestamp

            # current event becomes previous event
            self.previous_red_event = event

            if d_timestamp < 0.3:
                # the two RELEASE events associated with these two RED events
                # must be ignored. We force the next two calls to this method
                # to be skipped.
                self.events_to_skip = 2
                self.controller._handle_red_button(DUAL)

            return

        # Not a button that needs special handling. Just process it by
        # calling the controller method that process it.
        else:
            if button not in [RemoteButton.RELEASE]:
                self.controller.handset_actions[button_set][button]()


class Dispatcher:
    '''
    The dispatcher enables and handles communications and actions to take place
    system-wide. For instance, conditions in one of the trains may need to be
    broadcast to other trains in the system; the dispatcher should be the way to
    do this. The class exists to provide some degree of decoupling and isolation
    among the trains themselves, and the trains and controller.
    '''
    def __init__(self, controller):
        self.controller = controller

    def emergency_stop(self):
        self.controller.reset_all()


# class that provides dummy methods to be used in case train2 is None
class _DummyTrain():
    def up_speed(self):
        return
    def stop(self):
        return
    def down_speed(self):
        return
    def initialize_sectors(self):
        return
    def timed_stop_at_station(self):
        return

