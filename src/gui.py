import tkinter as T

class GUI():

    def __init__(self):
        self.gui = T.Tk()
        self.gui.title("Lego train control")

        label1 = T.Label(self.gui, text="Voltage 1").grid(row=1, column=1)
        label2 = T.Label(self.gui, text="Voltage 2").grid(row=2, column=1)
        label3 = T.Label(self.gui, text="Current 1").grid(row=1, column=3)
        label4 = T.Label(self.gui, text="Current 2").grid(row=2, column=3)

        self.voltage_1_text = T.Label(self.gui, width=10)
        self.voltage_2_text = T.Label(self.gui, width=10)
        self.current_1_text = T.Label(self.gui, width=10)
        self.current_2_text = T.Label(self.gui, width=10)

        self.voltage_1_text.grid(row=1, column=2)
        self.voltage_2_text.grid(row=2, column=2)
        self.current_1_text.grid(row=1, column=4)
        self.current_2_text.grid(row=2, column=4)

if __name__ == '__main__':
    g = GUI()

    g.voltage_1_text.config(text="10.0")
    g.current_1_text.config(text="150.0")

    g.gui.mainloop()
