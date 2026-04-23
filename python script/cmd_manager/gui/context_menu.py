import tkinter as tk
from tkinter import messagebox, simpledialog


class ContextMenuManager:
    def __init__(self, main_window, db):
        self.app = main_window
        self.db = db
        self.tree = main_window.tree
        self.bind_events()

    def bind_events(self):
        self.tree.bind("<Button-3>", self.show_menu)

    def show_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        self.tree.selection_set(item_id)
        node = self.app.node_map[item_id]

        menu = tk.Menu(self.tree, tearoff=0)

        if node["type"] == "group":
            menu.add_command(label="Add Sub-Group", command=lambda: self.add_group(node))
            menu.add_command(label="Add Entry", command=lambda: self.add_element(node))
            menu.add_separator()
            menu.add_command(label="Rename Group", command=lambda: self.rename_node(node))
            if node.get("name") != "Root":
                menu.add_command(label="Delete Group", command=lambda: self.delete_node(node, item_id))

        elif node["type"] == "element":
            menu.add_command(label="Rename Entry", command=lambda: self.rename_node(node))
            menu.add_command(label="Delete Entry", command=lambda: self.delete_node(node, item_id))

        menu.tk_popup(event.x_root, event.y_root)

    def commit_tree_change(self):
        self.app.refresh_tree()
        self.app.update_file_context()
        self.app.persist_current_file(show_message=False)

    def add_group(self, parent_node):
        name = simpledialog.askstring("New Group", "Enter group name:", parent=self.app.root)
        if name:
            new_group = {"type": "group", "name": name.strip(), "children": []}
            parent_node.setdefault("children", []).append(new_group)
            self.commit_tree_change()

    def add_element(self, parent_node):
        name = simpledialog.askstring("New Entry", "Enter entry name:", parent=self.app.root)
        if name:
            new_element = {
                "type": "element",
                "name": name.strip(),
                "command": "",
                "description": "",
            }
            parent_node.setdefault("children", []).append(new_element)
            self.commit_tree_change()

    def rename_node(self, node):
        new_name = simpledialog.askstring(
            "Rename", "Enter new name:", initialvalue=node.get("name", ""), parent=self.app.root
        )
        if new_name:
            node["name"] = new_name.strip()
            self.commit_tree_change()

    def delete_node(self, node, item_id):
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{node.get('name')}'?",
            parent=self.app.root,
        )
        if not confirm:
            return

        parent_id = self.tree.parent(item_id)
        if parent_id:
            parent_node = self.app.node_map[parent_id]
            parent_node["children"].remove(node)
            self.commit_tree_change()
