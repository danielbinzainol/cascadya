import re
import keyword

class PythonHighlighter:
    def __init__(self, text_widget):
        self.text = text_widget
        self.setup_tags()
        
        # We use a debounce job so highlighting doesn't lag while typing fast
        self._highlight_job = None
        
        # Trigger highlighting whenever text changes
        self.text.bind("<<Change>>", self.schedule_highlight, add="+")

    def setup_tags(self):
        # Define the color palette
        self.text.tag_configure("Keyword", foreground="#0000FF", font=("Consolas", 11, "bold"))
        self.text.tag_configure("Def", foreground="#795E26", font=("Consolas", 11, "bold"))
        self.text.tag_configure("String", foreground="#A31515")
        self.text.tag_configure("Comment", foreground="#008000", font=("Consolas", 11, "italic"))
        
        # Priority order (Comments override strings, Strings override keywords, etc.)
        self.text.tag_raise("Keyword")
        self.text.tag_raise("Def")
        self.text.tag_raise("String")
        self.text.tag_raise("Comment")

    def schedule_highlight(self, event=None):
        if self._highlight_job:
            self.text.after_cancel(self._highlight_job)
        # Wait 300ms after the user stops typing to apply colors
        self._highlight_job = self.text.after(300, self.highlight)

    def highlight(self):
        content = self.text.get("1.0", "end-1c")
        
        # Skip highlighting if the file is massive (prevents GUI freezing)
        if len(content) > 100000: return 

        # 1. Clear existing tags
        for tag in ["Keyword", "Def", "String", "Comment"]:
            self.text.tag_remove(tag, "1.0", "end")
            
        # 2. Keywords (import, class, if, return, etc.)
        kw_pattern = r'\b(' + '|'.join(keyword.kwlist) + r')\b'
        for match in re.finditer(kw_pattern, content):
            self.text.tag_add("Keyword", f"1.0 + {match.start()}c", f"1.0 + {match.end()}c")
            
        # 3. Function and Class names
        def_pattern = r'\b(?:def|class)\s+([a-zA-Z0-9_]+)'
        for match in re.finditer(def_pattern, content):
            self.text.tag_add("Def", f"1.0 + {match.start(1)}c", f"1.0 + {match.end(1)}c")

        # 4. Strings ("" and '')
        for match in re.finditer(r'r?\"([^\\\n]|(\\.))*?\"|r?\'([^\\\n]|(\\.))*?\'', content):
            self.text.tag_add("String", f"1.0 + {match.start()}c", f"1.0 + {match.end()}c")

        # 5. Comments (starts with #)
        for match in re.finditer(r'#.*', content):
            self.text.tag_add("Comment", f"1.0 + {match.start()}c", f"1.0 + {match.end()}c")