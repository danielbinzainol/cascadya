import tkinter as tk
from gui.syntax import PythonHighlighter

class LineNumberCanvas(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.text_widget = None

    def attach(self, text_widget):
        self.text_widget = text_widget

    def redraw(self, *args):
        """Redraws the line numbers based on the visible text in the widget."""
        self.delete("all")
        
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None: 
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, font=("Consolas", 11), fill="#888888")
            i = self.text_widget.index(f"{i}+1line")

class CustomText(tk.Text):
    """A Text widget that triggers an event whenever its content or scroll changes."""
    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, *args):
        cmd = (self._orig,) + args
        try:
            result = self.tk.call(cmd)
        except tk.TclError:
            return None

        # Generate event if text is modified or scrolled
        if (args[0] in ("insert", "replace", "delete") or 
            args[0:3] == ("mark", "set", "insert") or
            args[0:2] in (("xview", "moveto"), ("xview", "scroll"), ("yview", "moveto"), ("yview", "scroll"))):
            self.event_generate("<<Change>>", when="tail")
            
        return result

class EditorWithLineNumbers(tk.Frame):
    """A composite widget containing the Text area and the Line Number Canvas."""
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        
        self.text = CustomText(self, undo=True, wrap="none", font=("Consolas", 11), bg="#fdfdfd")
        self.linenumbers = LineNumberCanvas(self, width=40, bg="#f0f0f0", highlightthickness=0)
        self.linenumbers.attach(self.text)

        # Pack line numbers on the left, text on the right
        self.linenumbers.pack(side="left", fill="y")
        self.text.pack(side="right", fill="both", expand=True)

        self.text.bind("<<Change>>", self._on_change)
        self.text.bind("<Configure>", self._on_change)

        self.highlighter = PythonHighlighter(self.text)

    def _on_change(self, event):
        self.linenumbers.redraw()
        
    def get_text(self):
        return self.text.get("1.0", "end-1c")
        
    def set_text(self, content):
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, content)