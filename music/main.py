import tkinter as tk
from player_gui import MusicPlayerGUI

def main():
    root = tk.Tk()
    app = MusicPlayerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()