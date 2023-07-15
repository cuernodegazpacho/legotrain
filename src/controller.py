import logging
from time import sleep
from threading import RLock

from pylgbst.hub import RemoteHandset
from pylgbst.peripherals import RemoteButton, COLOR_PURPLE

import uuid_definitions
from train import SimpleTrain, SmartTrain, CompoundTrain
from gui import GUI

# logging.basicConfig(level=logging.DEBUG)


# class that provides dummy methods to be used in case train2 is None
class _DummyTrain():
    def up_speed(self):
        return
    def stop(self):
        return
    def down_speed(self):
        return


def controller(train1, train2=None):
    '''
    Main controller function.

    It accepts initialized instances of subclasses of Train.

    This function creates a remote handset instance that allows the operator to control one
    or two trains with one handset.

    Correct startup sequence requires that, with the script already started, the train
    hub(s) be connected first (by momentary press of the green button). Wait a few seconds
    until the hub(s) connect(s). As soon as it(they) connect, press the green button on the remote
    handset. As soon as it connects, the control loop starts running and the GUI pops up on screen.
    Notice that the train LED will be set to its initialization color, and the LED in the handset
    will go solid white. They won't change color (channel) by pressing the green button (the green
    buttons in both train and handset won't respond to button presses from this point on).
    '''
    sleep(5)
    handset = RemoteHandset(address=uuid_definitions.HANDSET_TEST)

    # define sensible handset actions for a dummy train2 object
    if train2 is None:
        train2 = _DummyTrain()

    # actions associated with each handset button
    handset_actions = {
        RemoteButton.LEFT:
        {
            RemoteButton.PLUS: train1.up_speed,
            RemoteButton.RED: train1.stop,
            RemoteButton.MINUS: train1.down_speed
        },
        RemoteButton.RIGHT:
        {
            RemoteButton.PLUS: train2.up_speed,
            RemoteButton.RED: train2.stop,
            RemoteButton.MINUS: train2.down_speed
        },
    }

    # handset callback handles most of the interactive logic associated with the buttons
    def handset_callback(button, set):

        # for now, ignore all button release actions.
        if button == RemoteButton.RELEASE:
            return

        # select action on train speed based on which button was pressed
        handset_actions[set][button]()

    # we can either have one single callback and handle the button set choice in the
    # callback, or have two separate callbacks, one associated with each button set
    # from the start. Since we may be handling two trains identically, each one on one
    # side of the handset, the one-callback approach seems better at preventing code
    # duplication.
    handset.port_A.subscribe(handset_callback)
    handset.port_B.subscribe(handset_callback)


if __name__ == '__main__':

    # global lock for threading access
    # lock = RLock()
    lock = None

    # Tkinter window for displaying status information
    gui = GUI()

    # Use one of these setups to configure

    # ---------------------- Simple train setup --------------------------

    # train = SimpleTrain("Train", "1", lock=lock, report=True, record=True,
    #                           gui=gui, address=uuid_definitions.HUB_ORIG)
    # controller(train)

    # ---------------------- Smart train setup ----------------------------

    # train = SmartTrain("Train", "1", lock=lock, report=True, record=True,
    #                         gui=gui, address=uuid_definitions.HUB_TEST)
    # controller(train)

    # ---------------------- Two-train setup ----------------------------

    train1 = SmartTrain("Train 1", "1", led_color=COLOR_PURPLE, lock=lock, report=True, record=True,
                            gui=gui, address=uuid_definitions.HUB_TEST)
    train2 = SmartTrain("Train 2", "2", lock=lock, report=True, record=True,
                         gui=gui, address=uuid_definitions.HUB_ORIG)
    controller(train1, train2=train2)

    # ---------------------- Compound train setup --------------------------

    # # front train hub allows control over the LED headlight.
    # train_front = SimpleTrain("Front", "1", lock=lock, report=True, record=True,
    #                           gui=gui, address=uuid_definitions.HUB_ORIG)
    #
    # # rear train hub has a vision sensor
    # train_rear = SmartTrain("Rear", "2", lock=lock, report=True, record=True,
    #                         gui=gui, address=uuid_definitions.HUB_TEST)
    #
    # train = CompoundTrain("Massive train", train_front, train_rear)
    #
    # controller(train)

    # --------------------------------------------------------------------------

    # connect gui and start main loop
    gui.root.after(100, gui.after_callback)
    gui.root.mainloop()

