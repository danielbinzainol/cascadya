import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'commands.json')

# Default nested structure
DEFAULT_DATA = {
    "type": "group",
    "name": "Root",
    "children": [
        {
            "type": "group",
            "name": "Ansible",
            "children": [
                {
                    "type": "element",
                    "name": "Playbook with Vault",
                    "command": "export VAULT_TOKEN=<token>\nansible-playbook playbook.yml",
                    "description": "Full workflow to declare vault variables and execute."
                }
            ]
        }
    ]
}

class Database:
    def __init__(self):
        self.data = self.load_data()

    def load_data(self):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        # If the file doesn't exist OR is completely empty (0 bytes)
        if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
            with open(DATA_FILE, 'w') as f:
                json.dump(DEFAULT_DATA, f, indent=4)
            return DEFAULT_DATA
            
        # Try to read it, but catch the error if the JSON is corrupted
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Warning: commands.json was corrupted. Resetting to defaults.")
            with open(DATA_FILE, 'w') as f:
                json.dump(DEFAULT_DATA, f, indent=4)
            return DEFAULT_DATA

    def save_data(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)

    def search(self, keywords):
        """Recursively searches elements based on command AND description."""
        if not keywords:
            return self.data

        keywords = keywords.lower().split()
        
        def filter_node(node):
            if node["type"] == "element":
                text_pool = f"{node.get('name', '')} {node.get('command', '')} {node.get('description', '')}".lower()
                # Element matches if ALL keywords are found
                if all(kw in text_pool for kw in keywords):
                    return node.copy()
                return None
            
            elif node["type"] == "group":
                matched_children = []
                for child in node.get("children", []):
                    result = filter_node(child)
                    if result:
                        matched_children.append(result)
                
                # If a group has matching children, keep the group
                if matched_children:
                    new_group = node.copy()
                    new_group["children"] = matched_children
                    return new_group
                return None

        filtered_data = filter_node(self.data)
        return filtered_data if filtered_data else {"type": "group", "name": "Root", "children": []}