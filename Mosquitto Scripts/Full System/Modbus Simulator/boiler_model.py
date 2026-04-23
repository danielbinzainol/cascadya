import time

class BoilerState:
    """Enumération des états de la chaudière (format entier pour Modbus)"""
    OFF = 0
    PURGING = 1
    IGNITING = 2
    RUNNING = 3
    COOLDOWN = 4
    FAULT = 99

class Boiler:
    def __init__(self, boiler_id, max_power_kw, ramp_rate=2.0):
        """
        Initialise une chaudière industrielle (IBC).
        
        :param boiler_id: ID unique de la chaudière (ex: 1, 2, 3)
        :param max_power_kw: Puissance maximale en kW (ex: 400, 1000)
        :param ramp_rate: Vitesse de montée en charge (% par seconde)
        """
        self.id = boiler_id
        self.max_power_kw = max_power_kw
        self.ramp_rate = ramp_rate  # Inertie thermique
        
        # Variables d'état
        self.state = BoilerState.OFF
        self.current_load = 0.0      # Charge actuelle (0 à 100%)
        self.target_load = 0.0       # Consigne demandée par le SBC (0 à 100%)
        
        # Timers pour les transitions d'état
        self.state_timer = 0.0       # Chrono interne de l'état en cours
        self.last_update_time = time.time()
        
        # Délais de sécurité simulés (en secondes)
        self.PURGE_TIME = 5.0
        self.IGNITE_TIME = 3.0
        self.COOLDOWN_TIME = 5.0

    def set_target_load(self, load_percent):
        """Le SBC utilise cette méthode pour envoyer une consigne de charge."""
        # On s'assure que la consigne reste entre 0 et 100%
        self.target_load = max(0.0, min(100.0, load_percent))

    def trigger_fault(self):
        """Simule une panne matérielle (pour tester le fallback C3)."""
        self.state = BoilerState.FAULT
        self.current_load = 0.0
        self.target_load = 0.0

    def clear_fault(self):
        """Acquittement du défaut."""
        if self.state == BoilerState.FAULT:
            self.state = BoilerState.OFF
            self.state_timer = 0.0

    def update(self):
        """
        Moteur d'exécution de la chaudière.
        Doit être appelé dans la boucle principale du simulateur (ex: chaque seconde).
        """
        now = time.time()
        dt = now - self.last_update_time  # Temps écoulé depuis la dernière mise à jour
        self.last_update_time = now

        # ---------------------------------------------------------
        # LOGIQUE DE LA MACHINE À ÉTATS
        # ---------------------------------------------------------
        if self.state == BoilerState.OFF:
            self.current_load = 0.0
            # Si le SBC demande de la puissance, on démarre la séquence
            if self.target_load > 0:
                self.state = BoilerState.PURGING
                self.state_timer = 0.0

        elif self.state == BoilerState.PURGING:
            self.state_timer += dt
            if self.state_timer >= self.PURGE_TIME:
                self.state = BoilerState.IGNITING
                self.state_timer = 0.0
                
            # Si le SBC annule la commande pendant la purge
            if self.target_load == 0:
                self.state = BoilerState.OFF

        elif self.state == BoilerState.IGNITING:
            self.state_timer += dt
            if self.state_timer >= self.IGNITE_TIME:
                self.state = BoilerState.RUNNING
                self.state_timer = 0.0
                
        elif self.state == BoilerState.RUNNING:
            # Si le SBC coupe la demande, on passe en refroidissement
            if self.target_load == 0:
                self.state = BoilerState.COOLDOWN
                self.state_timer = 0.0
            else:
                # INERTIE THERMIQUE : On monte ou descend progressivement vers la cible
                if self.current_load < self.target_load:
                    self.current_load += self.ramp_rate * dt
                    if self.current_load > self.target_load:
                        self.current_load = self.target_load
                elif self.current_load > self.target_load:
                    self.current_load -= self.ramp_rate * dt
                    if self.current_load < self.target_load:
                        self.current_load = self.target_load

        elif self.state == BoilerState.COOLDOWN:
            self.current_load = 0.0
            self.state_timer += dt
            if self.state_timer >= self.COOLDOWN_TIME:
                self.state = BoilerState.OFF
                self.state_timer = 0.0
                
            # Si le SBC redemande de la puissance pendant le cooldown
            if self.target_load > 0:
                self.state = BoilerState.PURGING
                self.state_timer = 0.0

        elif self.state == BoilerState.FAULT:
            self.current_load = 0.0
            # Bloqué jusqu'à ce que clear_fault() soit appelé

    def get_output_kw(self):
        """Retourne la puissance réelle instantanée en kW."""
        return (self.current_load / 100.0) * self.max_power_kw
    
    def get_state_modbus(self):
        """Retourne les valeurs prêtes à être écrites dans un registre Modbus."""
        return {
            "state": self.state,
            "load": int(self.current_load),
            "target": int(self.target_load)
        }