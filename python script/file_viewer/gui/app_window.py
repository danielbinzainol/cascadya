import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from core.file_handler import FileHandler
from gui.line_text import EditorWithLineNumbers

class FileQuickViewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Quick-Look Explorer")
        self.root.geometry("1200x800")
        
        self.current_file = None
        self.current_workspace = None
        self.is_dirty = False
        self.is_loading = False
        
        self.build_ui()
        self.setup_context_menu()
        
        # Bindings
        self.root.bind("<Control-s>", self.save_file)
        self.root.bind("<Control-o>", self.load_directory)
        self.editor.text.bind("<Control-s>", self.save_file)
        self.editor.text.bind("<<Change>>", self.on_text_change, add="+")

    def build_ui(self):
        toolbar = ttk.Frame(self.root, padding="5")
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(toolbar, text="📁 Open Folder (Ctrl+O)", command=self.load_directory).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="💾 Save Changes (Ctrl+S)", command=self.save_file).pack(side=tk.LEFT, padx=5)
        # --- NEW: Sync Button ---
        ttk.Button(toolbar, text="🔄 Sync", command=self.sync_tree).pack(side=tk.RIGHT, padx=5)

        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree_frame = ttk.Frame(self.paned)
        self.paned.add(tree_frame, weight=1)

        self.tree = ttk.Treeview(tree_frame, show="tree")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self.on_file_select)
        self.tree.bind("<<TreeviewOpen>>", self.on_folder_extend)

        edit_frame = ttk.Frame(self.paned)
        self.paned.add(edit_frame, weight=3)

        self.editor = EditorWithLineNumbers(edit_frame)
        self.editor.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=2)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ==========================================
    # WORKSPACE & TREE LOGIC
    # ==========================================
    def load_directory(self, event=None):
        path = filedialog.askdirectory()
        if not path: return
        self.current_workspace = path
        self.sync_tree()

    def sync_tree(self):
        """Refreshes the tree view from the current workspace folder."""
        if not self.current_workspace: return
        self.tree.delete(*self.tree.get_children())
        node = self.tree.insert("", "end", text=os.path.basename(self.current_workspace), values=[self.current_workspace], open=True)
        self.fill_tree(node, self.current_workspace)
        self.status_var.set(f"Loaded workspace: {self.current_workspace}")

    def fill_tree(self, parent, path):
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            for entry in items:
                if entry in ["__pycache__", "__init__.py"] or entry.endswith(".pyc"):
                    continue

                full_path = os.path.join(path, entry)
                is_dir = os.path.isdir(full_path)
                
                icon = "📁 " if is_dir else "📄 "
                node = self.tree.insert(parent, "end", text=f"{icon}{entry}", values=[full_path])
                
                if is_dir:
                    self.tree.insert(node, "end", text="dummy")
        except PermissionError:
            pass

    def on_folder_extend(self, event):
        node = self.tree.focus()
        path = self.tree.item(node, "values")[0]
        
        children = self.tree.get_children(node)
        if len(children) == 1 and self.tree.item(children[0], "text") == "dummy":
            self.tree.delete(children[0])
            self.fill_tree(node, path)

    # ==========================================
    # CONTEXT MENU LOGIC (NEW FILES / FOLDERS)
    # ==========================================
    def setup_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="📄 New File", command=self.action_new_file)
        self.context_menu.add_command(label="📁 New Folder", command=self.action_new_folder)
        
        # Bind right-click
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        if not self.current_workspace: return
        
        # Highlight the row the user right-clicked on
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def get_selected_dir(self):
        """Determines the target folder based on what is selected."""
        selection = self.tree.selection()
        if not selection: 
            return self.current_workspace
            
        path = self.tree.item(selection[0], "values")[0]
        if os.path.isdir(path):
            return path
        return os.path.dirname(path) # If a file is clicked, use its parent folder

    def action_new_file(self):
        target_dir = self.get_selected_dir()
        filename = simpledialog.askstring("New File", "Enter file name with extension (e.g., config.yaml):", parent=self.root)
        if filename:
            full_path = os.path.join(target_dir, filename.strip())
            try:
                FileHandler.create_file(full_path)
                self.sync_tree()
                self.status_var.set(f"Created file: {filename}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def action_new_folder(self):
        target_dir = self.get_selected_dir()
        foldername = simpledialog.askstring("New Folder", "Enter folder name:", parent=self.root)
        if foldername:
            full_path = os.path.join(target_dir, foldername.strip())
            try:
                FileHandler.create_folder(full_path)
                self.sync_tree()
                self.status_var.set(f"Created folder: {foldername}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ==========================================
    # EDITOR LOGIC
    # ==========================================
    def on_file_select(self, event):
        selection = self.tree.selection()
        if not selection: return
        
        file_path = self.tree.item(selection[0], "values")[0]

        if os.path.isfile(file_path):
            # --- NEW: Silent Auto-Save ---
            # If we have unsaved changes and are switching to a different file, save silently
            if self.is_dirty and self.current_file and self.current_file != file_path:
                self.save_file()
                
            try:
                content = FileHandler.read_file(file_path)
                
                self.is_loading = True
                self.editor.set_text(content)
                self.current_file = file_path
                self.is_loading = False
                self.is_dirty = False
                
                filename = os.path.basename(self.current_file)
                self.status_var.set(f"Editing: {file_path}")
                self.root.title(f"Python Quick-Look Explorer - {filename}")
                
                # Highlight immediately
                self.editor.highlighter.highlight()
                
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file:\n{e}")

    def on_text_change(self, event=None):
        if not self.is_loading and not self.is_dirty and self.current_file:
            self.is_dirty = True
            filename = os.path.basename(self.current_file)
            self.status_var.set(f"* Editing: {self.current_file}")
            self.root.title(f"* {filename} - Python Quick-Look Explorer")

    def save_file(self, event=None):
        if not self.current_file: return "break"
            
        try:
            content = self.editor.get_text()
            FileHandler.save_file(self.current_file, content)
            
            self.is_dirty = False
            filename = os.path.basename(self.current_file)
            self.status_var.set(f"✓ Saved: {self.current_file}")
            self.root.title(f"Python Quick-Look Explorer - {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")
            
        return "break"