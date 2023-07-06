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
segments = {"RED_1": Segment("RED", is_fast=False),
            "MAGENTA": Segment("MAGENTA", is_fast=False),
            "GREEN": Segment("GREEN"),
            "RED_2": Segment("RED", is_fast=False),
            "YELLOW": Segment("YELLOW", is_fast=False),
            "BLUE": Segment("BLUE")
           }

# The track layout is defined by how the segments connect to each
# other. There are actually two tracks, one for each direction of
# movement. In a fixed switch track, this is enough to completely
# specify a train's trajectory. If movable switches are included,
# we will probably need a 2-level dict to specify the two possible
# choices allowed in the segment connections where a movable switch
# is located.

#TODO use color constants defined in event.py instead of plain strings.
# That way, segments are tied directly to the sensor response associated
# with each segment.

segments["GREEN"].next[CLOCKWISE] = segments["MAGENTA"]
segments["GREEN"].next[ANTI_CLOCKWISE] = segments["YELLOW"]
segments["BLUE"].next[CLOCKWISE] = segments["RED_2"]
segments["BLUE"].next[ANTI_CLOCKWISE] = segments["RED_1"]
segments["MAGENTA"].next[CLOCKWISE] = segments["BLUE"]
segments["MAGENTA"].next[ANTI_CLOCKWISE] = segments["GREEN"]
segments["YELLOW"].next[CLOCKWISE] = segments["GREEN"]
segments["YELLOW"].next[ANTI_CLOCKWISE] = segments["BLUE"]
segments["RED_1"].next[CLOCKWISE] = segments["BLUE"]
segments["RED_1"].next[ANTI_CLOCKWISE] = segments["GREEN"]
segments["RED_2"].next[CLOCKWISE] = segments["GREEN"]
segments["RED_2"].next[ANTI_CLOCKWISE] = segments["BLUE"]
