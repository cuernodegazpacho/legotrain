from threading import RLock

from signal import RED, GREEN, BLUE, PURPLE
from gui import tk_color, INTER_SECTOR

# these names are actually descriptive on a topologically circular track,
# but are just labels on a figure-8 track, or more complex topologies.
DIRECTION_A = "clockwise"
DIRECTION_B = "counter_clockwise"

FAST = 0
SLOW = 1

DEFAULT_SECTOR_TIME = 0.8 #s
TIME_BLIND = 0.7
DEFAULT_BRAKING_TIME = 2.0
XTRACK_BRAKING_TIME = 0.5

MAX_SPEED = 7
MAX_SPEED_TIME = 4.5 # s
DEFAULT_SPEED = 4
SECTOR_EXIT_SPEED = 2
STATION_SPEED = 1

class Sector():
    def __init__(self, color, sector_time=DEFAULT_SECTOR_TIME,
                 max_speed=MAX_SPEED, max_speed_time=MAX_SPEED_TIME,
                 exit_speed=SECTOR_EXIT_SPEED, look_ahead=None):
        '''
        Encapsulates properties of a track sector. Sectors are used
        to isolate sections of a continuous track, such that only one
        train can be at any given sector at any time.

        As trains move in and out of sectors, they mark the sector
        they are currently in as occupied, so that other trains can
        avoid entering that same sector. A train can book a given
        sector in advance when necessary, to prevent other trains
        from taking it. Trains free sectors when they leave them,
        or, in some cases, only when they enter the next sector.

        A "look ahead" Xtrack object can be provided. In case it is not
        None, the sector will check its status before attempting to
        move out of the sector, in case it stopped there. This should
        be used whenever a xtrack object sits close to a sector exit.

        Sectors support variable speed. For now, we define a high speed
        setting that should be maintained for a given time, after which
        the train returns to its default auto-control speed.

        The sector instance should be initialized with a time value in sec
        that represents the typical time interval a train takes to traverse
        the sector. This is used to prevent premature false detections of a
        sector end mark.

        :param color: the sector's color
        :param sector_time typical time needed to traverse a given sector
        :param max_speed: the speed setting to which the train must
            accelerate when entering the sector
        :param max_speed_time: the time to sustain max speed (in sec.)
        :param exit_speed: the speed setting to which the train must
            accelerate when exiting the sector
        :param look_ahead: a XTrack object that has to be checked
            in advance
        '''
        self.color = color
        self.sector_time = sector_time
        self.max_speed = max_speed
        self.max_speed_time = max_speed_time
        self.exit_speed = exit_speed
        self.look_ahead = look_ahead

        # Describes sector position in track. For now, this is a 2-element dict
        # with pointers to the two neighboring sectors, keyed by the train's
        # sense of motion (A or B).
        self.next = {}

        # This attribute tells what train owns the sector.
        self.occupier = None


class StructuredSector(Sector):
    '''
    A StructuredSector contains a higher-speed stretch and a lower-speed
    stretch within it. An attribute in the sector tells where the train is
    located. The stretches are separated by a signal mark with same color
    as the sector itself.

    Note that in this case, the time it takes to traverse a sector should be
    the time it takes to reach the FAST-SLOW transition point only (otherwise
    that transition point won't be detected)

    :param color: the sector's color
    :param sector_time typical time needed to traverse a given sector.
        End-of-sector events are ignored if happening before this time limit.
    :param max_speed: the speed setting to which the train must
        accelerate when entering the sector
    :param max_speed_time: the time to sustain max speed (in sec.). After that,
        the speed in bumped down twice.
    :param exit_speed: the speed setting to which the train must
        accelerate when exiting the sector
    '''
    def __init__(self, color, sector_time=DEFAULT_SECTOR_TIME,
                 max_speed=MAX_SPEED, max_speed_time=MAX_SPEED_TIME,
                 exit_speed=SECTOR_EXIT_SPEED):

        super(StructuredSector, self).__init__(color, sector_time=sector_time,
                                               max_speed=max_speed,
                                               max_speed_time=max_speed_time,
                                               exit_speed=exit_speed)

        # defaults assume the train enters the sector via its FAST side.
        # Note that a physical sector may have two SLOW sub-sectors, one
        # at each end. However, for any given train direction, only one
        # is visible.
        self.sub_sector_type = FAST


class XTrack():
    '''
    XTrack encapsulates the information needed for a train to move across a
    cross track crossing.

    Once a cross-track signal is detected, the appropriate check is performed to
    see if the cross-track is free. If free, the train books the cross-track and
    keeps moving. If not free, the train should stop and wait until the cross-track
    opens. Or, if the cross-track was booked by the same train that is querying it,
    it means that the cross-track exit signal was detected; it that case, just open
    the cross-track.
    '''
    # signals may not be required at the 4 sides of a cross-track. The list
    # of valid signals should be queried by the user in order to accept track
    # signals that make sense for the specific track layout. The list contains
    # valid pairs of (sector, direction).
    # For the specific track layout we have now, this is redundant. But we keep
    # it in place just in case. New layouts are coming out soon...
    valid_signals = [
        (BLUE, DIRECTION_A),
        (BLUE, DIRECTION_B),
        (GREEN, DIRECTION_A),
        (GREEN, DIRECTION_B),
        (RED, DIRECTION_A),
        (RED, DIRECTION_B),
    ]
    def __init__(self, name):

        # keep identifications of trains that booked, and last stopped
        self.booked = None
        self.last_stopped = None

        self.lock = RLock()

    def is_free(self, train):
        self.lock.acquire()
        result = not (self.booked is not None and self.booked != train.name)
        self.lock.release()
        return result

    def book(self, train):
        self.lock.acquire()

        if self.booked is None:
            self.booked = train.name
            train.report_xtrack(tk_color[RED])

        elif self.booked == train.name:
            self.booked = None
            train.report_xtrack(tk_color[INTER_SECTOR])

        else:
            print("Error booking xtrack")
            #TODO maybe should generate an emergency stop?

        self.lock.release()

    def initialize(self, train):
        self.booked = None
        if train is not None and train.gui is not None:
            train.report_xtrack(tk_color[INTER_SECTOR])

    def is_valid_event(self, current_event, previous_event):
        # checks for unexpected events. This may need to be made more
        # generic/capable, but for now we just add each case as an
        # explicit check.
        result = True

        # case 1: a PURPLE event may be triggered by a RED tile (and the
        # other way around), since their HSV values are kinda close to
        # each other. In the current track layout, these are invalid
        # combinations. That is, there are no situations where a RED tile
        # immediately precedes, or is followed, by a PURPLE tile.
        # TODO: this might not be the casee when 2 xtracks are present
        if (current_event in [PURPLE] and previous_event in [RED]) or \
                (current_event in [RED] and previous_event in [PURPLE]):
            result = False

        # case 2: multiple RED events are not allowed, since stations are
        # never positioned that close to each other. This may happen when
        # a train stops at a station, with its sensor right above the red
        # tile. The sensor may keep triggering events randomly. Class
        # SensorEventFilter won't be able to detect such multiple events
        # coming from a stopped train, since this filter checks for event
        # multiplicity only within a short time interval.
        if (current_event in [RED] and previous_event in [RED]):
            result = False

        return result


def clear_track():
    for sector in sectors.items():
        sector[1].occupier = None


#------------------ TRACK DEFINITION ----------------------------

# this track layout has one instance of cross-track
xtrack = XTrack("Crossing 1")

# sectors. Note that the xtrack sits right after the exit from RED_2
#TODO max_speed doesn't work on the red sectors, since they lack a sector
# entry signal tile. Use special handling when exiting the previous segment
sectors = {"RED_1": Sector(RED, max_speed=2, max_speed_time=15.),
           GREEN: Sector(GREEN, max_speed=5, max_speed_time=3.),
           "RED_2": Sector(RED, max_speed=3, look_ahead=xtrack),
           BLUE: StructuredSector(BLUE, max_speed_time=4.)
           }

station_sector_names = {DIRECTION_B: "RED_1",
                        DIRECTION_A: "RED_2"}


# The track layout is defined by how the sectors connect to each
# other. There are actually two tracks, one for each direction of
# movement. In a fixed switch track, this is enough to completely
# specify a train's trajectory. If movable switches are included,
# we will probably need a 2-level dict to specify the two possible
# choices allowed in the sector connections where a movable switch
# is located.

# Since in this basic initial implementation we have 2 red sectors
# (stations), we use a special string to key them into the 'sectors'
# dict.

# A track
sectors["RED_2"].next[DIRECTION_A] = sectors[BLUE]
sectors[BLUE].next[DIRECTION_A] = sectors[GREEN]
sectors[GREEN].next[DIRECTION_A] = sectors["RED_2"]

# B track
sectors["RED_1"].next[DIRECTION_B] = sectors[BLUE]
sectors[BLUE].next[DIRECTION_B] = sectors[GREEN]
sectors[GREEN].next[DIRECTION_B] = sectors["RED_1"]
