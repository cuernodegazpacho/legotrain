import time, datetime
from time import sleep
from threading import Thread

from pylgbst.hub import RemoteHandset
from pylgbst.peripherals import RemoteButton

import uuid_definitions

import track
import signal
from train import SmartTrain, CompoundTrain

DUAL = "dual"
LONG = "long"


class Controller:
    '''
    Main controller class.

    It accepts initialized instances of subclasses of Train.

    This class creates a remote handset instance that allows the operator to
    control one or two trains with one handset. Optionally, it can add a
    second handset to control a third train.

    The class was last used to control two instances of SmartTrain in a
    self-driving setup. Other configurations (such as CompoundTrain) may
    not work without some additional work).

    '''
    def __init__(self, train1, train2=None, train3=None,
                 handset_address=uuid_definitions.HANDSET_ORIG,
                 handset2_address=None):
        self.train1 = train1
        self.train2 = train2
        self.train3 = train3
        # define sensible handset actions for a dummy train object
        if self.train2 is None:
            self.train2 = _DummyTrain("Dummy")
        if self.train3 is None:
            self.train3 = _DummyTrain("Dummy")

        # when using a second handset, we need yet another dummy train to
        # receive dummy commands from the right button set on the second
        # handset. This might be the place to add additional controls such
        # as for motorized switches.
        self.train4 = _DummyTrain("place holder")

        # sleep(5)
        self.handset = RemoteHandset(address=handset_address)
        self.handset_handler = HandsetHandler(self, self.handset)

        if handset2_address is not None:
            # sleep(5)
            self.handset2 = RemoteHandset(address=handset2_address)
            self.handset2_handler = HandsetHandler(self, self.handset2, second=True)
        else:
            self.handset2 = None
            self.handset2_handler = None

        # Subscribe callbacks with train actions to handset button gestures.
        # We can either have one single callback and handle the button set choice
        # in the callback, or have two separate callbacks, one associated with
        # each button set from the start. Since we may be handling two trains
        # identically, each one on one side of the handset, the one-callback
        # approach seems better at preventing code duplication.
        self.handset_handler.handset.port_A.subscribe(self.handset_handler.callback_from_button)
        self.handset_handler.handset.port_B.subscribe(self.handset_handler.callback_from_button)
        if self.handset2_handler is not None:
            self.handset2_handler.handset.port_A.subscribe(self.handset2_handler.callback_from_button)
            self.handset2_handler.handset.port_B.subscribe(self.handset2_handler.callback_from_button)

        # enable system-wide communications
        self.dispatcher = Dispatcher(self)
        self.train1.dispatcher = self.dispatcher
        self.train2.dispatcher = self.dispatcher
        self.train3.dispatcher = self.dispatcher


    # def connect_handset(self):
    #     # Subscribe callbacks with train actions to handset button gestures.
    #     # We can either have one single callback and handle the button set choice
    #     # in the callback, or have two separate callbacks, one associated with
    #     # each button set from the start. Since we may be handling two trains
    #     # identically, each one on one side of the handset, the one-callback
    #     # approach seems better at preventing code duplication.
    #     self.handset_handler.handset.port_A.subscribe(self.handset_handler.callback_from_button)
    #     self.handset_handler.handset.port_B.subscribe(self.handset_handler.callback_from_button)

    def reset_all(self):
        self.train1.stop()
        self.train2.stop()
        self.train3.stop()

        self.dispatcher.stop()

        track.clear_track()

        #TODO this is begging for a refactor

        # both trains should be conducted in manual mode from now on
        if isinstance(self.train1, SmartTrain) and (isinstance(self.train2, SmartTrain) or
                isinstance(self.train2, _DummyTrain)) and (isinstance(self.train3, SmartTrain) or
                isinstance(self.train3, _DummyTrain)):
            self.train1.auto = False
            self.train2.auto = False
            self.train3.auto = False

            self.train1.cancel_all_threads()
            self.train2.cancel_all_threads()
            self.train3.cancel_all_threads()

            self.train1.initialize_sectors()
            self.train2.initialize_sectors()
            self.train3.initialize_sectors()

            if track.xtrack is not None:
                track.xtrack.initialize(self.train1)
                track.xtrack.initialize(self.train2)
                track.xtrack.initialize(self.train3)

        # reset mode for configuration with compound train
        if isinstance(self.train1, CompoundTrain):
            self.train1.train_rear.auto = False
            self.train1.train_rear.cancel_all_threads()

            self.train1.train_rear.initialize_sectors()

            if track.xtrack is not None:
                track.xtrack.initialize(self.train1.train_rear)

    def _restart(self):
        # this method assumes the train(s) is(are) stopped at its(their) designated
        # station(s), after manual mode was entered, and it(they) was(were) driven
        # manually to there.

        track.clear_track()

        #TODO this is begging for a refactor

        # restart mode for configuration with two smart trains
        if isinstance(self.train1, SmartTrain) and (isinstance(self.train2, SmartTrain) or
                isinstance(self.train2, _DummyTrain)) and (isinstance(self.train3, SmartTrain) or
                isinstance(self.train3, _DummyTrain)):
            self.train1.auto = True
            self.train2.auto = True
            self.train3.auto = True

            self.train1.initialize_sectors()
            self.train2.initialize_sectors()
            self.train3.initialize_sectors()

            # override random time generator to force trains to start in a pre-defined
            # sequence. This is necessary because train3 is departing not from a station
            # (on a 2-station track layout), but from an inter-sector region. It has to
            # start first in order to immediately occupy the sector ahead. We used this as
            # well to help in debugging the 3-train configuration.
            self.train1.timed_stop_at_station(time_to_wait=10)
            time.sleep(0.5)
            self.train2.timed_stop_at_station(time_to_wait=20)
            time.sleep(0.5)
            self.train3.timed_stop_at_station(time_to_wait=1)

        # restart mode for configuration with compound train
        if isinstance(self.train1, CompoundTrain):
            self.train1.train_rear.auto = True
            self.train1.train_rear.initialize_sectors()
            self.train1.train_rear.timed_stop_at_station()

        # dispatcher will detect and solve stuck train situations
        self.dispatcher.start_stuck_thread()

class HandsetEvent:
    def __init__(self, button):
        self.button = button
        self.timestamp = time.time()


class HandsetHandler:
    def __init__(self, controller, handset, second=False):
        self.handset = handset
        self.controller = controller
        self.second = second

        # helper variables for handling more complex gestures
        self.previous_red_event = HandsetEvent(RemoteButton.RED)
        self.previous_event = HandsetEvent(RemoteButton.RELEASE)
        self.events_to_skip = 0

        # actions associated with each handset button.
        # Note that the red buttons require special handling,
        # thus their associated events are processed elsewhere.
        # 'second' tells that the handler is associated with the
        # second handset in a 3-train setup.
        train1 = self.controller.train1
        train2 = self.controller.train2
        if self.second:
            train1 = self.controller.train3
            train2 = self.controller.train4

        self.handset_actions = {
            RemoteButton.LEFT:
                {
                    RemoteButton.PLUS: train1.up_speed,
                    RemoteButton.MINUS: train1.down_speed
                },
            RemoteButton.RIGHT:
                {
                    RemoteButton.PLUS: train2.up_speed,
                    RemoteButton.MINUS: train2.down_speed
                    # TODO
                    # RemoteButton.PLUS: self.controller.train1.switch_semaphore,
                    # RemoteButton.RED: self.controller.train1.switch_semaphore,
                    # RemoteButton.MINUS: self.controller.train1.switch_semaphore
                },
        }

        # actions associated with a short RED button press
        self.handset_short_red_actions = {
            RemoteButton.LEFT: train1.stop,
            RemoteButton.RIGHT: train2.stop
        }

        # actions associated with long and dual red button actions
        self.red_button_actions = {
            DUAL: self.controller._restart,
            LONG: self.controller.reset_all
        }

    def _handle_red_button(self, mode):
        # mode can be "dual" or "long"
        self.red_button_actions[mode]()

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

        # store all non-RELEASE events, so we can know after wards if a given RELEASE
        # event is associated with a previous RED event, or to another key event.
        if event.button not in [RemoteButton.RELEASE]:
            self.previous_event = event

        # got a RELEASE event. Compare timestamps with previous RED event
        # and take appropriate action
        if event.button in [RemoteButton.RELEASE] and self.previous_event.button in [RemoteButton.RED]:
            d_timestamp = event.timestamp - self.previous_red_event.timestamp

            if d_timestamp < 1.:
                self.handset_short_red_actions[button_set]()
            else:
                self._handle_red_button(LONG)

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
                self._handle_red_button(DUAL)

            return

        # Not a button that needs special handling. Just process it by
        # calling the controller method that process it.
        else:
            if button not in [RemoteButton.RELEASE]:
                self.handset_actions[button_set][button]()


class Dispatcher:
    '''
    The dispatcher enables and handles communications and actions to take place
    system-wide. For instance, conditions in one of the trains may need to be
    broadcast to other trains in the system; the dispatcher should be the way to
    do this. The class exists to provide some degree of decoupling and isolation
    among the trains themselves, and the trains and controller.

    In this version, we use the dispatcher to untangle a lock situation that
    appears on 3-train setups. Sometimes the 3 trains may be stuck with closed
    sectors in front all of them. The dispatcher finds that situation by periodically
    quering the status of each train. When it finds that the 3 trains are stopped
    in a red-signal situation (it queries their LED status light), it overrides the
    'occupied' status of specific sector in front one of the trains. This is dependent
    on the specific layout, and should be generalized.
    '''
    def __init__(self, controller):
        self.controller = controller

        self.start_stuck_thread()

    def start_stuck_thread(self):
        self._stop = False
        self.stuck_thread = Thread(target=self._query_train_stuck)
        self.stuck_thread.start()

    def _query_train_stuck(self):
        while(1):
            # to break from the thread
            if self._stop:
                break

            # check train status, and free them
            if self.controller.train1.is_stuck() & \
               self.controller.train2.is_stuck() & \
               self.controller.train3.is_stuck():

                # unblock sector TODO this depends on the particular track layout
                track.sectors[signal.BLUE].occupier = None

            sleep(3.0)

    def stop(self):
        self._stop = True

    def emergency_stop(self):
        self.controller.reset_all()


# class that provides dummy methods to be used in case train2 is None
class _DummyTrain():
    def __init__(self, name):
        self.name = name
        self.gui = None
    def up_speed(self):
        return
    def stop(self):
        return
    def down_speed(self):
        return
    def initialize_sectors(self):
        return
    def timed_stop_at_station(self, time_to_wait=None):
        return
    def cancel_all_threads(self):
        return
    def is_stuck(self):
        return False


# testing the Dispatcher class
if __name__ == '__main__':

    dispatcher = Dispatcher(None)
    sleep(15)
    dispatcher.stop()

