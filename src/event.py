import time
from time import sleep

from signal import RED, GREEN, BLUE, YELLOW
from track import StructuredSector, FAST, SLOW


TIME_THRESHOLD = 0.6 # seconds

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
SATURATION[YELLOW] = (0.41, 0.51)

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
        '''
        # red signal means stop at station

        print("Event:  ", event)

        # RED events are reserved for handling sectors that contain a
        # train stop (station). As such, they require a specialized logic
        # that differs from the logic applied to regular track sectors.
        if event in [RED]:

            # at station, re-initialize train sector tracking
            self.train.initialize_sectors()

            self.train.check_acceleration_thread()
            # action = track.sectors[event]

            sleep(0.01)
            self.train.stop()

            # after stopping at station, execute a Timer delay followed by a re-start
            self.train.timed_stop_at_station()

            # if a secondary train instance is registered, call its stop
            # method. But *do not* call its timed delay routine, since this
            # functionality must be commanded by the current train only.
            if self.train.secondary_train is not None:
                self.train.secondary_train.stop()

        elif event in [YELLOW, BLUE]:
            # if the most recent signal event has a color identical to the
            # sector color where the train is right now, this means the train
            # detected the sector end signal, and is departing the sector.
            # It's now entering the inter-sector zone.
            if self.train.Sector is not None and \
                    self.train.Sector.color is not None and \
                    self.train.Sector.color == event:
                self.train.previous_sector = self.train.Sector

                # free current sector. TODO this should be handled elsewhere.
                self.train.Sector.occupied = False

                self.train.Sector = None
                print("Exiting sector ", event)

                # YELLOW sector precedes a station stop for both clockwise
                # and counter-clockwise directions. This should however be
                # integrated in the red sector handling.
                if event in [YELLOW]:
                    self._slowdown()

#TODO code below requires handling of None sector


                # BLUE signal may indicate either the FAST-SLOW decision point within
                # blue sector, or just the end of that sector. Decide which one
                # based on sector type.
                if event in [BLUE] and isinstance(self.train.Sector, StructuredSector):

                    # decision on how to behave from now on depends on the
                    # occupancy status of the next sector ahead of train.
                    next_sector = self.train.Sector.next[self.train.direction]

                    if self.train.Sector.sub_sector_type == FAST:
                        # leaving FAST subsector and entering SLOW
                        self.train.Sector.sub_sector_type = SLOW

                        # train should slow down and eventually stop only if
                        # next sector is occupied. Otherwise, grab next sector.
                        if next_sector.occupied:
                            # occupied: slow down
                            self._slowdown()
                        else:
                            # next sector is free. Grab it.
                            next_sector.occupied = True

                    elif self.train.Sector.sub_sector_type == SLOW:
                        # leaving SLOW sector. Either do a full stop-and-wait,
                        # or keep going based on occupancy status of next sector
                        if next_sector.occupied:
                            self._stop_and_wait()

            elif self.train.Sector is None:
                # train is moving from inter-sector zone into new sector
                self.train.Sector = self.train.previous_sector.next[self.train.direction]
                print("Entering sector ", self.train.Sector.color)

                # lock sector. This was probably handled somewhere else, before
                # the train had taken the decision to enter the sector. But we do
                # it again here just in case.
                self.train.Sector.occupied = True

            else:
                print("ERROR: detected signal inside sector")

    def _slowdown(self):
        # the train might be moving backwards, so first we generate
        # a positive representation of the current power index (the
        # `accelerate` method will handle the actual sense of movement
        # for the new speed values).
        current_power_index_value = self.train.power_index * sign(self.train.power_index)
        # generate downward sequence of power index values. In this case,
        # we want to go way down to speed 1, thus we use zero for the new
        # index (it's being generated by a `range` call)
        new_power_index_value = 0
        power_index_step = -1
        power_index_range = list(range(current_power_index_value,
                                       new_power_index_value,
                                       power_index_step))
        # a sequence of 6 deceleration steps has 5 sleeping intervals. It
        # is executed in approx. 1 sec. Normalize so it takes about the
        # same time regardless of current speed.
        sleep_time = 6. / len(power_index_range) * 0.15
        # sleep_time = 6. / len(power_index_range) * 0.1  # TODO test for fast stop (2-car = 0.1, 1-car = 0.05)
        sleep_time *= 6. / current_power_index_value
        sleep_time *= 1.1  # fudge factor
        self.train.accelerate(power_index_range, sign(self.train.power_index), sleep_time=sleep_time)

    def _stop_and_wait(self):

        #TODO here we have to reset that fast/slow logic on the sector when departing it

        pass