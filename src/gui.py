import queue
import tkinter as T
from tkinter import StringVar

tkinter_output_queue = queue.Queue()
QUEUE_POLLING = 50 # ms


class GUI():
    def __init__(self):
        self.root = T.Tk()
        self.root.geometry("500x150")
        font = ('Helvetica', 24)

        self.root.title("Lego train control")

        T.Label(self.root, text="Voltage 1", font=font).grid(row=1, column=1)
        T.Label(self.root, text="Voltage 2", font=font).grid(row=2, column=1)
        T.Label(self.root, text="Current 1", font=font).grid(row=1, column=3)
        T.Label(self.root, text="Current 2", font=font).grid(row=2, column=3)

        self.voltage_1_text = StringVar(self.root, '- - -')
        self.current_1_text = StringVar(self.root, '- - -')
        self.voltage_2_text = StringVar(self.root, '- - -')
        self.current_2_text = StringVar(self.root, '- - -')

        self.voltage_1_label = T.Label(self.root, textvariable=self.voltage_1_text, font=font, width=10)
        self.voltage_2_label = T.Label(self.root, textvariable=self.voltage_2_text, font=font, width=10)
        self.current_1_label = T.Label(self.root, textvariable=self.current_1_text, font=font, width=10)
        self.current_2_label = T.Label(self.root, textvariable=self.current_2_text, font=font, width=10)

        self.voltage_1_label.grid(row=1, column=2)
        self.voltage_2_label.grid(row=2, column=2)
        self.current_1_label.grid(row=1, column=4)
        self.current_2_label.grid(row=2, column=4)

    def after_callback(self):
        try:
            message = tkinter_output_queue.get(block=False)
        except queue.Empty:
            # try again later
            self.root.after(QUEUE_POLLING, self.after_callback)
            return

        if message is not None:
            self._decode_message(message)

            # we're not done yet, let's come back later
            self.root.after(QUEUE_POLLING, self.after_callback)

    def encode_basic_variables(self, name, voltage, current, power_index, power):
        message = ("BASIC, %s, %5.2f, %5.3f, %i, %4.2f" % (name, voltage, current, power_index, power))
        return message

    def _decode_message(self, message):
        tokens = message.split(',')

        name = tokens[1]
        voltage = tokens[2]
        current = tokens[3]
        power_index = tokens[4]
        power_level = tokens[5]

        self.voltage_1_text.set(voltage)


if __name__ == '__main__':
    g = GUI()
    g.voltage_1_text.set("12.0")
    g.root.mainloop()
