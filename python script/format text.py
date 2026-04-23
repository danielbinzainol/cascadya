import tkinter as tk

def nettoyer_texte():
    # "end-1c" permet de ne pas récupérer le saut de ligne fantôme ajouté par Tkinter
    texte_brut = zone_texte.get("1.0", "end-1c")
    
    # On sépare par ligne et on garde uniquement celles qui ne sont pas vides
    lignes_propres = [ligne for ligne in texte_brut.split('\n') if ligne.strip()]
    
    # On rassemble le tout
    texte_final = '\n'.join(lignes_propres)
    
    # On efface et on remplace par le résultat copiable
    zone_texte.delete("1.0", tk.END)
    zone_texte.insert("1.0", texte_final)

# --- Création de l'interface ---
fenetre = tk.Tk()
fenetre.title("Nettoyeur de lignes")
fenetre.geometry("450x350") # Taille compacte

# Zone de texte (Entrée et Sortie combinées)
zone_texte = tk.Text(fenetre, wrap=tk.WORD, font=("Consolas", 10))
zone_texte.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

# Bouton d'action
bouton = tk.Button(fenetre, text="Supprimer les lignes vides", command=nettoyer_texte, bg="#f0f0f0")
bouton.pack(pady=(0, 10))

# Lancement de l'application
fenetre.mainloop()