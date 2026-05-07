# unit root test, pour savoir si la donnée est stationnaire, pour tester l'hypothèse de stationnarité
# adf test : augmented dickey fuller test
# Kwiatkowski-Phillips-Schmidt-Shin (KPSS) test (dans livre hyndman)

# differencing : une façon de transformer une série non-stationnaire en série temporelle stationnaire

# en calculer le prediction interval (l'intervalle de confiance)
# est-ce que les résidus du modèle ARIMA sont distribués normalement et non correlé ?
# Si oui, on peut calculer la variance présente au pas n de la prévision. Ca suivrait alors une loi normale.
# si non, on peut plutot adapter la méthode ARIMA. Au lieu de créer un forecast d'un point, générer des "sample paths".
## l'idée : au lieu de remplacer les erreurs futures par 0, les remplacer par un tirage **bootstrap** de la distribution empirique des résidus passés. Voir le livre Hyndman sur la partie toolbox > bootstrap
