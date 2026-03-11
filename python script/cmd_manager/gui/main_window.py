import tkinter as tk
from tkinter import ttk, messagebox
import uuid
from gui.context_menu import ContextMenuManager

class MainWindow:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.root.title("Modular Command Manager")
        self.root.geometry("1000x700")
        
        # Maps Treeview Item IDs to actual data nodes
        self.node_map = {} 

        self.build_ui()
        self.refresh_tree()
        self.context_menu = ContextMenuManager(self, self.db)

        self.root.bind("<Control-s>", self.save_current_edits)
        self.root.bind("<Control-S>", self.save_current_edits)

    def build_ui(self):
        # --- Top Search Bar ---
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="Search (Matches Command & Desc):").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search)
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        # --- Main Splitter (Left Tree, Right Details) ---
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEFT PANE: Hierarchical Tree
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=1)
        
        self.tree = ttk.Treeview(tree_frame, show="tree")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # RIGHT PANE: Details (Command & Description)
        detail_frame = ttk.Frame(paned)
        paned.add(detail_frame, weight=3)
        
        self.lbl_title = ttk.Label(detail_frame, text="Select an element", font=("Arial", 14, "bold"))
        self.lbl_title.pack(anchor=tk.W, pady=(0, 10))

        # Command Section
        ttk.Label(detail_frame, text="Command / Workflow (Editable for copy):", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.text_cmd = tk.Text(detail_frame, height=12, font=("Consolas", 11), bg="#f4f4f4")
        self.text_cmd.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Copy Button
        ttk.Button(detail_frame, text="Copy Command", command=self.copy_command).pack(anchor=tk.W, pady=(0, 10))

        # Button Frame to hold Save Button and Notification Label side-by-side
        btn_frame = ttk.Frame(detail_frame)
        btn_frame.pack(anchor=tk.W, pady=(0, 10))

        ttk.Button(btn_frame, text="💾 Save Edits", command=self.save_current_edits).pack(side=tk.LEFT)
        
        # NEW: Subtle green notification label (Starts empty)
        self.save_msg_label = tk.Label(btn_frame, text="", fg="green", font=("Arial", 10))
        self.save_msg_label.pack(side=tk.LEFT, padx=10)
        
        # Description Section
        ttk.Label(detail_frame, text="Description / Notes:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.text_desc = tk.Text(detail_frame, height=8, font=("Arial", 11), bg="#ffffff")
        self.text_desc.pack(fill=tk.BOTH, expand=True)

    def populate_tree(self, node, parent_id=""):
        """Recursively build the UI tree from the nested dictionary."""
        node_id = str(uuid.uuid4())
        self.node_map[node_id] = node
        
        # Display name and visual icon depending on type
        icon = "📁 " if node["type"] == "group" else "⚡ "
        display_name = f"{icon}{node['name']}"
        
        # Only insert root's children to the top level, or root itself
        if parent_id == "" and node["name"] == "Root":
            # Skip showing a literal "Root" folder, just show its children
            for child in node.get("children", []):
                self.populate_tree(child, "")
            return

        self.tree.insert(parent_id, "end", node_id, text=display_name, open=True)
        
        if node["type"] == "group":
            for child in node.get("children", []):
                self.populate_tree(child, node_id)

    def refresh_tree(self, data=None):
        """Clears and redraws the treeview."""
        self.tree.delete(*self.tree.get_children())
        self.node_map.clear()
        
        display_data = data if data else self.db.data
        self.populate_tree(display_data)

    def on_search(self, *args):
        keyword = self.search_var.get()
        filtered_data = self.db.search(keyword)
        self.refresh_tree(filtered_data)

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        
        node = self.node_map[selected[0]]
        self.lbl_title.config(text=node.get("name", ""))
        
        # Clear texts
        self.text_cmd.delete("1.0", tk.END)
        self.text_desc.delete("1.0", tk.END)
        
        if node["type"] == "element":
            self.text_cmd.insert(tk.END, node.get("command", ""))
            self.text_desc.insert(tk.END, node.get("description", ""))

    def copy_command(self):
        content = self.text_cmd.get("1.0", tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)

    def save_current_edits(self, event=None):
        selected = self.tree.selection()
        if not selected: 
            return "break"
        
        node = self.node_map[selected[0]]
        if node["type"] == "element":
            # Save logic
            node["command"] = self.text_cmd.get("1.0", tk.END).strip()
            node["description"] = self.text_desc.get("1.0", tk.END).strip()
            self.db.save_data()
            
            # Show the subtle success message
            self.save_msg_label.config(text="✔ Saved successfully")
            
            # Schedule the message to clear after 2 seconds (2000ms)
            self.root.after(2000, self.clear_save_message)
            
        # Prevents Tkinter from trying to type a control character in the Text widget
        return "break"

    def clear_save_message(self):
        """Clears the green save notification text."""
        self.save_msg_label.config(text="")