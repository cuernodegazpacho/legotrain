import time
from time import sleep
from threading import Timer

from signal import RED, GREEN, BLUE, YELLOW, INTER_SECTOR
from track import StructuredSector, sectors
from track import FAST, SLOW, DEFAULT_SPEED
from gui import tkinter_output_queue, tk_color, SECTOR


TIME_THRESHOLD = 1.4  # seconds


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
        # events should be processed only when train is in auto mode
        if not self.train.auto:
            return

        # train may be blinded against signals
        if self.train.signal_blind:
            return

        # YELLOW events cause a temporary drop in speed. In the current track
        # layout, they are caused by a signal positioned at the highest point
        # in a bridge; its purpose is to reduce the power setting so the train
        # doesn't speed up too much while going over the descending part of the
        # track.
        if event in [YELLOW]:

            self._process_braking_event()

        # RED events are reserved for handling sectors that contain a
        # train stop (station). As such, they require a specialized logic
        # that differs from the logic applied to regular track sectors.
        elif event in [RED]:

            self._process_station_event(event)

        # signal events coming from sector-defininf tiles are handled here
        elif event in [GREEN, BLUE]:

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
                    self._slowdown(time=2)
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
        # This thrad acts just on the ability of a signal event to be
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
                                         self.train.return_to_default_speed)
        self.train.speedup_timer.start()
        self.train.accelerate(list(range(self.train.power_index, self.train.sector.max_speed + 1)), 1)

        # print("Train ", self.train.name, " entered sector ", self.train.sector.color, " with event ", event)

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
            self._slowdown()

        else:
            # next sector is free. Grab it.
            next_sector.occupier = self.train.name

            # drop speed to a reasonable value to cross over the inter-sector zone,
            # but avoid using train.down_speed(), since it kills any underlying threads.
            new_power_index_value = min(DEFAULT_SPEED - 1, self.train.power_index)
            self._slowdown(new_power_index=new_power_index_value)

    def _process_station_event(self, event):
        '''
        Processes events associated with train stations
        '''
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
        self.train.previous_sector = self.train.sector

        # entering inter-sector zone
        self.train.sector = None
        self.train.report_sector(tk_color[INTER_SECTOR])

        # print("Train ", self.train.name,  "exited sector ", self.train.previous_sector.color)

    def _process_braking_event(self):
        initial_power_index = self.train.power_index

        # fast braking
        new_power_index_value = 2
        self._slowdown(new_power_index=new_power_index_value, time=0.1)

        # time do cross bridge
        time.sleep(1.)

        # accelerate back to entry speed
        power_index_range = list(range(self.train.power_index,
                                       initial_power_index,
                                       1))
        sleep_time = 2. / len(power_index_range)
        self.train.accelerate(power_index_range, sign(self.train.power_index), sleep_time=sleep_time)

    def _slowdown(self, new_power_index=1, time=1.0):
        '''
        Slowdown the train from current power setting to the new power
        setting, taking by default about 1 sec to do that
        '''

        # the train might be moving backwards, so first we generate
        # a positive representation of the current power index (the
        # `accelerate` method will handle the actual sense of movement
        # for the new speed values).
        current_power_index_value = self.train.power_index * sign(self.train.power_index)

        # generate downward sequence of power index values. We subtract 1 because
        # to account for the way the range function works.
        new_power_index_value = new_power_index - 1
        power_index_step = -1
        power_index_range = list(range(current_power_index_value,
                                       new_power_index_value,
                                       power_index_step))

        # accelerate needs the time between each speed setting in the ramp
        sleep_time = time / len(power_index_range)

        self.train.accelerate(power_index_range, sign(self.train.power_index), sleep_time=sleep_time)

    def _stop_and_wait(self, next_sector):
        self.train.stop(from_handset=False)

        # make sure we wait for the next sector to go free. This
        # may be redundant here, since train.restart_movement should
        # be doing the same check anyway. We do just in case though.
        while next_sector.occupier is not None and \
              next_sector.occupier != self.train.name:
            time.sleep(0.5)

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
              "  event: ", event, "  just entered: ", self.train.just_entered_sector)

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


class DummyEventProcessor(EventProcessor):
    '''
    Testing / debug
    '''

    def process_event(self, event):
        print("Event: ", event)

