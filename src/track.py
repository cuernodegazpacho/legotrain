from signal import RED, BLUE, YELLOW

CLOCKWISE = "clockwise"
COUNTER_CLOCKWISE = "counter_clockwise"

DEFAULT_SECTOR_TIME = 6 #s
FAST = 0
SLOW = 1

MAX_SPEED = 5
MAX_SPEED_TIME = 8 # s


class Sector():
    def __init__(self, color, sector_time=DEFAULT_SECTOR_TIME,
                 max_speed=MAX_SPEED, max_speed_time=MAX_SPEED_TIME):
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
        '''
        self.color = color
        self.sector_time = sector_time
        self.max_speed = max_speed
        self.max_speed_time = max_speed_time

        # Describes sector position in track. For now, this is a 2-element dict
        # with pointers to the two neighboring sectors, keyed by the train's
        # sense of motion (clockwise or counter-clockwise).
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
    :param sector_time typical time needed to traverse a given sector
    :param max_speed: the speed setting to which the train must
        accelerate when entering the sector
    :param max_speed_time: the time to sustain max speed (in sec.)
    '''
    def __init__(self, color, sector_time=DEFAULT_SECTOR_TIME,
                 max_speed=MAX_SPEED, max_speed_time=MAX_SPEED_TIME):

        super(StructuredSector, self).__init__(color, sector_time=sector_time,
                                               max_speed=max_speed,
                                               max_speed_time=max_speed_time)

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
           YELLOW: Sector(YELLOW, sector_time=8, max_speed_time=4),
           "RED_2": Sector(RED),
           BLUE: StructuredSector(BLUE, sector_time=2, max_speed_time=1)
           }

station_sector_names = {COUNTER_CLOCKWISE: "RED_1",
                        CLOCKWISE: "RED_2"}

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

# clockwise track
sectors["RED_2"].next[CLOCKWISE] = sectors[BLUE]
sectors[BLUE].next[CLOCKWISE] = sectors[YELLOW]
sectors[YELLOW].next[CLOCKWISE] = sectors["RED_2"]

# counter-clockwise track
sectors["RED_1"].next[COUNTER_CLOCKWISE] = sectors[BLUE]
sectors[BLUE].next[COUNTER_CLOCKWISE] = sectors[YELLOW]
sectors[YELLOW].next[COUNTER_CLOCKWISE] = sectors["RED_1"]
