from signal import RED, GREEN, BLUE, YELLOW, INTER_SECTOR

DIRECTION_A = "clockwise"
DIRECTION_B = "counter_clockwise"

FAST = 0
SLOW = 1

DEFAULT_SECTOR_TIME = 6.0 #s
TIME_BLIND = 1.0
BRAKING_TIME = 2.0
MINIMUM_TIME_STATION = 2.
MAXIMUM_TIME_STATION = 20.

MAX_SPEED = 6
MAX_SPEED_TIME = 8.0 # s
DEFAULT_SPEED = 4
SECTOR_EXIT_SPEED = 3

class Sector():
    def __init__(self, color, sector_time=DEFAULT_SECTOR_TIME,
                 max_speed=MAX_SPEED, max_speed_time=MAX_SPEED_TIME,
                 exit_speed=SECTOR_EXIT_SPEED):
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
        '''
        self.color = color
        self.sector_time = sector_time
        self.max_speed = max_speed
        self.max_speed_time = max_speed_time
        self.exit_speed = exit_speed

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


def clear_track():
    for sector in sectors.items():
        sector[1].occupier = None


#------------------ TRACK DEFINITION ----------------------------

# sectors
sectors = {"RED_1": Sector(RED),
           GREEN: Sector(GREEN, sector_time=1, max_speed=4, max_speed_time=1.0),
           "RED_2": Sector(RED),
           BLUE: StructuredSector(BLUE, sector_time=2., max_speed_time=10.0)
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
