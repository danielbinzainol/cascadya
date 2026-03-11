import os

class FileHandler:
    @staticmethod
    def read_file(file_path):
        """Reads a file safely, replacing unknown binary characters."""
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    @staticmethod
    def save_file(file_path, content):
        """Writes content to a file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    @staticmethod
    def create_file(file_path):
        """Creates an empty file if it doesn't already exist."""
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("") # Create empty file
        else:
            raise FileExistsError("A file with this name already exists.")

    @staticmethod
    def create_folder(folder_path):
        """Creates a directory if it doesn't already exist."""
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        else:
            raise FileExistsError("A folder with this name already exists.")