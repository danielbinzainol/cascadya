import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gui.context_menu import ContextMenuManager


class MainWindow:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.node_map = {}

        self.build_ui()
        self.refresh_tree()
        self.context_menu = ContextMenuManager(self, self.db)
        self.update_file_context()

        self.root.bind("<Control-s>", self.save_current_edits)
        self.root.bind("<Control-S>", self.save_current_edits)
        self.root.bind("<Control-o>", self.open_data_file)
        self.root.bind("<Control-O>", self.open_data_file)

        if self.db.startup_warning:
            self.root.after(
                0,
                lambda: messagebox.showwarning(
                    "Data File Warning", self.db.startup_warning, parent=self.root
                ),
            )

    def build_ui(self):
        self.root.geometry("1000x700")

        file_frame = ttk.Frame(self.root, padding="10")
        file_frame.pack(fill=tk.X)

        ttk.Button(file_frame, text="Open JSON", command=self.open_data_file).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="Save", command=self.save_current_edits).pack(
            side=tk.LEFT, padx=(10, 0)
        )
        ttk.Button(file_frame, text="Save As", command=self.save_data_as).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        self.file_label_var = tk.StringVar()
        ttk.Label(file_frame, textvariable=self.file_label_var).pack(
            side=tk.LEFT, padx=(15, 0), fill=tk.X, expand=True
        )

        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)

        ttk.Label(search_frame, text="Search (matches name, content, notes):").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search)
        ttk.Entry(search_frame, textvariable=self.search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=10
        )

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=1)

        self.tree = ttk.Treeview(tree_frame, show="tree")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        detail_frame = ttk.Frame(paned)
        paned.add(detail_frame, weight=3)

        self.lbl_title = ttk.Label(detail_frame, text="Select an entry", font=("Arial", 14, "bold"))
        self.lbl_title.pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(detail_frame, text="Primary Content / Workflow:", font=("Arial", 10, "bold")).pack(
            anchor=tk.W
        )
        self.text_cmd = tk.Text(detail_frame, height=12, font=("Consolas", 11), bg="#f4f4f4")
        self.text_cmd.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Button(detail_frame, text="Copy Content", command=self.copy_command).pack(
            anchor=tk.W, pady=(0, 10)
        )

        btn_frame = ttk.Frame(detail_frame)
        btn_frame.pack(anchor=tk.W, pady=(0, 10))

        ttk.Button(btn_frame, text="Save File", command=self.save_current_edits).pack(side=tk.LEFT)

        self.save_msg_label = tk.Label(btn_frame, text="", fg="green", font=("Arial", 10))
        self.save_msg_label.pack(side=tk.LEFT, padx=10)

        ttk.Label(detail_frame, text="Description / Notes:", font=("Arial", 10, "bold")).pack(
            anchor=tk.W
        )
        self.text_desc = tk.Text(detail_frame, height=8, font=("Arial", 11), bg="#ffffff")
        self.text_desc.pack(fill=tk.BOTH, expand=True)

    def update_file_context(self):
        self.root.title(f"Modular Command Manager - {self.db.data_file.name}")
        self.file_label_var.set(f"Active JSON: {self.db.data_file}")

    def show_status_message(self, text, color="green"):
        self.save_msg_label.config(text=text, fg=color)
        self.root.after(2500, self.clear_save_message)

    def clear_save_message(self):
        self.save_msg_label.config(text="")

    def get_text_value(self, widget):
        return widget.get("1.0", tk.END).rstrip("\n")

    def sync_selected_edits_to_memory(self):
        selected = self.tree.selection()
        if not selected:
            return False

        node = self.node_map.get(selected[0])
        if not node or node["type"] != "element":
            return False

        node["command"] = self.get_text_value(self.text_cmd)
        node["description"] = self.get_text_value(self.text_desc)
        return True

    def has_unsaved_selected_edits(self):
        selected = self.tree.selection()
        if not selected:
            return False

        node = self.node_map.get(selected[0])
        if not node or node["type"] != "element":
            return False

        return (
            self.get_text_value(self.text_cmd) != node.get("command", "")
            or self.get_text_value(self.text_desc) != node.get("description", "")
        )

    def confirm_pending_edits(self):
        if not self.has_unsaved_selected_edits():
            return True

        choice = messagebox.askyesnocancel(
            "Unsaved Changes",
            "Save the current file before opening another JSON?",
            parent=self.root,
        )
        if choice is None:
            return False

        if choice:
            self.sync_selected_edits_to_memory()
            return self.persist_current_file(show_message=False)

        return True

    def persist_current_file(self, show_message=True):
        try:
            self.db.save_data()
        except OSError as exc:
            messagebox.showerror(
                "Save Failed",
                f"Could not save this file:\n{self.db.data_file}\n\n{exc}",
                parent=self.root,
            )
            return False

        self.update_file_context()
        if show_message:
            self.show_status_message("Saved successfully")
        return True

    def populate_tree(self, node, parent_id=""):
        node_id = str(id(node))
        source_node = node.get("_source", node)
        self.node_map[node_id] = source_node

        icon = "[Group] " if node["type"] == "group" else "[Item] "
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

        display_data = data if data else self.db.data
        self.populate_tree(display_data)

    def clear_detail_fields(self):
        self.lbl_title.config(text="Select an entry")
        self.text_cmd.delete("1.0", tk.END)
        self.text_desc.delete("1.0", tk.END)

    def on_search(self, *args):
        keyword = self.search_var.get()
        filtered_data = self.db.search(keyword)
        self.refresh_tree(filtered_data)
        self.clear_detail_fields()

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        node = self.node_map[selected[0]]
        self.lbl_title.config(text=node.get("name", ""))

        self.text_cmd.delete("1.0", tk.END)
        self.text_desc.delete("1.0", tk.END)

        if node["type"] == "element":
            self.text_cmd.insert(tk.END, node.get("command", ""))
            self.text_desc.insert(tk.END, node.get("description", ""))

    def copy_command(self):
        content = self.get_text_value(self.text_cmd)
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)

    def open_data_file(self, event=None):
        if not self.confirm_pending_edits():
            return "break" if event else None

        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Open JSON repertoire",
            initialdir=str(self.db.data_file.parent),
            initialfile=self.db.data_file.name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return "break" if event else None

        try:
            self.db.open_data_file(file_path)
        except Exception as exc:
            messagebox.showerror(
                "Open Failed",
                f"Could not open this file:\n{file_path}\n\n{exc}",
                parent=self.root,
            )
            return "break" if event else None

        self.search_var.set("")
        self.refresh_tree()
        self.clear_detail_fields()
        self.update_file_context()
        self.show_status_message(f"Opened {self.db.data_file.name}")
        return "break" if event else None

    def save_data_as(self):
        self.sync_selected_edits_to_memory()

        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save JSON repertoire as",
            initialdir=str(self.db.data_file.parent),
            initialfile=self.db.data_file.name,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            self.db.save_as(file_path)
        except OSError as exc:
            messagebox.showerror(
                "Save Failed",
                f"Could not save this file:\n{file_path}\n\n{exc}",
                parent=self.root,
            )
            return

        self.update_file_context()
        self.show_status_message(f"Saved as {self.db.data_file.name}")

    def save_current_edits(self, event=None):
        self.sync_selected_edits_to_memory()
        self.persist_current_file()
        return "break"
