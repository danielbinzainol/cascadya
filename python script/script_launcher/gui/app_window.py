import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from core.runner import ScriptRunner

# --- HARDCODED REFERENCE FOLDER ---
BASE_DIR = r"C:\Users\Daniel BIN ZAINOL\Downloads\python script"
DESC_FILE = os.path.join(BASE_DIR, "script_descriptions.json")

class ScriptLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python App Launcher & Documentation")
        self.root.geometry("900x650") # Made slightly wider to fit the 2 panels
        
        self.current_folder = BASE_DIR
        self.descriptions = self.load_descriptions()
        self.current_app_key = None  # Tracks which app is currently selected
        
        self.build_ui()
        
        if os.path.exists(self.current_folder):
            self.populate_list()
        else:
            messagebox.showwarning("Folder Not Found", f"Could not find the target folder:\n{self.current_folder}")

        # Bind Ctrl+S to save the description
        self.root.bind('<Control-s>', self.shortcut_save)

    def load_descriptions(self):
        """Loads the descriptions JSON file, or creates an empty dict if it doesn't exist."""
        if os.path.exists(DESC_FILE):
            try:
                with open(DESC_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_descriptions(self):
        """Saves the current dictionary of descriptions to the JSON file."""
        with open(DESC_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.descriptions, f, indent=4)

    def build_ui(self):
        # --- Top: Folder Info & Search ---
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="📁 Base:").pack(side=tk.LEFT)
        ttk.Label(top_frame, text=self.current_folder, foreground="gray").pack(side=tk.LEFT, padx=(5, 10))

        ttk.Label(top_frame, text="🔍 Filter:").pack(side=tk.LEFT, padx=(10, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search)
        ttk.Entry(top_frame, textvariable=self.search_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(top_frame, text="🔄 Sync", command=self.on_sync).pack(side=tk.RIGHT, padx=(10, 0))

        # --- Middle: Split PanedWindow ---
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # LEFT PANE: App List
        list_frame = ttk.Frame(paned)
        paned.add(list_frame, weight=1)

        self.tree = ttk.Treeview(list_frame, show="headings")
        self.tree["columns"] = ("Name",)
        self.tree.heading("Name", text="Available Apps & Scripts", anchor='w')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind Single-Click to load description, Double-Click to launch
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda e: self.run_script())

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # RIGHT PANE: Description/Documentation
        desc_frame = ttk.Frame(paned)
        paned.add(desc_frame, weight=2)
        
        header_frame = ttk.Frame(desc_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.lbl_title = ttk.Label(header_frame, text="Select an app...", font=("Arial", 12, "bold"))
        self.lbl_title.pack(side=tk.LEFT)
        
        self.lbl_status = ttk.Label(header_frame, text="", foreground="green")
        self.lbl_status.pack(side=tk.RIGHT)

        ttk.Label(desc_frame, text="Description & Notes (Ctrl+S to save):", foreground="gray").pack(anchor=tk.W)
        self.text_desc = tk.Text(desc_frame, font=("Arial", 11), bg="#fdfdfd", wrap=tk.WORD, state=tk.DISABLED)
        self.text_desc.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        # --- Bottom: Args & Launch ---
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)

        ttk.Label(bottom_frame, text="Arguments (optional):").pack(side=tk.LEFT)
        self.entry_args = ttk.Entry(bottom_frame, width=30)
        self.entry_args.pack(side=tk.LEFT, padx=10)

        ttk.Button(bottom_frame, text="🚀 Launch Selected", command=self.run_script).pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def populate_list(self, filter_text=""):
        self.tree.delete(*self.tree.get_children())
        if not os.path.exists(self.current_folder): return

        items = os.listdir(self.current_folder)
        
        for item in sorted(items, key=str.lower):
            full_path = os.path.join(self.current_folder, item)
            
            # CASE 1: Modular App (Folder with main.py)
            if os.path.isdir(full_path):
                main_script_path = os.path.join(full_path, "main.py")
                if os.path.exists(main_script_path):
                    if filter_text and filter_text not in item.lower():
                        continue
                    
                    display_name = f"🚀 {item} (Modular App)"
                    # Store both the execution path AND the unique app name (item) in tags
                    self.tree.insert("", "end", values=(display_name,), tags=(main_script_path, item))
            
            # CASE 2: Standalone Script
            elif os.path.isfile(full_path) and item.endswith(".py") and item != "main.py":
                if filter_text and filter_text not in item.lower():
                    continue
                
                display_name = f"🐍 {item}"
                # Store the execution path AND the unique app name (item) in tags
                self.tree.insert("", "end", values=(display_name,), tags=(full_path, item))

    def on_search(self, *args):
        self.populate_list(self.search_var.get().lower())
        
    def on_sync(self):
        self.populate_list(self.search_var.get().lower())

    def on_select(self, event):
        """Triggered on single-click. Loads the description for the selected item."""
        selected_item = self.tree.selection()
        if not selected_item: return

        # Grab the unique app name from the second tag
        tags = self.tree.item(selected_item[0])['tags']
        if not tags or len(tags) < 2: return
        
        self.current_app_key = tags[1]
        
        # Update Title
        self.lbl_title.config(text=self.current_app_key)
        
        # Enable text box, clear it, insert saved description, keep it enabled
        self.text_desc.config(state=tk.NORMAL)
        self.text_desc.delete("1.0", tk.END)
        
        saved_desc = self.descriptions.get(self.current_app_key, "")
        self.text_desc.insert(tk.END, saved_desc)
        
        self.lbl_status.config(text="") # Clear any old "Saved" messages

    def shortcut_save(self, event=None):
        """Triggered by Ctrl+S. Saves the current text box to the JSON file."""
        if not self.current_app_key: 
            return # Nothing is selected
            
        # Get the text (ignoring the automatic trailing newline tkinter adds)
        current_text = self.text_desc.get("1.0", "end-1c")
        
        # Update the dictionary and save to file
        self.descriptions[self.current_app_key] = current_text
        self.save_descriptions()
        
        # Show visual confirmation
        self.lbl_status.config(text="✓ Saved")
        self.root.after(2000, lambda: self.lbl_status.config(text=""))

    def run_script(self):
        selected_item = self.tree.selection()
        if not selected_item: return

        # The actual file path to execute is the first tag
        file_path = self.tree.item(selected_item[0])['tags'][0]
        args = self.entry_args.get().strip()

        try:
            ScriptRunner.launch(file_path, args)
        except Exception as e:
            messagebox.showerror("Execution Error", str(e))