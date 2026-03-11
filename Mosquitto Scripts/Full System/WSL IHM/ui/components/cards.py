import customtkinter as ctk

class DataCard(ctk.CTkFrame):
    def __init__(self, master, title, unit="", icon="📊", **kwargs):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=12, **kwargs)
        
        # Titre avec icône
        self.label_title = ctk.CTkLabel(self, text=f"{icon} {title}", 
                                        font=("Arial", 13, "bold"), text_color="gray")
        self.label_title.pack(pady=(10, 0), padx=15, anchor="w")

        # Conteneur pour la valeur et l'unité
        self.val_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.val_frame.pack(expand=True, fill="both", padx=15)

        self.label_value = ctk.CTkLabel(self.val_frame, text="---", 
                                        font=("Arial", 32, "bold"), text_color="#1f538d")
        self.label_value.pack(side="left")

        self.label_unit = ctk.CTkLabel(self.val_frame, text=unit, 
                                       font=("Arial", 14), text_color="gray")
        self.label_unit.pack(side="left", padx=5, pady=(10, 0))

    def update_value(self, value, color=None):
        """Met à jour le texte affiché et optionnellement la couleur"""
        self.label_value.configure(text=str(value))
        if color:
            self.label_value.configure(text_color=color)