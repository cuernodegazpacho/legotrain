actions = {"RED": "stop"}


class Segment():
    def __init__(self, name):
        self.name = name
        self.action = actions[self.name]

    def action(self):
        return self.action

station = Segment("RED")

segments = {station.name: station}
