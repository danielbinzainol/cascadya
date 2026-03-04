================================================================================
FICHIER : debian-final.pkr.hcl
ROLE    : Configuration, Scripts "Zero Touch" et Livraison
FREQ    : Fréquente (Plusieurs fois par jour en développement)
DUREE   : ~2 à 5 minutes
================================================================================

[DESCRIPTION]
Ce fichier est le laboratoire de développement. Il ne réinstalle PAS Debian.
Il prend une COPIE de l'image de base (générée à l'étape précédente), la démarre,
et applique nos personnalisations par dessus.

[POURQUOI CETTE ÉTAPE ?]
C'est ici que nous testons Ansible et les scripts d'industrialisation.
Comme l'OS est déjà installé, le démarrage prend quelques secondes, ce qui permet
des itérations très rapides pour corriger les bugs.

[ACTIONS EFFECTUÉES]
1. Source :
   - Ne télécharge rien. Utilise le fichier local "output-debian-base/debian-base.img".
   
2. Provisioning (Configuration) :
   - Installe Ansible (apt-get install ansible).
   - Lance le Playbook "ansible/site.yml" (Configuration Docker, etc.).
     > Note : Ansible n'a plus besoin de mot de passe sudo grâce à l'étape Base.
     
3. Injection "Zero Touch" :
   - Copie le script "scripts/install-to-disk.sh" (Smart Clone).
   - Active le service systemd "install-mode.service".
   
4. Nettoyage :
   - Désinstalle Ansible et vide les logs pour livrer une image la plus légère possible.

[ET APRÈS ?]
L'image générée ici ("cascadya-v1.img") est prête à être flashée sur clé USB
pour installation.
Pour l'intégration Mender (OTA), cette image devra passer par l'outil "mender-convert"
dans une étape ultérieure (Post-Process).

[SORTIE]
Génère le dossier : output-final/
Contient le fichier : cascadya-v1.img (Image de production).

[COMMANDE POUR LANCER]
.\packer build -var-file="packer/variables.pkr.hcl" packer/debian-final.pkr.hcl