import time
import random
import math

class SteamHeader:
    def __init__(self, initial_pressure=5.0, volume_factor=0.0005):
        """
        Simule le collecteur de vapeur (Steam Header) de l'usine.
        """
        self.pressure_bar = initial_pressure
        self.volume_factor = volume_factor
        
        # Limites physiques
        self.MAX_PRESSURE = 6.5  # Pression d'ouverture des soupapes
        self.MIN_PRESSURE = 0.0  # Vide absolu
        self.relief_valve_open = False
        
        # Paramètres pour la simulation de l'usine
        self.start_time = time.time()
        
        # Ajusté à 1250 kW pour centrer l'oscillation parfaitement entre 200 et 2300 kW
        self.base_demand_kw = 1250.0 
        self.current_demand_kw = self.base_demand_kw 
        
        self.last_update_time = time.time()
        
        # Timer pour permettre le forçage manuel sans être écrasé par la boucle auto
        self.manual_override_until = 0.0

    def set_factory_demand(self, demand_kw):
        """Permet de forcer manuellement une consommation via Modbus."""
        self.current_demand_kw = max(0.0, demand_kw)
        # Met en pause le cycle automatique pendant 15 secondes
        self.manual_override_until = time.time() + 15.0

    def simulate_factory_cycle(self):
        """
        Génère une demande réaliste (Sinusoïde + Bruit) couvrant toute la plage
        pour forcer le SBC à allumer et éteindre la cascade complète.
        """
        # Si une commande manuelle a été envoyée, on bloque la simulation auto
        if time.time() < self.manual_override_until:
            return

        elapsed = time.time() - self.start_time
        
        # 1. Cycle de production (Onde sinusoïdale). 
        # Oscille entre -1050 kW et +1050 kW.
        # Le diviseur (60.0) accélère un peu le cycle (1 tour = ~6 minutes) pour Grafana.
        cycle = math.sin(elapsed / 60.0) * 1050.0
        
        # 2. Bruit aléatoire (turbulences de petites machines)
        noise = random.uniform(-60.0, 60.0)
        
        # 3. Calcul de la demande (Moyenne + Cycle + Bruit)
        total_demand = self.base_demand_kw + cycle + noise
        
        # On force la valeur entre 200 kW (minimum pour pas tout couper) et 2350 kW
        self.current_demand_kw = max(200.0, min(total_demand, 2350.0))

    def update(self, total_boiler_output_kw):
        """Moteur physique : Calcule la nouvelle pression."""
        now = time.time()
        dt = now - self.last_update_time
        self.last_update_time = now

        # Calcule la nouvelle demande de l'usine
        self.simulate_factory_cycle()

        # 1. Bilan énergétique (Production - Consommation)
        net_energy_kw = total_boiler_output_kw - self.current_demand_kw
        
        # 2. Calcul de la variation de pression (ΔP)
        delta_p = net_energy_kw * self.volume_factor * dt
        
        # 3. Application
        self.pressure_bar += delta_p

        # 4. Sécurités physiques
        if self.pressure_bar >= self.MAX_PRESSURE:
            self.pressure_bar = self.MAX_PRESSURE
            self.relief_valve_open = True
        else:
            self.relief_valve_open = False

        if self.pressure_bar <= self.MIN_PRESSURE:
            self.pressure_bar = self.MIN_PRESSURE

    def get_pressure_modbus(self):
        """Standard industriel : x10 pour Modbus."""
        return int(self.pressure_bar * 10)
    
    def get_demand_modbus(self):
        return int(self.current_demand_kw)