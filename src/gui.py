import queue
import tkinter as T
from tkinter import StringVar

the_queue = queue.Queue()

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
            message = the_queue.get(block=False)
        except queue.Empty:
            # let's try again later
            self.root.after(100, self.after_callback)
            return

        print('after_callback got', message)
        if message is not None:
            # we're not done yet, let's do something with the message and
            # come back later
            self.voltage_1_text.set(message)
            self.root.after(100, self.after_callback)

    def update(self, name, voltage, current, power_index, power):
        self.voltage_1_text.set(str(voltage))


if __name__ == '__main__':
    g = GUI()

    g.voltage_1_text.set("12.0")

    g.root.mainloop()
