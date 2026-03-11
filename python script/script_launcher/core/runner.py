import subprocess
import platform
import os

class ScriptRunner:
    @staticmethod
    def launch(file_path, args_string=""):
        """Launches a python script in a new terminal window based on the OS."""
        if not os.path.exists(file_path) or not file_path.endswith('.py'):
            raise ValueError("Invalid file. Must be a .py script.")

        # Split arguments if any exist
        args_list = args_string.split() if args_string else []
        
        system = platform.system()

        try:
            if system == "Windows":
                # Opens a new cmd window and runs Python
                cmd = ["python", file_path] + args_list
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                
            elif system == "Darwin":  # macOS
                args_joined = " ".join(args_list)
                apple_script = f'tell app "Terminal" to do script "python3 \\"{file_path}\\" {args_joined}"'
                subprocess.Popen(["osascript", "-e", apple_script])
                
            else:  # Linux 
                terminals = ["gnome-terminal", "x-terminal-emulator", "konsole", "xfce4-terminal"]
                for term in terminals:
                    if subprocess.call(["which", term], stdout=subprocess.PIPE) == 0:
                        subprocess.Popen([term, "--", "bash", "-c", f"python3 '{file_path}' {' '.join(args_list)}; exec bash"])
                        return
                raise OSError("Could not find a suitable terminal emulator on Linux.")
                
        except Exception as e:
            raise RuntimeError(f"Failed to launch script: {str(e)}")