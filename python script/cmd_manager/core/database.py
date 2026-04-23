import copy
import json
from json import JSONDecodeError
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DATA_FILE = DATA_DIR / "commands.json"
STATE_FILE = DATA_DIR / "app_state.json"

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
                    "description": "Full workflow to declare vault variables and execute.",
                }
            ],
        }
    ],
}


class DataFileError(Exception):
    def __init__(self, file_path, message):
        super().__init__(message)
        self.file_path = Path(file_path)


class Database:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        self.data_file = self._resolve_startup_file()
        self.data = copy.deepcopy(DEFAULT_DATA)
        self.startup_warning = None
        self._load_startup_data()

    def _coerce_path(self, file_path):
        path = Path(file_path).expanduser()
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path

    def _load_state(self):
        if not STATE_FILE.exists():
            return {}

        try:
            with STATE_FILE.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, JSONDecodeError):
            return {}

        return payload if isinstance(payload, dict) else {}

    def _save_state(self):
        with STATE_FILE.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(self.state, handle, indent=4, ensure_ascii=False)

    def _resolve_startup_file(self):
        saved_path = self.state.get("last_opened_file")
        if saved_path:
            candidate = self._coerce_path(saved_path)
            if candidate.exists():
                return candidate

        return DEFAULT_DATA_FILE

    def _set_current_file(self, file_path):
        self.data_file = self._coerce_path(file_path)
        self.state["last_opened_file"] = str(self.data_file)
        self._save_state()

    def _write_json(self, file_path, payload):
        file_path = self._coerce_path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=4, ensure_ascii=False)

    def _normalize_node(self, node, file_path):
        if not isinstance(node, dict):
            raise DataFileError(file_path, "Each node must be a JSON object.")

        node_type = node.get("type")
        name = str(node.get("name", "Untitled")).strip() or "Untitled"
        normalized = dict(node)
        normalized["name"] = name

        if node_type == "group":
            children = node.get("children", [])
            if children is None:
                children = []
            if not isinstance(children, list):
                raise DataFileError(file_path, f"Group '{name}' has an invalid 'children' value.")
            normalized["type"] = "group"
            normalized["children"] = [self._normalize_node(child, file_path) for child in children]
            return normalized

        if node_type == "element":
            content = node.get("command")
            if content is None:
                content = node.get("content", "")

            description = node.get("description")
            if description is None:
                description = node.get("details", "")

            normalized["type"] = "element"
            normalized["command"] = str(content or "")
            normalized["description"] = str(description or "")
            return normalized

        raise DataFileError(file_path, f"Node '{name}' has unsupported type '{node_type}'.")

    def _load_data_file(self, file_path, create_if_missing=False):
        file_path = self._coerce_path(file_path)

        if not file_path.exists():
            if create_if_missing:
                payload = copy.deepcopy(DEFAULT_DATA)
                self._write_json(file_path, payload)
                return payload
            raise DataFileError(file_path, "The file does not exist.")

        try:
            raw_text = file_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise DataFileError(file_path, f"Could not read the file: {exc}") from exc

        if not raw_text.strip():
            raise DataFileError(file_path, "The file is empty.")

        try:
            payload = json.loads(raw_text)
        except JSONDecodeError as exc:
            message = f"Invalid JSON at line {exc.lineno}, column {exc.colno}."
            raise DataFileError(file_path, message) from exc

        if not isinstance(payload, dict):
            raise DataFileError(file_path, "The root JSON value must be an object.")

        normalized = self._normalize_node(payload, file_path)
        if normalized.get("type") != "group":
            raise DataFileError(file_path, "The root node must be a group.")

        return normalized

    def _load_startup_data(self):
        startup_file = self.data_file
        create_default = startup_file == DEFAULT_DATA_FILE

        try:
            self.data = self._load_data_file(startup_file, create_if_missing=create_default)
            self._set_current_file(startup_file)
        except DataFileError as exc:
            self.startup_warning = (
                f"Could not load:\n{exc.file_path}\n\n"
                f"Reason: {exc}\n\n"
                "The original file was left unchanged. The app loaded the default repertoire instead."
            )
            self.data = copy.deepcopy(DEFAULT_DATA)
            if not DEFAULT_DATA_FILE.exists():
                self._write_json(DEFAULT_DATA_FILE, self.data)
            self._set_current_file(DEFAULT_DATA_FILE)

    def open_data_file(self, file_path):
        target = self._coerce_path(file_path)
        self.data = self._load_data_file(target)
        self._set_current_file(target)

    def save_as(self, file_path):
        target = self._coerce_path(file_path)
        self._write_json(target, self.data)
        self._set_current_file(target)

    def save_data(self):
        self._write_json(self.data_file, self.data)
        self._set_current_file(self.data_file)

    def search(self, keywords):
        """Recursively searches elements based on command and description."""
        if not keywords:
            return self.data

        keywords = keywords.lower().split()

        def filter_node(node):
            if node["type"] == "element":
                text_pool = (
                    f"{node.get('name', '')} "
                    f"{node.get('command', '')} "
                    f"{node.get('description', '')}"
                ).lower()
                if all(kw in text_pool for kw in keywords):
                    result = node.copy()
                    result["_source"] = node
                    return result
                return None

            matched_children = []
            for child in node.get("children", []):
                result = filter_node(child)
                if result:
                    matched_children.append(result)

            if matched_children:
                new_group = node.copy()
                new_group["children"] = matched_children
                new_group["_source"] = node
                return new_group
            return None

        filtered_data = filter_node(self.data)
        return filtered_data if filtered_data else {"type": "group", "name": "Root", "children": []}
