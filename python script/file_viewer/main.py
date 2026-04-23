import tkinter as tk
from gui.app_window import FileQuickViewApp

def main():
    root = tk.Tk()
    app = FileQuickViewApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()