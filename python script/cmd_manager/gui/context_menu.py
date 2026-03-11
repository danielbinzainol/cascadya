import tkinter as tk
from tkinter import simpledialog, messagebox

class ContextMenuManager:
    def __init__(self, main_window, db):
        self.app = main_window
        self.db = db
        self.tree = main_window.tree
        self.bind_events()

    def bind_events(self):
        # Bind right-click (Button-3 on Windows/Linux, sometimes Button-2 on Mac)
        self.tree.bind("<Button-3>", self.show_menu)

    def show_menu(self, event):
        # Find which item was right-clicked
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        # Select the item automatically
        self.tree.selection_set(item_id)
        node = self.app.node_map[item_id]

        # Create the popup menu
        menu = tk.Menu(self.tree, tearoff=0)

        if node["type"] == "group":
            menu.add_command(label="📁 Add Sub-Group", command=lambda: self.add_group(node))
            menu.add_command(label="⚡ Add Command Element", command=lambda: self.add_element(node))
            menu.add_separator()
            menu.add_command(label="✏️ Rename Group", command=lambda: self.rename_node(node))
            if node.get("name") != "Root":  # Prevent deleting the root folder
                menu.add_command(label="🗑️ Delete Group", command=lambda: self.delete_node(node, item_id))
        
        elif node["type"] == "element":
            menu.add_command(label="✏️ Rename Command", command=lambda: self.rename_node(node))
            menu.add_command(label="🗑️ Delete Command", command=lambda: self.delete_node(node, item_id))

        # Display the menu at mouse position
        menu.tk_popup(event.x_root, event.y_root)

    def add_group(self, parent_node):
        name = simpledialog.askstring("New Group", "Enter group name:", parent=self.app.root)
        if name:
            new_group = {"type": "group", "name": name.strip(), "children": []}
            parent_node.setdefault("children", []).append(new_group)
            self.db.save_data()
            self.app.refresh_tree()

    def add_element(self, parent_node):
        name = simpledialog.askstring("New Command", "Enter command name:", parent=self.app.root)
        if name:
            new_element = {
                "type": "element", 
                "name": name.strip(), 
                "command": "# Your command here\n", 
                "description": "Add a description..."
            }
            parent_node.setdefault("children", []).append(new_element)
            self.db.save_data()
            self.app.refresh_tree()

    def rename_node(self, node):
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=node.get("name", ""), parent=self.app.root)
        if new_name:
            node["name"] = new_name.strip()
            self.db.save_data()
            self.app.refresh_tree()

    def delete_node(self, node, item_id):
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{node.get('name')}'?", parent=self.app.root)
        if confirm:
            # Find parent in the tree to remove this child from the data structure
            parent_id = self.tree.parent(item_id)
            if parent_id:
                parent_node = self.app.node_map[parent_id]
                parent_node["children"].remove(node)
                self.db.save_data()
                self.app.refresh_tree()