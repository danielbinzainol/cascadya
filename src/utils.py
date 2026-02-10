import yaml
from pathlib import Path

def load_config():
    config_path = Path(__file__).resolve().parent.parent / "config.yml"  # uses src/config.yml
    with config_path.open("r", encoding='utf-8') as file:
        config = yaml.safe_load(file)
        return config