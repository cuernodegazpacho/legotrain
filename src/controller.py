from time import sleep
import logging

from pylgbst.hub import RemoteHandset
from pylgbst.peripherals import RemoteButton, COLOR_YELLOW, COLOR_PURPLE

from train import SimpleTrain, SmartTrain

# logging.basicConfig(level=logging.DEBUG)

def controller(train):
    '''
    Main controller function.

    It accepts an initialized instance of SimpleTrain. A future upgrade will support
    two instances.

    This function creates a remote handset instance which at this first pass just
    re-creates the functionality available in the unmodified Lego product. Future
    upgrades may include controlling two trains with one handset, or controlling
    each train from a separate handset. Which one, remains to be seen. It all depends
    on usability issues, such as having one person controlling both trains, or having
    two players, each one controlling a separate train.

    Correct startup sequence requires that, with the script already started, the train
    hub be connected first (by a green button momentary press). Wait a few seconds until
    the train hub connects. As soon as it connects, press the green button on the remote
    handset. As soon as it connects, the control loop starts running. Notice that the train
    LED will be set to its initialization color, and the LED in the handset will go solid
    white. They won't change color (channel) by pressing the green button (the green buttons
    in both train and handset won't respond to button presses from this point on).
    '''
    sleep(5)
    # handset = RemoteHandset(address='5D319849-7D59-4EBB-A561-0C37C5EF8DCD')  # train handset
    handset = RemoteHandset(address='2BC6E69B-5F56-4716-AD8C-7B4D5CBC7BF8')  # test handset

    # actions associated with each handset button
    speed_actions = {
        RemoteButton.PLUS: train.up_speed,
        RemoteButton.RED: train.stop,
        RemoteButton.MINUS: train.down_speed
    }

    # handset callback handles most of the interactive logic associated with the buttons
    def handset_callback(button, set):

        # for now, ignore the right side buttons, and all button release actions.
        # This will change when we implement support for a second train.
        if set == RemoteButton.RIGHT or button == RemoteButton.RELEASE:
            return

        # select action on train speed based on which button was pressed
        speed_actions[button]()

    # we can either have one single callback and handle the button set choice in the
    # callback, or have two separate callbacks, one associated with each button set
    # from the start. Since we may be handling two trains identically, each one on one
    # side of the handset, the one-callback approach is better at preventing code
    # duplication.
    handset.port_A.subscribe(handset_callback)
    handset.port_B.subscribe(handset_callback)


if __name__ == '__main__':
    # train hub allows control over the LED headlight.
    # train = SimpleTrain("Train_1", report=True, record=True,
    #                     address='F88800F6-F39B-4FD2-AFAA-DD93DA2945A6')

    # test hub - with sensor
    train = SmartTrain("Train_2", led_color=COLOR_YELLOW, led_secondary_color=COLOR_PURPLE,
                       linear=True,
                        address='86996732-BF5A-433D-AACE-5611D4C6271D')

    controller(train)

    # Dummy main execution thread. All actions take place in the event threads instead.
    while True:
        # since this is an infinite loop, we don't care about unsubscribing from anything
        pass

