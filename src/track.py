from event import RED, GREEN, BLUE

CLOCKWISE = "clockwise"
ANTI_CLOCKWISE = "anti_clockwise"

class Segment():
    def __init__(self, color, is_fast=True):
        '''






        :param color: the segment's color
        :param is_fast: if True, the segment has an internal sub-segment that
                        can be travelled at faster speeds.
        '''
        self.color = color
        self.is_fast = is_fast

        # for now, this is a 2-element dict with pointers to the two neighboring
        # segments, keyed by the train's sense of motion (clockwise or counter-clockwise).
        self.next = {}

#------------------ TRACK DEFINITION ----------------------------

# segments
segments = {"RED_1": Segment(RED, is_fast=False),
            GREEN: Segment(GREEN),
            "RED_2": Segment(RED, is_fast=False),
            BLUE: Segment(BLUE)
           }

# The track layout is defined by how the segments connect to each
# other. There are actually two tracks, one for each direction of
# movement. In a fixed switch track, this is enough to completely
# specify a train's trajectory. If movable switches are included,
# we will probably need a 2-level dict to specify the two possible
# choices allowed in the segment connections where a movable switch
# is located.

# Since in this basic initial implementation we have 2 red segments
# (stations), we use a special string to key them into the 'segments'
# dict.

# clockwise track
segments[GREEN].next[CLOCKWISE] = segments[BLUE]
segments[BLUE].next[CLOCKWISE] = segments["RED_2"]
segments["RED_2"].next[CLOCKWISE] = segments[GREEN]

# anti-clockwise track
segments[GREEN].next[ANTI_CLOCKWISE] = segments[BLUE]
segments[BLUE].next[ANTI_CLOCKWISE] = segments["RED_1"]
segments["RED_1"].next[ANTI_CLOCKWISE] = segments[GREEN]
