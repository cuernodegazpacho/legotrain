import queue
import tkinter as T
from tkinter import StringVar, LEFT, TOP

tkinter_output_queue = queue.Queue()
QUEUE_POLLING = 50 # ms


class GUI():
    def __init__(self):
        self.root = T.Tk()
        self.root.geometry("650x350")
        font = ('Helvetica', 36)

        self.root.title("Lego train control")

        left_frame = T.Frame(self.root)
        center_frame = T.Frame(self.root)
        right_frame = T.Frame(self.root)

        # left frame: field names
        T.Label(left_frame, text="",        font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Voltage", font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Current", font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Speed",   font=font, justify=LEFT).pack(side=TOP)
        T.Label(left_frame, text="Power",   font=font, justify=LEFT).pack(side=TOP)

        # text variables
        self.name_1_text = StringVar(center_frame, '')
        self.voltage_1_text = StringVar(center_frame, '- - -')
        self.current_1_text = StringVar(center_frame, '- - -')
        self.speed_1_text = StringVar(center_frame, '- - -')
        self.power_1_text = StringVar(center_frame, '- - -')
        self.name_2_text = StringVar(right_frame, '')
        self.voltage_2_text = StringVar(right_frame, '- - -')
        self.current_2_text = StringVar(right_frame, '- - -')
        self.speed_2_text = StringVar(right_frame, '- - -')
        self.power_2_text = StringVar(right_frame, '- - -')

        # center frame: fields associated with id 1
        self.name_1_label = T.Label(center_frame, textvariable=self.name_1_text, font=font)
        self.voltage_1_label = T.Label(center_frame, textvariable=self.voltage_1_text, font=font, width=10, anchor="e")
        self.current_1_label = T.Label(center_frame, textvariable=self.current_1_text, font=font, width=10, anchor="e")
        self.speed_1_label =   T.Label(center_frame, textvariable=self.speed_1_text, font=font, width=10, anchor="e")
        self.power_1_label =   T.Label(center_frame, textvariable=self.power_1_text, font=font, width=10, anchor="e")
        self.name_1_label.pack(side=TOP)
        self.voltage_1_label.pack(side=TOP)
        self.current_1_label.pack(side=TOP)
        self.speed_1_label.pack(side=TOP)
        self.power_1_label.pack(side=TOP)

        # right frame: fields associated with id 2
        self.name_2_label = T.Label(right_frame, textvariable=self.name_2_text, font=font)
        self.voltage_2_label = T.Label(right_frame,  textvariable=self.voltage_2_text, font=font, width=10, anchor="e")
        self.current_2_label = T.Label(right_frame,  textvariable=self.current_2_text, font=font, width=10, anchor="e")
        self.speed_2_label =   T.Label(right_frame, textvariable=self.speed_2_text, font=font, width=10, anchor="e")
        self.power_2_label =   T.Label(right_frame, textvariable=self.power_2_text, font=font, width=10, anchor="e")
        self.name_2_label.pack(side=TOP)
        self.voltage_2_label.pack(side=TOP)
        self.current_2_label.pack(side=TOP)
        self.speed_2_label.pack(side=TOP)
        self.power_2_label.pack(side=TOP)

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
        message = ("BASIC, %s, %1s, %5.2f, %5.3f, %i, %4.2f" % (name, id, voltage, current, power_index, power))
        return message

    def _decode_message_and_update(self, message):
        tokens = message.split(',')

        if tokens[0] != "BASIC":
            return

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


if __name__ == '__main__':
    g = GUI()
    g.voltage_1_text.set("12.0")
    g.root.mainloop()
