import time
from threading import Thread
from pymodbus.server.sync import StartTcpServer
from pymodbus.datastore import (
    ModbusSlaveContext,
    ModbusServerContext,
    ModbusSequentialDataBlock
)

# --- CONFIGURATION DES REGISTRES ---
# %MW0-16   : Préparation des ordres [cite: 182]
# %MW50     : Bit d'envoi (ENVOI_00)
# %MW51     : Statut de l'envoi
# %MW100+   : Pile du planificateur (Ordre 1) [cite: 202]
# %MW602-607: Horloge SBC [cite: 309]
# %MW620    : Watchdog SteamSwitch [cite: 326]

store = ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0]*1000))
context = ModbusServerContext(slaves=store, single=True)

def sbc_internal_clock():
    """Simule l'horloge interne du M580 (SBC) """
    while True:
        try:
            now = time.localtime()
            clock_data = [now.tm_mday, now.tm_mon, now.tm_year, now.tm_hour, now.tm_min, now.tm_sec]
            context[0].setValues(3, 602, clock_data)
        except Exception as e:
            print(f"[CLOCK ERROR] {e}")
        time.sleep(1)

def handle_orders():
    """Simule la logique du planificateur SBC : Traitement des ordres entrants """
    last_envoi_bit = 0
    while True:
        try:
            # 1. Lecture du registre de commande %MW50
            mw50_val = context[0].getValues(3, 50, count=1)[0]
            envoi_bit = mw50_val & 0x1  # On regarde le bit 0

            # 2. Détection d'un front montant (passage de 0 à 1)
            if envoi_bit == 1 and last_envoi_bit == 0:
                print("📥 [SBC] Nouvel ordre détecté en préparation...")

                # Lecture de la zone de préparation (%MW0 à %MW16) [cite: 182]
                prep_data = context[0].getValues(3, 0, count=17)
                order_id = (prep_data[0] << 16) | prep_data[1]

                print(f"✅ [SBC] Traitement Ordre ID: {order_id}")

                # Simulation du transfert dans la pile FIFO (Emplacement 1 : %MW100)
                context[0].setValues(3, 100, prep_data)

                # Mise à jour du statut : 0 = Succès
                context[0].setValues(3, 51, [0])

                # Remise à zéro du bit d'envoi par l'automate
                context[0].setValues(3, 50, [0])
                print(f"🏁 [SBC] Ordre {order_id} ajouté au planificateur. Statut: OK")

            last_envoi_bit = envoi_bit
        except Exception as e:
            print(f"[ORDER ERROR] {e}")
        time.sleep(0.2)

def monitor_watchdog():
    """Surveille le Watchdog du SteamSwitch (%MW620) [cite: 326, 331]"""
    last_wd_value = None
    last_change = time.time()
    while True:
        current_wd = context[0].getValues(3, 620, count=1)[0]
        if current_wd != last_wd_value:
            last_wd_value = current_wd
            last_change = time.time()
        elif time.time() - last_change > 30:
            print(f"⚠️ [ALERTE SBC] Watchdog SteamSwitch (%MW620) FIGÉ !")
        time.sleep(0.5)

if __name__ == "__main__":
    Thread(target=sbc_internal_clock, daemon=True).start()
    Thread(target=handle_orders, daemon=True).start()
    Thread(target=monitor_watchdog, daemon=True).start()

    print("--- Simulateur SBC (M580) Planificateur Actif ---")
    print("Écoute : %MW0-%MW50 | Retour Statut : %MW51 | Pile : %MW100")
    StartTcpServer(context, address=("0.0.0.0", 502))