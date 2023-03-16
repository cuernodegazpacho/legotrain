import time

RED_EVENT = "RED"

class SensorEventProcessor():

    events = {}

    def __init__(self, train):
        self.train = train

    def handle_event(self, event_key):
        # events are discriminated by their color. If an event of a given
        # color is already stored here, it means that this current event is
        # possibly a spurious detection. Verify by checking event times.
        event_time = time.time()
        if event_key in self.events:
            if (event_time - self.events[event_key]) > 1.0:
                # not a secondary detection. Alert caller and
                # redefine stored event
                self.events[event_key] = event_time
                self.train.process_sensor_event(event_key)

            else:
                # secondary detection. Do nothing.
                pass

        # if event of current color is not stored here, store current event
        else:
            self.events[event_key] = event_time
