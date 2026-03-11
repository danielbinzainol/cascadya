import tkinter as tk
from core.database import Database
from gui.main_window import MainWindow

def main():
    db = Database()
    root = tk.Tk()
    app = MainWindow(root, db)
    root.mainloop()

if __name__ == "__main__":
    main()