import logging
import sys

def setup_logger():
    """Configure un logger professionnel pour la console"""
    logger = logging.getLogger("SteamSwitch")
    logger.setLevel(logging.DEBUG)

    # Format : Heure - Niveau - Message
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')

    # Sortie console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(console_handler)
    
    return logger

# On l'initialise une fois pour tout le projet
log = setup_logger()