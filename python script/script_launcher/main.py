import tkinter as tk
from tkinter import ttk
from gui.app_window import ScriptLauncherApp

def main():
    root = tk.Tk()
    
    # Optional: Applies a slightly cleaner built-in theme
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
        
    app = ScriptLauncherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()