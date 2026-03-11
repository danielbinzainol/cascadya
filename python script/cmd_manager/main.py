import tkinter as tk
from core.database import Database
from gui.main_window import MainWindow

def main():
    # 1. Initialize the backend
    db = Database()
    
    # 2. Initialize the Tkinter root
    root = tk.Tk()
    
    # 3. Attach the GUI to the root and pass the database
    app = MainWindow(root, db)
    
    # 4. Start the application
    root.mainloop()

if __name__ == "__main__":
    main()