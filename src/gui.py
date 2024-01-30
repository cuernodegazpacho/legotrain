import queue
import tkinter as T
from tkinter import StringVar, LEFT, TOP

tkinter_output_queue = queue.Queue()
QUEUE_POLLING = 50 # ms

BASIC = "BASIC"
ASTATION = "@STATION"
SECTOR = "SECTOR"


class GUI():
    def __init__(self):
        self.root = T.Tk()
        self.root.geometry("600x430")
        font = ('Helvetica', 36)

        self.root.title("Lego train control")

        left_frame = T.Frame(self.root)
        center_frame = T.Frame(self.root)
        right_frame = T.Frame(self.root)

        # left frame: field names
        T.Label(left_frame, text="",          font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Voltage",   font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Current",   font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Speed",     font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Power",     font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="@ station", font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Sector",    font=font, justify=LEFT).pack(side=TOP)

        # text variables
        self.name_1_text     = StringVar(center_frame, '')
        self.voltage_1_text  = StringVar(center_frame, '- - -')
        self.current_1_text  = StringVar(center_frame, '- - -')
        self.speed_1_text    = StringVar(center_frame, '- - -')
        self.power_1_text    = StringVar(center_frame, '- - -')
        self.astation_1_text = StringVar(center_frame, '- - -')
        # self.sector_1_text   = StringVar(center_frame, '- - -')

        self.name_2_text     = StringVar(right_frame, '')
        self.voltage_2_text  = StringVar(right_frame, '- - -')
        self.current_2_text  = StringVar(right_frame, '- - -')
        self.speed_2_text    = StringVar(right_frame, '- - -')
        self.power_2_text    = StringVar(right_frame, '- - -')
        self.astation_2_text = StringVar(center_frame, '- - -')
        # self.sector_2_text   = StringVar(center_frame, '- - -')

        # center frame: fields associated with id 1
        width = 9
        self.name_1_label     = T.Label(center_frame, textvariable=self.name_1_text, font=font)
        self.voltage_1_label  = T.Label(center_frame, textvariable=self.voltage_1_text, font=font, width=width)
        self.current_1_label  = T.Label(center_frame, textvariable=self.current_1_text, font=font, width=width)
        self.speed_1_label    = T.Label(center_frame, textvariable=self.speed_1_text, font=font, width=width)
        self.power_1_label    = T.Label(center_frame, textvariable=self.power_1_text, font=font, width=width)
        self.astation_1_label = T.Label(center_frame, textvariable=self.astation_1_text, font=font, width=width)
        # self.sector_1_label   = T.Label(center_frame, textvariable=self.sector_1_text, font=font, width=width, anchor="e")
        self.sector_1_label   = T.Label(center_frame, font=font, width=5, anchor="e")

        self.name_1_label.pack(side=TOP)
        self.voltage_1_label.pack(side=TOP)
        self.current_1_label.pack(side=TOP)
        self.speed_1_label.pack(side=TOP)
        self.power_1_label.pack(side=TOP)
        self.astation_1_label.pack(side=TOP)
        self.sector_1_label.pack(side=TOP)

        # right frame: fields associated with id 2
        self.name_2_label     = T.Label(right_frame, textvariable=self.name_2_text, font=font)
        self.voltage_2_label  = T.Label(right_frame, textvariable=self.voltage_2_text, font=font, width=width)
        self.current_2_label  = T.Label(right_frame, textvariable=self.current_2_text, font=font, width=width)
        self.speed_2_label    = T.Label(right_frame, textvariable=self.speed_2_text, font=font, width=width)
        self.power_2_label    = T.Label(right_frame, textvariable=self.power_2_text, font=font, width=width)
        self.astation_2_label = T.Label(right_frame, textvariable=self.astation_2_text, font=font, width=width)
        # self.sector_2_label   = T.Label(right_frame, textvariable=self.sector_2_text, font=font, width=width, anchor="e")
        self.sector_2_label   = T.Label(right_frame, font=font, width=5, anchor="e")

        self.name_2_label.pack(side=TOP)
        self.voltage_2_label.pack(side=TOP)
        self.current_2_label.pack(side=TOP)
        self.speed_2_label.pack(side=TOP)
        self.power_2_label.pack(side=TOP)
        self.astation_2_label.pack(side=TOP)
        self.sector_2_label.pack(side=TOP)

        left_frame.pack(side=LEFT)
        center_frame.pack(side=LEFT)
        right_frame.pack(side=LEFT)

    def after_callback(self):
        try:
            message = tkinter_output_queue.get(block=False)
        except queue.Empty:
            # try again later
            self.root.after(QUEUE_POLLING, self.after_callback)
            return

        if message is not None:
            self._decode_message_and_update(message)

            # we're not done yet, let's come back later
            self.root.after(QUEUE_POLLING, self.after_callback)

    def encode_basic_variables(self, name, id, voltage, current, power_index, power):
        message = ("%s, %s, %1s, %5.2f, %5.3f, %i, %4.2f" %
                   (BASIC, name, id, voltage, current, power_index, power))
        return message

    def encode_int_variable(self, message_type, name, id, value):
        message = (message_type + ", %s, %1s, %3i" % (name, id, value))
        return message

    def encode_str_variable(self, message_type, name, id, value):
        message = (message_type + ", %s, %1s, %s" % (name, id, value))
        return message

    def _decode_message_and_update(self, message):
        tokens = message.split(',')

        if tokens[0] == BASIC:
            name = tokens[1]
            id = tokens[2].strip()
            voltage_value = tokens[3]
            current_value = tokens[4]
            speed = tokens[5]
            power = tokens[6]

            vname = f"name_{id}_text".format(id=id)
            self.__dict__[vname].set(name)
            vname = f"voltage_{id}_text".format(id=id)
            self.__dict__[vname].set(voltage_value)
            vname = f"current_{id}_text".format(id=id)
            self.__dict__[vname].set(current_value)
            vname = f"speed_{id}_text".format(id=id)
            self.__dict__[vname].set(speed)
            vname = f"power_{id}_text".format(id=id)
            self.__dict__[vname].set(power)

        elif tokens[0] == ASTATION:
            id = tokens[2].strip()
            astation = tokens[3]

            vname = f"astation_{id}_text".format(id=id)
            self.__dict__[vname].set(astation)

        elif tokens[0] == SECTOR:
            id = tokens[2].strip()
            color = tokens[3].strip()

            vname = f"sector_{id}_label".format(id=id)
            self.__dict__[vname].configure(bg=color)


if __name__ == '__main__':
    g = GUI()

    g.voltage_1_text.set("8.1")
    g.name_1_text.set("Blue")

    g.voltage_2_text.set("7.9")
    g.name_2_text.set("Purple")

    g.sector_1_label.configure(bg='blue')
    g.sector_2_label.configure(bg='yellow')

    g.root.mainloop()
