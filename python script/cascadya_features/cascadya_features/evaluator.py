from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import unicodedata


@dataclass(frozen=True)
class DimensionScore:
    key: str
    label: str
    score: float
    rationale: str


@dataclass(frozen=True)
class EvaluationResult:
    total_score: float
    max_score: float
    gate: str
    summary: str
    dimensions: list[DimensionScore]
    suggestions: list[str]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["dimensions"] = [asdict(item) for item in self.dimensions]
        return payload


def _normalize(text: str) -> str:
    lowered = text.lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _line_count(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def _bullet_count(text: str) -> int:
    return len(re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+", text))


def _dimension(
    key: str,
    label: str,
    score: float,
    rationale: str,
) -> DimensionScore:
    return DimensionScore(key=key, label=label, score=round(max(0.0, min(1.0, score)), 2), rationale=rationale)


def evaluate_spec(spec: str) -> EvaluationResult:
    raw = spec.strip()
    if not raw:
        return EvaluationResult(
            total_score=0.0,
            max_score=5.0,
            gate="insufficient",
            summary="Aucune matiere a evaluer: colle d'abord une spec ou un brouillon.",
            dimensions=[
                _dimension("context", "Contexte", 0.0, "Aucun contenu fourni."),
                _dimension("impact", "Impact", 0.0, "Impossible d'identifier les utilisateurs cibles."),
                _dimension("scope", "Perimetre", 0.0, "Le scope n'est pas defini."),
                _dimension("acceptance", "Acceptance", 0.0, "Aucun critere d'acceptation detecte."),
                _dimension("delivery", "Risques", 0.0, "Aucun risque ni dependance mentionne."),
            ],
            suggestions=[
                "Ajoute le probleme a resoudre et pourquoi on le traite maintenant.",
                "Precise qui est impacte et comment on saura que le changement est utile.",
                "Ajoute des criteres d'acceptation testables avant de lancer le dev.",
            ],
        )

    normalized = _normalize(raw)
    lines = _line_count(raw)
    bullets = _bullet_count(raw)

    context_score = 0.0
    if len(raw) >= 220:
        context_score += 0.35
    if _contains_any(normalized, ("objectif", "problem", "probleme", "pourquoi", "contexte", "goal")):
        context_score += 0.45
    if _contains_any(normalized, ("aujourd", "maintenant", "pain point", "douleur", "blocage", "enjeu")):
        context_score += 0.20
    context = _dimension(
        "context",
        "Contexte",
        context_score,
        "Le besoin est plus solide quand la spec explique le probleme et le pourquoi.",
    )

    impact_score = 0.0
    if _contains_any(normalized, ("utilisateur", "user", "client", "team", "equipe", "ops", "dev", "support")):
        impact_score += 0.45
    if _contains_any(normalized, ("impact", "valeur", "benefice", "gain", "kpi", "mesure", "resultat")):
        impact_score += 0.35
    if _contains_any(normalized, ("persona", "role", "acteur", "owner")):
        impact_score += 0.20
    if bullets >= 3 and _contains_any(normalized, ("utilisateur", "owner", "acteur", "role")):
        impact_score += 0.15
    impact = _dimension(
        "impact",
        "Impact",
        impact_score,
        "Une bonne spec nomme les personnes concernees et l'effet attendu.",
    )

    scope_score = 0.0
    if _contains_any(normalized, ("scope", "perimetre", "mvp", "phase", "lot", "version", "iteration")):
        scope_score += 0.40
    if _contains_any(normalized, ("non objectif", "out of scope", "hors scope", "ne fera pas", "won't", "ne couvre pas")):
        scope_score += 0.35
    if bullets >= 3 or lines >= 8:
        scope_score += 0.25
    scope = _dimension(
        "scope",
        "Perimetre",
        scope_score,
        "Le perimetre doit aider a savoir ce qu'on fait maintenant et ce qu'on repousse.",
    )

    acceptance_score = 0.0
    if _contains_any(
        normalized,
        (
            "critere",
            "acceptance",
            "done",
            "definition of done",
            "test",
            "validation",
            "expected",
            "attendu",
        ),
    ):
        acceptance_score += 0.50
    if _contains_any(normalized, ("given", "when", "then", "si ", "quand", "alors")):
        acceptance_score += 0.20
    if re.search(r"\b\d+(?:[.,]\d+)?\s*(ms|s|mn|min|h|jours|users|utilisateurs|%|go|mo)\b", normalized):
        acceptance_score += 0.30
    acceptance = _dimension(
        "acceptance",
        "Acceptance",
        acceptance_score,
        "Le niveau monte quand la spec est testable et observable.",
    )

    delivery_score = 0.0
    if _contains_any(
        normalized,
        (
            "risque",
            "risk",
            "dependance",
            "dependency",
            "rollback",
            "monitoring",
            "securite",
            "security",
            "performance",
        ),
    ):
        delivery_score += 0.50
    if _contains_any(normalized, ("database", "db", "wireguard", "traefik", "nginx", "api", "migration")):
        delivery_score += 0.20
    if _contains_any(normalized, ("log", "alert", "telemetrie", "metrique", "observabilite")):
        delivery_score += 0.30
    delivery = _dimension(
        "delivery",
        "Risques",
        delivery_score,
        "Une spec mature anticipe les dependances, les garde-fous et l'exploitation.",
    )

    dimensions = [context, impact, scope, acceptance, delivery]
    total_score = round(sum(item.score for item in dimensions), 2)

    suggestions: list[str] = []
    if context.score < 0.7:
        suggestions.append("Ajoute un bloc court 'probleme / pourquoi maintenant' pour mieux cadrer la demande.")
    if impact.score < 0.7:
        suggestions.append("Precise qui est impacte, quel gain est attendu et si possible un indicateur simple.")
    if scope.score < 0.7:
        suggestions.append("Separe le MVP, les non-objectifs et ce qui peut attendre une phase suivante.")
    if acceptance.score < 0.7:
        suggestions.append("Liste 3 a 5 criteres d'acceptation testables avant implementation.")
    if delivery.score < 0.7:
        suggestions.append("Ajoute au moins les risques, les dependances techniques et le plan de verification.")
    if lines < 6:
        suggestions.append("Structure la spec avec des sections ou bullets pour faciliter la revue.")

    if total_score >= 4.5:
        gate = "strong"
        summary = "Spec bien cadree: on a de quoi challenger finement puis lancer l'implementation."
    elif total_score >= 3.5:
        gate = "promising"
        summary = "Base solide, mais quelques zones floues meritent un dernier tour avant go."
    elif total_score >= 2.5:
        gate = "fragile"
        summary = "L'intention est la, mais la spec reste trop ouverte pour eviter les reworks."
    else:
        gate = "insufficient"
        summary = "Spec trop legere pour lancer sereinement le dev sans ambiguite."

    return EvaluationResult(
        total_score=total_score,
        max_score=5.0,
        gate=gate,
        summary=summary,
        dimensions=dimensions,
        suggestions=suggestions,
    )
