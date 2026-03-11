import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'playbooks.json')

DEFAULT_DATA = {
    "type": "group",
    "name": "Root",
    "children": []
}

class Database:
    def __init__(self):
        self.data = self.load_data()

    def load_data(self):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
            with open(DATA_FILE, 'w') as f:
                json.dump(DEFAULT_DATA, f, indent=4)
            return DEFAULT_DATA
            
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            with open(DATA_FILE, 'w') as f:
                json.dump(DEFAULT_DATA, f, indent=4)
            return DEFAULT_DATA

    def save_data(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)

    def search(self, keywords):
        if not keywords:
            return self.data

        keywords = keywords.lower().split()
        
        def filter_node(node):
            if node["type"] == "element":
                text_pool = f"{node.get('name', '')} {node.get('content', '')}".lower()
                if all(kw in text_pool for kw in keywords):
                    return node.copy()
                return None
            
            elif node["type"] == "group":
                matched_children = []
                for child in node.get("children", []):
                    result = filter_node(child)
                    if result:
                        matched_children.append(result)
                
                if matched_children:
                    new_group = node.copy()
                    new_group["children"] = matched_children
                    return new_group
                return None

        filtered = filter_node(self.data)
        return filtered if filtered else {"type": "group", "name": "Root", "children": []}