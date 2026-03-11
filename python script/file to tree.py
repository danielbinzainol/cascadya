import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from pathlib import Path

def generate_tree_structure(path, prefix=""):
    """
    Recursively builds a string representation of the directory tree.
    """
    lines = []
    
    # Get all items in directory, sort them (folders first, then alphabetic)
    try:
        # We look for everything (*) in the path
        items = list(path.iterdir())
        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError:
        return [f"{prefix}└── [ACCESS DENIED]"]

    total_items = len(items)
    
    for index, item in enumerate(items):
        is_last = (index == total_items - 1)
        
        # Define the connectors
        connector = "└── " if is_last else "├── "
        
        # Determine the type label
        if item.is_dir():
            type_label = "[Folder]"
        else:
            # item.suffix gives extension like .txt, or use "File" if no extension
            ext = item.suffix.upper() if item.suffix else "FILE"
            type_label = f"[{ext}]"

        # Build the current line
        line = f"{prefix}{connector}{item.name}  {type_label}"
        lines.append(line)

        # If it is a folder, recurse into it
        if item.is_dir():
            # Prepare the prefix for the children
            extension = "    " if is_last else "│   "
            lines.extend(generate_tree_structure(item, prefix + extension))
            
    return lines

def browse_folder():
    """Open a dialog to select a folder and generate the tree."""
    folder_selected = filedialog.askdirectory()
    
    if folder_selected:
        path = Path(folder_selected)
        
        # Clear previous text
        text_area.delete('1.0', tk.END)
        text_area.insert(tk.END, f"{path.name}  [Root]\n")
        
        # Generate the tree
        try:
            tree_lines = generate_tree_structure(path)
            result = "\n".join(tree_lines)
            text_area.insert(tk.END, result)
        except Exception as e:
            messagebox.showerror("Error", f"Could not generate tree: {e}")

def copy_to_clipboard():
    """Copy the current text content to the system clipboard."""
    content = text_area.get('1.0', tk.END)
    root.clipboard_clear()
    root.clipboard_append(content)
    root.update() # Keeps the clipboard content after window closes
    messagebox.showinfo("Copied", "Tree structure copied to clipboard!")

# --- GUI Setup ---
root = tk.Tk()
root.title("File Tree Generator")
root.geometry("600x500")

# Top Frame for Buttons
button_frame = tk.Frame(root, pady=10)
button_frame.pack(side=tk.TOP, fill=tk.X)

btn_browse = tk.Button(button_frame, text="Select Folder", command=browse_folder, bg="#dddddd", padx=10)
btn_browse.pack(side=tk.LEFT, padx=10)

btn_copy = tk.Button(button_frame, text="Copy Output", command=copy_to_clipboard, bg="#dddddd", padx=10)
btn_copy.pack(side=tk.LEFT, padx=10)

# Text Area with Scrollbar
text_area = scrolledtext.ScrolledText(root, width=70, height=25, font=("Consolas", 10))
text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Start the App
root.mainloop()