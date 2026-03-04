def sbc_internal_clock():
    """Simule l'horloge du M580 dans les registres %MW602-%MW607"""
    while True:
        try:
            now = time.localtime()
            # On écrit JJ, MM, AAAA, HH, MM, SS (Réf Note Technique p.10-11)
            clock_values = [now.tm_mday, now.tm_mon, now.tm_year, now.tm_hour, now.tm_min, now.tm_sec]
            context[0].setValues(3, 602, clock_values) # %MW602 à %MW607 [cite: 309, 316]
        except Exception as e:
            print(f"Erreur horloge: {e}")
        time.sleep(1) # Mise à jour chaque seconde [cite: 324, 327]