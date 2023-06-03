import time

RED_EVENT = "RED"
LB_EVENT = "LIGHT BLUE"

TIME_THRESHOLD = 2.0 # seconds

# Vision sensor colorimetry parameters.
# TODO these values are still preliminary and require a lot of testing
# TODO use most recent values from colorimetry notebook
HUE = {}
SATURATION = {}
HUE[RED_EVENT]        = (0.90, 1.00)  # min and max hue for red
SATURATION[RED_EVENT] = (0.55, 0.82)  # min and max saturation for red
HUE[LB_EVENT]         = (0.55, 0.62)  # same for azure (light blue)
SATURATION[LB_EVENT]  = (0.50, 0.72)


class SensorEventFilter():
    '''
    This class is used to filter out multiple detections of the same color
    by the vision sensor in a SmartTrain.

    It works by ignoring all detections of the given color that take place
    within a pre-defined time interval. The first event will be passed back
    to the caller, an instance of SmartTrain, via its process_event method.
    '''

    events = {}

    def __init__(self, smart_train):
        '''
        
        :param smart_train: an instance of SmartTrain 
        '''
        self.smart_train = smart_train

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
                self.smart_train.process_event(event_key)

            else:
                # double detection. Do nothing.
                pass

        # if event of current color is not stored here, store current event
        else:
            self.events[event_key] = event_time
            self.smart_train.process_event(event_key)
