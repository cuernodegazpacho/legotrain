import time
from time import sleep
from threading import Timer

from signal import RED, GREEN, BLUE, YELLOW
from track import StructuredSector, FAST, SLOW, sectors


TIME_THRESHOLD = 0.4 # seconds

# Vision sensor colorimetry parameters.
# TODO preliminary values taken from colorimetry analysis
HUE = {}
SATURATION = {}

RGB_LIMIT = 10.0
V_LIMIT = 23.0

HUE[RED]    = (0.90, 1.00)  # min and max hue for red
HUE[GREEN]  = (0.37, 0.54)
HUE[BLUE]   = (0.58, 0.63)
HUE[YELLOW] = (0.66, 0.72)

SATURATION[RED]    = (0.52, 0.82)  # min and max saturation for red
SATURATION[GREEN]  = (0.20, 0.59)
SATURATION[BLUE]   = (0.56, 0.76)
SATURATION[YELLOW] = (0.40, 0.51)

sign = lambda x: x and (1, -1)[x<0]


class SensorEventFilter():
    '''
    This class is used to filter out multiple detections of the same color
    by the vision sensor in a SmartTrain.

    It works by ignoring all detections of the given color that take place
    within a pre-defined time interval. The first event will be passed back
    to the caller, an instance of SmartTrain, via its process_event method.
    '''

    events = {}

    def __init__(self, train):
        '''
        
        :param train: an instance of SmartTrain
        '''
        self.train = train

    def filter_event(self, event_key):
        # events are discriminated by their color. If an event of a given
        # color is already stored here, it means that this current event is
        # possibly a double detection. Verify by checking event times.
        event_time = time.time()
        if event_key in self.events:
            if (event_time - self.events[event_key]) > TIME_THRESHOLD:
                # not a double detection. Alert caller and
                # redefine stored event
                self.events[event_key] = event_time
                self.train.event_processor.process_event(event_key)

            else:
                # double detection. Do nothing.
                pass

        # if event of current color is not stored here, store current event
        else:
            self.events[event_key] = event_time
            self.train.event_processor.process_event(event_key)


class EventProcessor:
    '''
    Delegate class that handles everything associated with sensor
    events in a SmartTrain instance.
    '''
    def __init__(self, train):
        '''

        :param train: an instance of SmartTrain
        '''
        self.train = train

    def process_event(self, event):
        '''
        Processes events pre-filtered by SensorEventFilter.

        This method contains the logic for stopping/starting the
        train at sector end points based on the occupied/free
        status of a sector.

        TODO this badly needs refactoring. A conditional-plagued
        code is not conducive to a modular, scalable design.
        '''

        # events should be processed only when in auto mode
        if not self.train.auto:
            return

        # red signal means stop at station

        # RED events are reserved for handling sectors that contain a
        # train stop (station). As such, they require a specialized logic
        # that differs from the logic applied to regular track sectors.
        if event in [RED]:

            self.train.check_acceleration_thread()

            sleep(0.01)
            self.train.stop()

            # make sure previous sector is released.
            self.train.previous_sector.occupier = None

            # mark current sector as occupied. Note that this is not
            # strictly required in the current implementation, but we
            # do it anyway for debugging and logging purposes.
            self.train.previous_sector.next[self.train.direction].occupier = self.train.name

            # after stopping at station, execute a Timer delay followed by a re-start
            self.train.timed_stop_at_station()

            # if a secondary train instance is registered, call its stop
            # method. But *do not* call its timed delay routine, since this
            # functionality must be commanded by the current train only.
            if self.train.secondary_train is not None:
                self.train.secondary_train.stop()

            # when departing from station, re-initialize train sector tracking.
            # This means:
            # 1 - set current sector in train to None (train will be in inter-sector zone)
            # 2 - set previous sector in train to the corresponding station
            #     sector from which it will depart.
            # Note that the train will be put immediately in the state represented
            # by method initialize_sectors, even though it is still stopped at the
            # station, under control of the timing thread set by method timed_stop_at_station
            # above.
            self.train.initialize_sectors()

        elif event in [YELLOW, BLUE]:
            # if the most recent signal event has a color identical to the
            # sector color where the train is right now, this means the train
            # detected either the sector end signal, or the FAST-SLOW transition
            # point in the current (structured) sector.

            # print("")
            # print("-----------------DBG block ---------------------------------")
            # print("self.train.name: ", self.train.name)
            # print("event: ", event)
            # print("self.train.sector: ", self.train.sector)
            # if self.train.sector is not None:
            #     print("self.train.sector.color: ", self.train.sector.color)
            # print("self.train.just_entered_sector: ", self.train.just_entered_sector)
            # print("---------------END DBG block ---------------------------------")
            # print("")

            if self.train.sector is not None and \
                    self.train.sector.color is not None and \
                    self.train.sector.color == event and \
                    not self.train.just_entered_sector:

                if isinstance(self.train.sector, StructuredSector):

                    next_sector = self.train.sector.next[self.train.direction]

                    if  self.train.sector.sub_sector_type == FAST:

                        # leaving FAST sub-sector and entering SLOW
                        self.train.sector.sub_sector_type = SLOW

                        # Decision on how to behave from now on depends on the
                        # occupancy status of the next sector ahead of train.
                        # Train should slow down and eventually stop only if
                        # next sector is occupied. Otherwise, grab next sector.
                        if next_sector.occupier is not None and \
                           next_sector.occupier != self.train.name:
                            # occupied: slow down and wait for end-of-sector signal.
                            self._slowdown()
                        else:
                            # next sector is free. Grab it.
                            next_sector.occupier = self.train.name

                    else:
                        # leaving SLOW sub-sector, thus leaving the entire sector as well.
                        # Either do a full stop-and-wait, or keep going, based on occupancy
                        # status of next sector
                        if next_sector.occupier is not None and \
                           next_sector.occupier != self.train.name:
                            # occupied: stop and keep interrogating next sector
                            self._stop_and_wait(next_sector)
                        else:
                            # next sector is free: exit current sector
                            # and keep moving TODO at normal speed
                            self._exit_sector(event)

                # YELLOW sector precedes a station stop for both clockwise and counter-clockwise
                # directions. It also signals entry in an inter-sector zone.
                if event in [YELLOW] and not isinstance(self.train.sector, StructuredSector):
                    self._slowdown()
                    self._exit_sector(event)

            elif self.train.sector is None:
                # train is moving from inter-sector zone into new sector
                self.train.sector = self.train.previous_sector.next[self.train.direction]

                # structured segments start with a FAST sub-sector
                if isinstance(self.train.sector, StructuredSector):
                    self.train.sector.sub_sector_type = FAST

                # lock sector. This was probably handled somewhere else, before
                # the train had taken the decision to enter the sector. But we do
                # it again here just in case.
                self.train.sector.occupier = self.train.name

                # make sure previous sector is released.
                self.train.previous_sector.occupier = None

                # set up timer for sanity check to prevent false detections
                # of a spurious end-of-sector signal
                sector_time =self.train.sector.sector_time
                self.train.time_in_sector = Timer(sector_time, self.train.mark_exit_valid)
                self.train.just_entered_sector = True
                self.train.time_in_sector.start()

                # when entering sector, set timed speedup
                if self.train.speedup_timer is not None:
                    self.train.speedup_timer.cancel()
                self.train.speedup_timer = Timer(self.train.sector.max_speed_time,
                                                 self.train.return_to_default_speed)
                self.train.speedup_timer.start()
                self.train.accelerate(list(range(self.train.power_index, self.train.sector.max_speed + 1)), 1)

            else:
                pass
                print("ERROR: detected spurious signal inside sector")

    def _exit_sector(self, event):
        self.train.previous_sector = self.train.sector

        # entering inter-sector zone
        self.train.sector = None

    def _slowdown(self):
        # the train might be moving backwards, so first we generate
        # a positive representation of the current power index (the
        # `accelerate` method will handle the actual sense of movement
        # for the new speed values).
        current_power_index_value = self.train.power_index * sign(self.train.power_index)
        # generate downward sequence of power index values. In this case,
        # we want to go all the way down to speed 1, thus we use zero for
        # the new index (it's being generated by a `range` call)
        new_power_index_value = 0
        power_index_step = -1
        power_index_range = list(range(current_power_index_value,
                                       new_power_index_value,
                                       power_index_step))
        # a sequence of 6 deceleration steps has 5 sleeping intervals. It
        # is executed in approx. 1 sec. Normalize so it takes about the
        # same time regardless of current speed.
        sleep_time = current_power_index_value / len(power_index_range) * 0.15
        # sleep_time = current_power_index_value / len(power_index_range) * 0.1  # TODO test for fast stop (2-car = 0.1, 1-car = 0.05)
        # sleep_time *= current_power_index_value / current_power_index_value
        # sleep_time *= 1.1  # fudge factor

        self.train.accelerate(power_index_range, sign(self.train.power_index), sleep_time=sleep_time)

    def _stop_and_wait(self, next_sector):
        self.train.stop()

        # make sure we wait for the next sector to go free. This
        # may be redundant here, since train.restart_movement should
        # be doing the same check anyway. We do just in case though.
        while next_sector.occupier is not None and \
              next_sector.occupier != self.train.name:
            time.sleep(0.5)

        self._exit_sector("from stop and wait")
        self.train.restart_movement()


    def _debug(self, msg):
        print("----------------- SECTORS STATUS ---------------------------------")
        print(msg)
        for key in sectors:
            print("Sector: ", sectors[key].color, "   occupier: ", sectors[key].occupier)
        print("----------------- END SECTORS STATUS ---------------------------------")
        print("")


class DummyEventProcessor(EventProcessor):
    '''
    Testing / debug
    '''

    def process_event(self, event):
        print("Event: ", event)

