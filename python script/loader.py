import tkinter as tk
import math
import colorsys

class FloatingLoader:
    def __init__(self, root):
        self.root = root
        
        # --- Transparency Setup ---
        # We pick a color to act as our "green screen". 
        self.transparent_color = "black" 
        
        # --- Window Properties ---
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"100x100+{screen_width - 150}+50") 
        
        self.root.overrideredirect(True)      
        self.root.attributes("-topmost", True)  
        
        # THIS is the magic Windows trick for transparency:
        self.root.attributes("-transparentcolor", self.transparent_color)
        self.root.configure(bg=self.transparent_color)

        # --- Canvas Setup ---
        # The canvas background MUST match the transparent_color
        self.canvas = tk.Canvas(root, width=100, height=100, bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack()

        # --- Animation Variables ---
        self.num_particles = 10
        self.center_x = 50
        self.center_y = 50
        self.radius = 30
        self.base_particle_size = 3
        self.angle_offset = 0.0
        
        self.particles = []
        for _ in range(self.num_particles):
            p = self.canvas.create_oval(0, 0, 0, 0, fill="white", outline="")
            self.particles.append(p)

        # --- Mouse Bindings ---
        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<Button-3>", self.close_app) 

        self.animate()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def close_app(self, event):
        self.root.destroy()

    def animate(self):
        self.angle_offset += 0.06 
        
        for i, p in enumerate(self.particles):
            angle = (i / self.num_particles) * (2 * math.pi) + self.angle_offset
            
            x = self.center_x + math.cos(angle) * self.radius
            y = self.center_y + math.sin(angle) * self.radius
            
            hue = (i / self.num_particles + self.angle_offset / (2 * math.pi)) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
            color_hex = f'#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}'

            pulse = (math.sin(angle) + 1) / 2 
            current_size = self.base_particle_size + (pulse * 4)

            self.canvas.coords(p, x - current_size, y - current_size, x + current_size, y + current_size)
            self.canvas.itemconfig(p, fill=color_hex)

        self.root.after(30, self.animate)

if __name__ == "__main__":
    root = tk.Tk()
    app = FloatingLoader(root)
    root.mainloop()