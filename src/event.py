import time
from time import sleep
from threading import Timer

from signal import RED, GREEN, BLUE, YELLOW, PURPLE, INTER_SECTOR
from track import StructuredSector, sectors, xtrack, XTrack
from track import FAST, SLOW, DEFAULT_BRAKING_TIME, XTRACK_BRAKING_TIME, \
    MAX_SPEED, DEFAULT_SPEED, SECTOR_EXIT_SPEED, STATION_SPEED
from gui import tk_color


TIME_THRESHOLD = 0.5  # seconds


sign = lambda x: x and (1, -1)[x<0]


class SensorEventFilter():
    '''
    This class is used to filter out multiple detections of the same color
    by the vision sensor in a SmartTrain.

    It works by ignoring all detections of the given color that take place
    within a pre-defined time interval (TIME_THRESHOLD). The first event
    will be passed back to the caller, an instance of SmartTrain, via its
    process_event method.
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

        # handling of station events
        self.last_station_event = None

        # this helps to detected unexpected, thus invalid, events.
        self.last_processed_xtrack_event = None

    def process_event(self, event):
        '''
        Processes events pre-filtered by SensorEventFilter.

        This method contains the main logic for handling the train behavior
        at sector end points, as well as train speed variations, based, among
        other factors, on the occupied/free status of the sector ahead of the
        current sector.

        TODO this badly needs refactoring. A conditional-plagued
        code is not conducive to a modular, scalable design.
        '''

        # report signal color
        self.train.report_signal(tk_color[event])

        # events should be processed only when train is in auto mode
        if not self.train.auto:
            return

        # train may be blinded against signals
        if self.train.signal_blind:
            return

        # check event validity against event history
        #TODO this is checking against PURPLE and RED combinations. These are
        # no longer valid because we got rid of PURPLE, and handle multiple
        # RED events on stations now.
        # is_valid = xtrack.is_valid_event(event, self.last_processed_xtrack_event)
        # if not is_valid:
        #     return
        # self.last_processed_xtrack_event = event

        # PURPLE events are associated with the cross-track.
        #TODO PURPLE tiles are not being detected reliably enough.
        # Using YELLOW for now (no braking needed in current setup).
        # if event in [PURPLE]:
        #     self._process_xtrack_event()

        # YELLOW events cause a temporary drop in speed. In the current track
        # layout, they are caused by a signal positioned at the highest point
        # in a bridge; its purpose is to reduce the power setting so the train
        # doesn't speed up too much while going over the descending part of the
        # track.
        if event in [YELLOW]:
            # self._process_braking_event()
            self._process_xtrack_event()

        # RED events are reserved for handling sectors that contain a
        # train stop (station). As such, they require a specialized logic
        # that differs from the logic applied to regular track sectors.
        elif event in [RED]:
            self.process_station_event(event)

        # signal events coming from sector-defining signal tiles are handled here
        elif event in [GREEN, BLUE]:

            self.process_sector_event(event)

    def process_sector_event(self, event):
        # if the most recent signal event has a color identical to the
        # sector color where the train is right now, this means the train
        # detected either the sector's end signal, or the FAST-SLOW transition
        # point in the current (structured) sector.
        if self.train.sector is not None and \
                self.train.sector.color is not None and \
                self.train.sector.color == event and \
                not self.train.just_entered_sector:

            if isinstance(self.train.sector, StructuredSector):

                self._handle_structured_sector(event)

            else:
                # for a regular, non-structured sector, this event signals the
                # end-of-sector situation. Because in our track layout a regular
                # sector precedes a station sector where a mandatory stop takes
                # place, immediately start a slowdown to minimum speed. Note that
                # this logic depends in part of the specific track layout.
                # TODO generalize handling for regular sectors anywhere in the track.
                self._exit_sector(event)

        elif self.train.sector is None:
            # train is in inter-sector zone, thus this event signals the entry
            # in a new sector
            self._enter_sector(event)

        else:
            # handle unusual situations
            self.recover(event)

    def _enter_sector(self, event):
        '''
        This method handles the situation of a train moving from the
        inter-sector zone into the sector ahead
        '''
        # update current sector in Train instance
        self.train.sector = self.train.previous_sector.next[self.train.direction]

        self.train.report_sector(tk_color[event])

        # structured segments start with a FAST sub-sector
        if isinstance(self.train.sector, StructuredSector):
            self.train.sector.sub_sector_type = FAST
            self.train.report_sector(tk_color[event], subtext="F")

        # lock sector. This was probably handled somewhere else, before
        # the train had taken the decision to enter the sector. But we do
        # it again here just in case.
        self.train.sector.occupier = self.train.name

        # make sure previous sector is released.
        self.train.previous_sector.occupier = None

        # set up timer for sanity check to prevent false detections
        # of a spurious end-of-sector signal. The sector_time parameter
        # defines a time interval, counted from the instant of sector
        # entry, during which the train is blind from sector signals.
        # This thread acts just on the ability of a signal event to be
        # detected; it doesn't affect train movement.
        sector_time = self.train.sector.sector_time
        self.train.time_in_sector = Timer(sector_time, self.train.mark_exit_valid)
        self.train.just_entered_sector = True
        self.train.time_in_sector.start()

        # when entering sector, set timed speedup. Make sure the speedup
        # time duration ends before reaching any signal on the track.
        if self.train.speedup_timer is not None:
            self.train.speedup_timer.cancel()
        self.train.speedup_timer = Timer(self.train.sector.max_speed_time,
                                         self._return_to_sector_speed)
        self.train.speedup_timer.start()

        # enter sector at max speed setting
        self.accelerate(self.train.sector.max_speed)

    def _return_to_sector_speed(self):
        self.accelerate(DEFAULT_SPEED, time=0.8)

    def _handle_structured_sector(self, event):
        '''
        Structured sectors are divided in two sub-sectors, named FAST and SLOW.
        The signal that marks the transition between sub-sectors is of the same
        color as the sector color. The train always enters the sector by the FAST
        side. The purpose of this is to provide the train an opportunity to gradually
        slow down and check the status of the next sector, before hitting the
        end-of-sector signal.

        This method handles the two situations that may happen within a structured
        sector:
        1 - transition between the FAST and SLOW sub-sectors
        2 - exit of the entire structured sector into a inter-sector zone
        '''
        next_sector = self.train.sector.next[self.train.direction]

        if self.train.sector.sub_sector_type == FAST:

            self._handle_subsector_transition(next_sector, event)

        else:
            # leaving SLOW sub-sector, thus leaving the entire structured
            # sector as well. Either do a full stop-and-wait, or keep going,
            # based on occupancy status of next sector
            if next_sector.occupier is not None and \
                    next_sector.occupier != self.train.name:
                # occupied: stop and keep interrogating next sector
                self._stop_and_wait(next_sector)
            else:
                # next sector is free: exit current sector
                # and keep moving
                self._exit_sector(event)

    def _handle_subsector_transition(self, next_sector, event):
        '''
        Logic for handling the sub-sector transition signal within structured sectors.
        '''
        # this method is called when the first signal of the same color as
        # the current sector's is detected. This means that it is a sub-sector
        # transition signal, and thus the train is leaving the FAST sub-sector
        # and entering SLOW
        self.train.sector.sub_sector_type = SLOW
        self.train.report_sector(tk_color[event], subtext="S")

        # Decision on how to behave from now on depends on the occupancy status
        # of the next sector ahead of train. Train should slow down and eventually
        # stop only if next sector is occupied. Otherwise, grab next sector.
        if next_sector.occupier is not None and next_sector.occupier != self.train.name:
            # next sector is occupied: slow down to minimum speed and wait for
            # end-of-sector signal.
            self.accelerate(SECTOR_EXIT_SPEED, time=0.2)

        else:
            # next sector is free. Grab it.
            next_sector.occupier = self.train.name

            # drop speed to a reasonable value to cross over the inter-sector zone,
            # but avoid using train.down_speed(), since it kills any underlying threads.
            speed = min(SECTOR_EXIT_SPEED, self.train.power_index)
            self.accelerate(speed, time=0.2)

    def process_station_event(self, event):
        '''
        Processes events associated with train stations
        '''
        # Check if this is the first, or second signal in a station segment.
        if self.last_station_event is None:
            # first event: mark it is the first event, and take action
            self.last_station_event = "station entry event"
            self._handle_station_entry(event)
        else:
            # second event: it's the actual stop
            # self.last_station_event = None

            # upon detection of the station stop signal (RED), train
            # must stop. To prevent subsequent startups, make sure any
            # thread associated with train movement is cancelled.
            self.train.cancel_acceleration_thread()
            self.train.cancel_speedup_timer()
            sleep(0.01)
            self.train.stop(from_handset=False)

            # gui displays station color
            self.train.report_sector(tk_color[event])

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
                self.train.secondary_train.stop(from_handset=False)

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

    def _exit_sector(self, event):

        # define speed to be used in inter-sector zone
        exit_speed = SECTOR_EXIT_SPEED
        if self.train.sector is not None and self.train.sector.exit_speed is not None:
            exit_speed = self.train.sector.exit_speed

        # entering inter-sector zone
        self.train.previous_sector = self.train.sector
        self.train.sector = None
        self.train.report_sector(tk_color[INTER_SECTOR])

        self.accelerate(exit_speed, time=0.5)

    def _process_braking_event(self):
        # fast braking
        self.accelerate(1, time=0.1)

        # keep brake applied
        time.sleep(DEFAULT_BRAKING_TIME)

        # accelerate back to sector speed
        if self.train.sector is not None:
            pi = self.train.sector.max_speed
        else:
            pi = MAX_SPEED

        self.accelerate(pi)

    def _process_xtrack_event(self):

        # catch false detections and special situations
        # In the curremt layout, a special situation arises with a
        # xtrack object immediately after a station exit.
        if self.train.sector is None:
            if self.train.previous_sector is not None:
                # this can be a xtrack in an inter-sector stretch of track
                previous_sector = self.train.previous_sector
                if previous_sector is not None:
                    xt1 = previous_sector.look_ahead
                    if xt1 is not None and isinstance(xt1, XTrack):
                        # check out from xtrack
                        xt1.book(self.train)
                        return
                else:
                    return
            else:
                return

        # only handle signal if sector and direction are self-consistent.
        # This is redundant for now, but we keep the code in here in the
        # hopes it might be needed when implementing other track layouts.
        if (self.train.sector.color, self.train.direction) in xtrack.valid_signals:

            # stop train if xtrack is booked
            if not xtrack.is_free(self.train):

                self.train.cancel_acceleration_thread()
                self.train.cancel_speedup_timer()
                self.train.cancel_station_timer()

                # brake and wait until full stop
                speed = self.train.power_index
                self.accelerate(0, time=XTRACK_BRAKING_TIME)
                time.sleep(XTRACK_BRAKING_TIME + 0.5) # leeway to account for inertia

                # wait until crossing opens
                while not xtrack.is_free(self.train):
                    time.sleep(0.5)

                # this is the train that last stopped at the xtrack
                xtrack.last_stopped = self.train.name

                # recover speed
                self.accelerate(speed, time=2)

            # if not booked, book it
            else:
                if xtrack.last_stopped is None or \
                   (xtrack.last_stopped is not None and xtrack.last_stopped != self.train.name):
                    xtrack.book(self.train)
                else:
                    xtrack.last_stopped = None

    def _handle_station_entry(self, event):
        # on station entry, decelerate to entry speed. A station sector
        # must use its max_speed parameter to define the entry speed.
        if self.train.sector is not None:
            speed = self.train.sector.max_speed
        else:
            speed = STATION_SPEED
        self.accelerate(speed, time=1.0)

    def accelerate(self, new_power_index, time=1.0):
        '''
        Accelerates the train from current power setting to the new power
        setting, taking by default about 1 sec to do that.

        This seems to be generic enough to even handle the compound train
        '''
        self._accelerate(self.train.power_index, new_power_index, time=time)

    def _accelerate(self, initial_power_index, new_power_index, time=1.0):
        '''
        Accelerates the train from initial power setting to the new power
        setting, taking by default about 1 sec to do that.
        '''
        # new power index must have same sign as initial power index
        initial_power_index_sign = sign(initial_power_index)
        new_power_index_sign = sign(new_power_index)

        # only check if non-zero
        if initial_power_index != 0 and new_power_index != 0 and \
            new_power_index_sign != initial_power_index_sign:
            raise RuntimeError("error in power index signs")

        current_power_index_abs_value = abs(initial_power_index)
        new_power_index_abs_value = abs(new_power_index)

        # find sense of required sequence
        downward = new_power_index_abs_value < current_power_index_abs_value
        if downward:
            power_index_step = -1
        else:
            power_index_step = 1

        # find sign of power indices. Mind that power index can be
        # zero, and thus has no sign
        power_index_sign = new_power_index_sign
        if power_index_sign == 0:
            power_index_sign = initial_power_index_sign

        # generate sequence of power index values. We add the step value
        # to account for the way the range function works.
        power_index_range = list(range(current_power_index_abs_value,
                                       new_power_index_abs_value + power_index_step,
                                       power_index_step))

        # train.accelerate needs the time between each speed setting in the ramp
        sleep_time = time / len(power_index_range)

        self.train.accelerate(power_index_range, power_index_sign, sleep_time=sleep_time)

    def _stop_and_wait(self, next_sector):
        self.train.stop(from_handset=False)

        # make sure we wait for the next sector to go free. This
        # may be redundant here, since train.restart_movement should
        # be doing the same check anyway. We do just in case though.
        while next_sector.occupier is not None and \
              next_sector.occupier != self.train.name:
            time.sleep(0.3)

        self._exit_sector("from stop and wait")
        self.train.restart_movement()

    def recover(self, event):
        # TODO this situation may happen when moving from BLUE to GREEN (or vice-versa)
        # and missing the BLUE end-of-sector signal. The next signal to be detected is
        # GREEN, so it is interpreted as a spurious signal. We may attempt to fix the
        # situation by forcing the current sector to be this last sensed event, GREEN.
        # This requires that:
        # - the train.sector attribute be updated;
        # - the track sectors be updated
        # These updates are contingent upon the availability of sectors. Any conflict
        # should result in an emergency stop. Could we try a recovery sequence after this
        # stop?
        # Maybe we don't need to handle the other similar case, that is, missing the
        # GREEN end-of-sector signal, because a station reset will happen anyway (provided
        # the RED signal be detected).
        print("ERROR: spurious signal inside sector. Train sector: ", self.train.sector.color,
              "  event: ", event, "  just entered: ", self.train.just_entered_sector, "  ",
              self.train.name)

        # # event color matches train's next sector color. This means that the end-of-sector
        # # signal was missed and the train already entered the next sector.
        #
        # if not self.train.just_entered_sector:
        #
        #     if event == self.train.sector.next[self.train.direction].color:
        #
        #         # if next sector (where the train is physically in now) is not occupied,
        #         # grab it
        #         if self.train.sector.next[self.train.direction].occupier is None:
        #             self.train.sector.next[self.train.direction].occupier = self.train.name
        #             self.train.previous_sector = self.train.sector
        #             self.train.sector = self.train.sector.next
        #
        #             print("Fixed!")
        #
        #         # if next sector is occupied, emergency abort
        #         else:
        #             self.train.dispatcher.emergency_stop()


    def _debug(self, msg):
        print("----------------- SECTORS STATUS ---------------------------------")
        print(msg)
        for key in sectors:
            print("Sector: ", sectors[key].color, "   occupier: ", sectors[key].occupier)
        print("----------------- END SECTORS STATUS ---------------------------------")
        print("")


class CompoundTrainEventProcessor(EventProcessor):
    '''
    A CompoundTrain handles some events in a different way than a SmartTrain.
    This class should override any method where special handling is required.

    In a possible future implementation, color events will be interpreted as
    signaling speed changes. The compound train will ignore the sector layout
    of the track. Station handling would be similar to the one in the base
    class. Other colors will just trigger calls to the acceleration method.
    (acceleration cannot yet handle a two-engine compound train)
    '''
    def __init__(self, train):
        '''

        :param train: an instance of CompoundTrain
        '''

        super(CompoundTrainEventProcessor, self).__init__(train)

    def process_event(self, event):
        '''
        Overrides base class to process events in the rear train only.
        '''
        self.train.train_rear.report_signal(tk_color[event])

        if not self.train.train_rear.auto:
            return

        if event in [RED]:
            self.process_station_event(event)

    def process_station_event(self, event):
        '''
        Station events here are just stop signals.
        '''
        # Check if this is the first, or second signal in a station segment.
        if self.last_station_event is None:
            # first event: mark it is the first event, and take action
            self.last_station_event = "station entry event"

            # To prevent subsequent startups, make sure any
            # thread associated with train movement is cancelled.
            self.train.train_rear.cancel_acceleration_thread()
            self.train.train_rear.cancel_speedup_timer()

            # gui displays station color
            self.train.train_rear.report_sector(tk_color[event])

            # ot station entry, slowly decelerate to full stop.
            # Cannot use accelerate method in super class. It correctly
            # handles forward/backward movement, but not in a synchronous
            # way as is required by the compound train. We use here a simpler
            # approach that directly calls the power control methods in
            # the compound train instance. We hope that train inertia will
            # soften the deceleration. We leave as an exercise to the curious
            # programmer to fully implement a threaded accelerate method for
            # a compound train.
            self.train.set_power(1)
            sleep(2.)
            self.train.stop(False)

            # after stopping at station, execute a Timer delay followed by a re-start
            self.train.train_rear.timed_stop_at_station()

            # if a secondary train instance is registered, call its stop
            # method. But *do not* call its timed delay routine, since this
            # functionality must be commanded by the current train only.
            self.train.train_front.stop(from_handset=False)

        else:
            # second event: ignore, and prepare to respond
            # to next station event
            self.last_station_event = None


class DummyEventProcessor(EventProcessor):
    '''
    Testing / debug
    '''

    def process_event(self, event):
        print("Event: ", event)

