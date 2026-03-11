import tkinter as tk
from tkinter import simpledialog, messagebox

class ContextMenuManager:
    def __init__(self, main_window, db):
        self.app = main_window
        self.db = db
        self.tree = main_window.tree
        # Bind right-click (Button-3 on Windows)
        self.tree.bind("<Button-3>", self.show_menu)

    def show_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        menu = tk.Menu(self.tree, tearoff=0)

        # --- THE FIX: If you click the empty white space ---
        if not item_id:
            menu.add_command(label="📁 Add Main Folder", command=lambda: self.add_group(self.db.data))
            menu.add_command(label="📚 Add Playbook Template", command=lambda: self.add_playbook_template(self.db.data))
            menu.tk_popup(event.x_root, event.y_root)
            return
            
        # --- If you clicked on an actual item ---
        self.tree.selection_set(item_id)
        node = self.app.node_map[item_id]

        if node["type"] == "group":
            menu.add_command(label="📁 Add Sub-Folder", command=lambda: self.add_group(node))
            menu.add_command(label="📚 Add Playbook Template", command=lambda: self.add_playbook_template(node))
            menu.add_separator()
            menu.add_command(label="📄 Add Blank Document", command=lambda: self.add_element(node))
            menu.add_separator()
            menu.add_command(label="✏️ Rename", command=lambda: self.rename_node(node))
            menu.add_command(label="🗑️ Delete", command=lambda: self.delete_node(node, item_id))
        
        elif node["type"] == "element":
            menu.add_command(label="✏️ Rename Document", command=lambda: self.rename_node(node))
            menu.add_command(label="🗑️ Delete Document", command=lambda: self.delete_node(node, item_id))

        menu.tk_popup(event.x_root, event.y_root)

    def add_playbook_template(self, parent_node):
        """Auto-generates a playbook folder with Description and Repo children."""
        name = simpledialog.askstring("New Playbook", "Enter Playbook Name:", parent=self.app.root)
        if name:
            new_playbook = {
                "type": "group", 
                "name": name.strip(), 
                "children": [
                    {
                        "type": "element",
                        "name": "Description",
                        "content": "### Playbook Objective\n\n### Containers Managed\n- \n\n### Expected Results\n"
                    },
                    {
                        "type": "element",
                        "name": "Repo Structure",
                        "content": "Paste your tree output or repository files here:\n\n```text\n\n```"
                    }
                ]
            }
            parent_node.setdefault("children", []).append(new_playbook)
            self.db.save_data()
            self.app.refresh_tree()

    def add_group(self, parent_node):
        name = simpledialog.askstring("New Folder", "Enter folder name:", parent=self.app.root)
        if name:
            parent_node.setdefault("children", []).append({"type": "group", "name": name.strip(), "children": []})
            self.db.save_data()
            self.app.refresh_tree()

    def add_element(self, parent_node):
        name = simpledialog.askstring("New Document", "Enter document name:", parent=self.app.root)
        if name:
            parent_node.setdefault("children", []).append({"type": "element", "name": name.strip(), "content": ""})
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
            # Find the parent in the tree so we can remove this child from the data
            parent_id = self.tree.parent(item_id)
            parent_node = self.app.node_map.get(parent_id, self.db.data)
            
            if node in parent_node.get("children", []):
                parent_node["children"].remove(node)
                self.db.save_data()
                self.app.refresh_tree()
                
                # Safety: clear the text editor if the deleted item was currently open
                if self.app.current_node_id == item_id:
                    self.app.text_content.delete("1.0", tk.END)
                    self.app.lbl_title.config(text="Select a document")
                    self.app.current_node_id = None