from signal import RED, GREEN, BLUE, YELLOW

CLOCKWISE = "clockwise"
COUNTER_CLOCKWISE = "counter_clockwise"

FAST = 0
SLOW = 1

class Sector():
    def __init__(self, color, is_fast=True):
        '''
        Encapsulates properties of a track sector. sectors are used
        to isolate sections of a continuous track, such that only one
        train can be at any given sector at any time.

        As trains move in and out of sectors, they mark the sector
        they are currently in as occupied, so that other trains can
        avoid entering that same sector. A train can book a given
        sector in advance when necessary, to prevent other trains
        from taking it. Trains free sectors when they leave them.

        :param color: the sector's color
        :param is_fast: if True, the sector has an internal sub-sector that
                        can be travelled at faster speeds.
        '''
        self.color = color
        self.is_fast = is_fast

        # Describes sector position in track. For now, this is a 2-element dict
        # with pointers to the two neighboring sectors, keyed by the train's
        # sense of motion (clockwise or counter-clockwise).
        self.next = {}

        # This flag tells that the sector is occupied by a train.
        self.occupied = False


class StructuredSector(Sector):
    '''
    A StructuredSector contains a higher-speed stretch and a lower-speed
    stretch within it. An attribute in the sector tells where the train is
    located. The stretches are separated by a signal with same color as
    the sector itself.
    '''
    def __init__(self, color, is_fast=True):
        super(StructuredSector, self).__init__(color, is_fast=is_fast)

        # defaults assume the train enters the sector via its FAST side.
        self.sub_sector_type = FAST


#------------------ TRACK DEFINITION ----------------------------

station_sector_names = {COUNTER_CLOCKWISE: "RED_1",
                         CLOCKWISE: "RED_2"}

# sectors
sectors = {"RED_1": Sector(RED, is_fast=False),
            YELLOW: Sector(YELLOW),
            "RED_2": Sector(RED, is_fast=False),
            BLUE: StructuredSector(BLUE)
           }

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
sectors["RED_2"].next[CLOCKWISE] = sectors[YELLOW]
sectors[YELLOW].next[CLOCKWISE] = sectors[BLUE]
sectors[BLUE].next[CLOCKWISE] = sectors["RED_2"]

# counter-clockwise track
sectors["RED_1"].next[COUNTER_CLOCKWISE] = sectors[BLUE]
sectors[BLUE].next[COUNTER_CLOCKWISE] = sectors[YELLOW]
sectors[YELLOW].next[COUNTER_CLOCKWISE] = sectors["RED_1"]
