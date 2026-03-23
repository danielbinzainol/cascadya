1. Général : Pour tous les modèles (modèles avec les composantes individuelles uniquement, et modèles avec combinaisons de composantes) : 
	1. Utiliser TimeSeriesSplit pour créer des splits qui soient cohérents en termes temporels : taille de test fixes d'une semaine, et rajouter  un gap d'un jour.

2. Créer un modèle de baseline : moyenne globale.

3. Faire des modèles de régressions linéaires 

	1. Faire des modèles linéaires sur la base des composantes individuelles pertinentes
		1. Calculer la prédiction du prix sur la base de chacune des composantes individuelles, sur les échantillons obtenus par la séparation train/test. Comparer les métriques (MAE/RMSE/R^2) obtenues pour chaque modèle basé sur les composantes individuelles, sur chaque fold, avec celles obtenues pour le modèle baseline basé sur une moyenne/médiane globale.
		2. Modéliser les erreurs comme étant autorégressives, si elles le sont:
			1. baseline model -> residual ACF/PACF -> choose AR/MA orders -> validate with blocked CV.
        3. Vérifier a posteriori des régressions linéaires si les résidus suivent une loi normale, ce qui donnera de la confiance dans les résultats du modèle. Cela est testé avec :
            1. un diagrame quantile-quantile (QQ)
            2. et en comparant visuellement et numériquement l'asymétrie (skewness) et d'aplatissement (Kurtosis) des distributions des résidus, avec les valeurs d'une distribution normale.


	2. Faire des modèles linéaires sur la base des composantes combinées, et les évaluer
		1. Créer les modèles pour les composantes composées : créer des modèles "imbriqués":
			1. Modèle 0: calculer la moyenne globale seulement (baseline)
			2. Modèle 1: ajouter l'une des composantes individuelles seulement (month + weekday + hour + minute + holiday).  
			3. Modèle 2: ajoute des interactions en paire(weekday\*hour, month\*hour, etc.).
			4. Modèle 3: ajouter encore des composantes pour des interactions combinées d'ordre supérieur (3-way/4-way).
			5. Lorsqu'il y a beaucoup de paramètres, donc qu'on a un modèle à ordre élevé, ne pas faire de simple régressions linéaires.  Faire des modèles régularisés (ex. régression de Ridge) qui évitent le surapprentissage, ou du partial pooling.
			6. Comparer les métriques (MAE/RMSE/R^2) à chaque étape sur le set de tests, sur chaque fold. Seule une amélioration de M1->M2->M3 indique que la complexité additionnelle ajoute de l'information utile à la prévision.
		2. Pour évaluer les modèles avec composantes combinées, utiliser des "paired bootstrap CI on metric deltas". 
			1. on calcule la métrique (exemple: MAE) sur le M1 et le M2 (**paired** et **metric**)
			2. on calcule la différence entre la MAE du M1 et la MAE du M2 (**deltas**)
			3. on refait les points 1 et 2 (calcul du delta des métriques) pour différents ré-échantillonnages avec remise réalisés sur l'échantillon des metric deltas (**bootstrap**)
			4. l'intervalle de confiance est \[2,5%-97,5%\] (**CI**)
			5. Si 0 pour le delta ne tombe pas dans l'intervalle de confiance, alors la différence entre les métriques des deux modèles est probablement robuste. 
		3. Modéliser les erreurs comme étant autorégressives, si elles le sont:
			1. baseline model -> residual ACF/PACF -> choose AR/MA orders -> validate with blocked CV.
        4. Vérifier a posteriori des régressions linéaires si les résidus suivent une loi normale, ce qui donnera de la confiance dans les résultats du modèle. Cela est testé avec :
            1. un diagrame quantile-quantile (QQ)
            2. et en comparant visuellement et numériquement l'asymétrie (skewness) et d'aplatissement (Kurtosis) des distributions des résidus, avec les valeurs d'une distribution normale.

4. Faire des modèles autorégressifs
	1. Créer un modèle SARIMAX, 
        1. baseline model -> residual ACF/PACF -> choose AR/MA orders -> validate with blocked CV.
        2. évaluer avec les AR error
		3. Comme dans [le kaggle sarimax](https://www.kaggle.com/code/yemi99/time-series-forecasting-with-sarimax-model), tester si la donnée est stationnaire, avec un test ADF (Augmented Dickey Fuller). Tester si la différence entre la données à un pas de temps, et celle un jour, un mois avant, est stationnaire

5. inférence des paramètres (explication du poids de chacun)
	1. Pour l'analyse des paramètres des régressions, utiliser l'estimateur de Newey-West, c'est à dire l'erreur type robustes à l'hétéroscédasticité et à l'autocorrelation, pour avoir une mesure de la covariance pertinente.

	2. Etudier l'impact des composantes individuelles
		1. Vérifier si les conditions permettent d'utiliser un test paramétrique de Welch ANOVA : 
			1. est-ce que les observations sont indépendantes ? Testé avec une ACF et un test Q de Ljung-Box 
			2. est-ce que les données suivent une distribution a peu près normale au sein des groupes ? Testé avec :
                1. un diagrame quantile-quantile (QQ)
                2. et en comparant visuellement et numériquement l'asymétrie (skewness) et d'aplatissement (Kurtosis) des distributions des variances, avec les valeurs d'une distribution normale.
            3. Est-ce que les variances sont homogènes entre différents groupes (groupées par les valeurs de composantes individuelles) ? 
                1. Si les données suivent une distribution  symétrique, avec des queues/traines de taille pas trop grande (pour vérifier cela, faire notamment un histogramme), utiliser le test de Levene
                2. Sinon, utiliser le test de Brown–Forsythe
			4. Est-ce qu'il y a assez de données par groupes ? (n >= 30)
		2. Si oui, procéder à un test paramétrique de Welch ANOVA pour chaque composante individuelle (month, weekday, hour, minute, holiday_fr)
		3. Si non, procéder à un [test non-paramétrique de Kruskal-Wallis](https://stats.stackexchange.com/a/310262/383421) pour chaque composante individuelle.
		4. A côté de la p-value, procéder à la mesure de la taille d'effet, en calculant eta^2 et epsiolon^2. Ces valeurs auront surtout un intérêt si les tests de Kruskal-Wallis montrent qu'il existe un impact des composantes individuelles sur les prix, elles en donneront l'ampleur.
		5. Si les tests de Kruskal-Wallins montrent qu'il existe un impact d'une ou plusieurs compostantes individuelles sur les prix, réaliser un test post-hoc de Dunn permet de comparer les éléments par paire, afin de savoir quelles composantes sont celles qui ont un effet.
		6. Calculer les "Mutual Information (MI(component, price))", pour savoir à quel point connaitre une composante individuelle réduit l'incertitude sur le prix.


6. réaliser des sanity checks avec agregations à 30 minutes ou 1 heure.
	1. Un sanity check, c'est se demander : "est ce que les prédictions sont alignées avec la connaissance métier/business"