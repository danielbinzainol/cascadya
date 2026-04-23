import unittest

from cascadya_features.evaluator import evaluate_spec


class EvaluatorTestCase(unittest.TestCase):
    def test_empty_spec_scores_zero(self) -> None:
        result = evaluate_spec("")
        self.assertEqual(result.total_score, 0.0)
        self.assertEqual(result.gate, "insufficient")

    def test_rich_spec_scores_high(self) -> None:
        spec = """
        Objectif:
        Donner un lien interne pour challenger les specs de nouvelles features.

        Probleme:
        Les demandes arrivent dans trop de canaux, sans contexte stable ni critere de validation.

        Utilisateurs:
        - equipe IT Dev
        - ops
        - owner du script cible

        Perimetre MVP:
        - collage d'une spec
        - note automatique sur 5
        - liste de suggestions

        Hors scope:
        - historisation complete
        - SSO

        Criteres d'acceptation:
        - une spec bien structuree doit depasser 4/5
        - la page doit repondre en moins de 300 ms
        - un healthcheck doit etre disponible

        Risques et dependances:
        - reverse proxy Traefik
        - acces derriere WireGuard
        - recuperation de keys.js via la database
        - monitoring du service
        """
        result = evaluate_spec(spec)
        self.assertGreaterEqual(result.total_score, 4.0)
        self.assertIn(result.gate, {"strong", "promising"})

    def test_short_spec_stays_fragile(self) -> None:
        spec = "Faire une page pour les specs."
        result = evaluate_spec(spec)
        self.assertLess(result.total_score, 3.0)


if __name__ == "__main__":
    unittest.main()

