import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import uuid
import os
from gui.context_menu import ContextMenuManager

class MainWindow:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.root.title("Ansible Playbook Documentation Manager")
        self.root.geometry("1100x700")
        
        self.node_map = {} 
        self.current_node_id = None
        
        self.build_ui()
        self.refresh_tree()
        self.context_menu = ContextMenuManager(self, self.db)
        
        self.root.bind('<Control-s>', self.shortcut_save)
        # --- NEW: Bind explicitly to the text box so it doesn't get swallowed ---
        self.text_content.bind('<Control-s>', self.shortcut_save)
        
        # --- NEW: Intercept the Window Close 'X' button to force a final save ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_ui(self):
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="Search Docs:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search)
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEFT PANE: Tree & Export Button
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Note: selectmode="extended" allows Ctrl+Click and Shift+Click multiselect
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="extended")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Export Button at the bottom of the left pane
        btn_export = ttk.Button(left_frame, text="📤 Export Selected Folders to TXT", command=self.export_selected)
        btn_export.pack(fill=tk.X, pady=(5, 0))

        # RIGHT PANE: Single Panel Details
        detail_frame = ttk.Frame(paned)
        paned.add(detail_frame, weight=3)
        
        header_frame = ttk.Frame(detail_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_title = ttk.Label(header_frame, text="Select a document", font=("Arial", 16, "bold"))
        self.lbl_title.pack(side=tk.LEFT)
        
        self.lbl_status = ttk.Label(header_frame, text="", foreground="gray")
        self.lbl_status.pack(side=tk.RIGHT)

        self.text_content = tk.Text(detail_frame, font=("Consolas", 11), bg="#fdfdfd", wrap=tk.WORD, undo=True)
        self.text_content.pack(fill=tk.BOTH, expand=True)

    def populate_tree(self, node, parent_id=""):
        node_id = str(uuid.uuid4())
        self.node_map[node_id] = node
        
        icon = "📁 " if node["type"] == "group" else "📄 "
        display_name = f"{icon}{node['name']}"
        
        if parent_id == "" and node["name"] == "Root":
            for child in node.get("children", []):
                self.populate_tree(child, "")
            return

        self.tree.insert(parent_id, "end", node_id, text=display_name, open=True)
        
        if node["type"] == "group":
            for child in node.get("children", []):
                self.populate_tree(child, node_id)

    def refresh_tree(self, data=None):
        self.tree.delete(*self.tree.get_children())
        self.node_map.clear()
        self.populate_tree(data if data else self.db.data)

    def on_search(self, *args):
        self.refresh_tree(self.db.search(self.search_var.get()))

    def auto_save_current(self):
        if not self.current_node_id: return
        node = self.node_map.get(self.current_node_id)
        
        if node and node["type"] == "element":
            current_text = self.text_content.get("1.0", "end-1c")
            if node.get("content", "") != current_text:
                node["content"] = current_text
                self.db.save_data()

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        
        self.auto_save_current()
        
        # Always load the last clicked item in the details pane
        self.current_node_id = selected[-1]
        node = self.node_map[self.current_node_id]
        
        self.lbl_title.config(text=node.get("name", ""))
        self.text_content.delete("1.0", tk.END)
        self.lbl_status.config(text="")
        
        if node["type"] == "element":
            self.text_content.insert(tk.END, node.get("content", ""))
            self.text_content.config(state=tk.NORMAL)
        else:
            self.text_content.insert(tk.END, "Select a document element to edit...")
            self.text_content.config(state=tk.DISABLED)

    def shortcut_save(self, event=None):
        self.auto_save_current()
        self.lbl_status.config(text="✓ Saved", foreground="green")
        self.root.after(2000, lambda: self.lbl_status.config(text=""))
        return "break" # <--- Add this line

    def export_selected(self):
        """Extracts multiselected folders and formats them into nice TXT files."""
        # Save any in-progress typing first
        self.auto_save_current()
        
        selected_ids = self.tree.selection()
        if not selected_ids:
            messagebox.showinfo("Export", "Please select at least one folder to export.\n(Hold Ctrl or Shift to select multiple)")
            return
            
        # Filter to only groups (folders)
        nodes_to_export = [self.node_map[i] for i in selected_ids if self.node_map[i]["type"] == "group"]
        
        if not nodes_to_export:
            messagebox.showinfo("Export", "No folders selected. Please select a Folder/Group to export.")
            return
            
        # Ask for destination
        dest_dir = filedialog.askdirectory(title="Select Destination Folder")
        if not dest_dir: return 
        
        # Recursive formatter
        def extract_content(node):
            content = ""
            if node["type"] == "element":
                content += f"## {node['name']}\n"
                content += f"{node.get('content', '')}\n\n"
            elif node["type"] == "group":
                for child in node.get("children", []):
                    content += extract_content(child)
            return content
            
        # Write files silently
        success_count = 0
        for node in nodes_to_export:
            # Clean folder name to make a safe filename
            safe_name = "".join(c for c in node["name"] if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_name: safe_name = "export"
            
            filepath = os.path.join(dest_dir, f"{safe_name}.txt")
            
            # Format the document
            file_body = f"{'='*50}\nPLAYBOOK: {node['name']}\n{'='*50}\n\n"
            for child in node.get("children", []):
                file_body += extract_content(child)
                
            # 'w' mode automatically overwrites existing files without warning
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(file_body)
            success_count += 1
                
        # Show success status
        self.lbl_status.config(text=f"✓ Exported {success_count} file(s)", foreground="green")
        self.root.after(4000, lambda: self.lbl_status.config(text=""))

    def on_closing(self):
        """Forces a final save of the currently open document before quitting."""
        self.auto_save_current()
        self.root.destroy()