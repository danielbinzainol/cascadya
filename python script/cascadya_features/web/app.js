const specInput = document.getElementById("spec-input");
const evaluateButton = document.getElementById("evaluate-button");
const sampleButton = document.getElementById("sample-button");
const clearButton = document.getElementById("clear-button");
const statusPill = document.getElementById("status-pill");
const runtimeText = document.getElementById("runtime-text");
const runtimeTags = document.getElementById("runtime-tags");
const overviewTitle = document.getElementById("overview-title");
const consensusBadge = document.getElementById("consensus-badge");
const decisionBadge = document.getElementById("decision-badge");
const overviewCallout = document.getElementById("overview-callout");
const overviewSummary = document.getElementById("overview-summary");
const overviewMetadata = document.getElementById("overview-metadata");
const modelReviewList = document.getElementById("model-review-list");
const scoreTableHead = document.getElementById("score-table-head");
const scoreTableBody = document.getElementById("score-table-body");

const sampleSpec = `Titre
Enrichir le panel Alerts du Control Panel avec des alertes monitoring issues de Mimir / Alloy

Contexte / probleme
Aujourd'hui, le panel Alerts du Control Panel remonte principalement des alertes Wazuh. C'est utile pour la securite mais insuffisant pour donner une vue operateur complete sur l'etat des IPC.

Objectif
Faire evoluer le panel Alerts pour qu'il agregre les alertes Wazuh existantes et des alertes monitoring derivees de Mimir a partir des metriques host collectees par Alloy.

Utilisateurs / impact
- operateurs Control Panel
- equipe exploitation / support
- equipe infra / edge

Perimetre fonctionnel vise
- enrichir /api/alerts/live
- materialiser uniquement des situations inquietantes
- ne pas afficher de telemetrie brute

Hors perimetre
- remplacer Grafana
- afficher des graphes ou dashboards dans Alerts
- creer un moteur d'alerting generique

Criteres d'acceptation
- /api/alerts/live retourne toujours les alertes Wazuh existantes
- un IPC down via monitoring cree une alerte visible
- un disque critique cree une alerte visible
- le backend degrade proprement si Mimir est indisponible

Risques / dependances / exploitation
- connectivite control panel -> Mimir
- labels IPC stables
- risque de bruit si les seuils sont mal choisis
- besoin de dedoublonner les situations qui remontent via plusieurs sources`;

const DEMO_REVIEW = {
  title: "Synthese consolidee",
  consensus: "modere",
  decision: "POC_CADRE",
  callout:
    "Consensus modere a fort sur un point central: l'outil est utile pour standardiser les revues, mais la V1 doit rester un POC cadre tant que les garde-fous plateforme, secrets et observabilite ne sont pas au niveau attendu.",
  summary:
    "La trajectoire recommandee est un POC restreint, instrumente et reversible. L'utilite produit est reelle, mais l'industrialisation doit attendre une meilleure maitrise des secrets, de la gouvernance, de l'audit et des donnees envoyees aux fournisseurs LLM.",
  metadata: [
    { label: "Mode", value: "Projection UI sur scorer V1" },
    { label: "Agents", value: "4 axes consolides" },
    { label: "Modeles", value: "Claude, GPT, Gemini" },
    { label: "Sortie", value: "POC cadre" },
  ],
  models: [
    {
      name: "Claude Opus 4.6",
      consensus: "fort",
      decision: "POC_CADRE",
      intro:
        "Les retours convergent sur l'utilite immediate de l'outil pour clarifier les decisions d'architecture, avec une bonne reversibilite si on le garde hors du chemin critique.",
      summary:
        "Le POC est defendable si la trajectoire d'industrialisation est explicite: owner, garde-fous secrets, audit, CI minimale et criteres de sortie avant generalisation.",
      recurringRisks: [
        "Secrets et cles API hors Vault en V1",
        "ROI encore peu mesure face a une alternative plus simple type checklist Markdown",
        "Bus factor eleve si l'outil reste porte par un owner unique",
      ],
      recurringStrengths: [
        "Besoin reel de standardisation des revues",
        "Hebergement prive cohérent avec le VPC et WireGuard",
        "Reversibilite simple avec export markdown ou process manuel",
      ],
      nextSteps: [
        "Nommer un owner et un co-mainteneur",
        "Ajouter une CI minimale avec tests d'integration",
        "Fixer des criteres de sortie du POC avant extension",
      ],
    },
    {
      name: "GPT-5.4",
      consensus: "modere",
      decision: "POC_CADRE",
      intro:
        "Le consensus est favorable sur le besoin de structuration, mais les divergences se concentrent sur la severite des ecarts plateforme et la gestion des donnees potentiellement sensibles.",
      summary:
        "Le POC est acceptable uniquement dans un cadre restreint, sur des contenus non sensibles et avec une trajectoire explicite vers Vault, auth, audit et observabilite.",
      recurringRisks: [
        "Envoi de specs ou artefacts sensibles vers des SaaS LLM sans garde-fous suffisants",
        "Ecarts au standard plateforme: Vault, auth, audit, observabilite",
        "Risque qu'un POC minimal se perennise sans gouvernance claire",
      ],
      recurringStrengths: [
        "Besoin concret de meilleure tracabilite des revues",
        "Specification claire des limites de la V1",
        "Possibilite de garder Grafana et les autres outils de detail comme reference",
      ],
      nextSteps: [
        "Limiter l'usage a un POC prive derriere WireGuard",
        "Documenter les flux de donnees et la retention fournisseur",
        "Mettre en place une auth applicative et un runbook minimal",
      ],
    },
    {
      name: "Gemini 3.1 Pro",
      consensus: "modere",
      decision: "POC_CADRE",
      intro:
        "Les agents s'accordent sur la qualite du cadrage et de l'isolation reseau, mais relevent des inquietudes majeures sur la securite des donnees et la maintenabilite si la V1 reste trop artisanale.",
      summary:
        "L'outil est prometteur comme point de triage et de discussion, a condition d'ajouter rapidement des garde-fous techniques avant toute extension au-dela d'un noyau d'utilisateurs restreint.",
      recurringRisks: [
        "Exfiltration de donnees ou de propriete intellectuelle vers des LLM publics",
        "Tests insuffisants pour un outil appele a influencer les decisions d'equipe",
        "Definition encore partielle de la gouvernance long terme",
      ],
      recurringStrengths: [
        "Isolement reseau respecte via VPC et WireGuard",
        "Documentation honnete des limites et hypotheses du POC",
        "Reversibilite presque totale sans impact sur le chemin critique",
      ],
      nextSteps: [
        "Definir une charte de sanitization avant tout usage large",
        "Ajouter des tests automatises sur parsing, cout et retries",
        "Fixer un budget cible et une baseline de comparaison",
      ],
    },
  ],
  scoreRows: [
    { agent: "Architecture", tone: "architecture", scores: { "Claude Opus 4.6": 4, "GPT-5.4": 3, "Gemini 3.1 Pro": 3 } },
    { agent: "Securite / Ops", tone: "security", scores: { "Claude Opus 4.6": 3, "GPT-5.4": 2, "Gemini 3.1 Pro": 2 } },
    { agent: "Valeur / Produit", tone: "value", scores: { "Claude Opus 4.6": 4, "GPT-5.4": 3, "Gemini 3.1 Pro": 3 } },
    { agent: "Delivery / Maintenance", tone: "delivery", scores: { "Claude Opus 4.6": 4, "GPT-5.4": 3, "Gemini 3.1 Pro": 3 } },
  ],
};

function setStatus(message, tone = "neutral") {
  statusPill.textContent = message;
  statusPill.dataset.tone = tone;
}

function decisionLabel(decision) {
  if (decision === "GO") return "Go";
  if (decision === "POC_CADRE") return "POC cadre";
  if (decision === "A_RETRAVAILLER") return "A retravailler";
  if (decision === "REJET") return "Rejet";
  return decision;
}

function consensusLabel(consensus) {
  if (consensus === "fort") return "Consensus fort";
  if (consensus === "modere") return "Consensus modere";
  if (consensus === "fragile") return "Consensus fragile";
  return "Consensus a confirmer";
}

function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function roundOne(value) {
  return Math.round(value * 10) / 10;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function extractDimensionMap(result) {
  const entries = {};
  result.dimensions.forEach((dimension) => {
    entries[dimension.key] = dimension.score;
  });
  return entries;
}

function buildStrengths(result) {
  const strengths = [];
  result.dimensions.forEach((dimension) => {
    if (dimension.score >= 0.8) {
      strengths.push(`${dimension.label} bien cadre (${dimension.score.toFixed(2)} / 1).`);
    }
  });
  if (result.total_score >= 4) {
    strengths.push("Spec deja exploitable pour un challenge d'equipe rapide.");
  }
  return strengths.slice(0, 4);
}

function buildRisks(result) {
  const risks = [];
  result.dimensions.forEach((dimension) => {
    if (dimension.score < 0.75) {
      risks.push(`${dimension.label} encore trop faible pour limiter les ambiguities sans rework.`);
    }
  });
  result.suggestions.forEach((suggestion) => risks.push(suggestion));
  if (!risks.length) {
    risks.push("Peu de risques immediats detects par la grille V1, mais une validation humaine reste necessaire.");
  }
  return risks.slice(0, 5);
}

function buildNextSteps(result) {
  const steps = result.suggestions.length ? [...result.suggestions] : ["Conserver la spec telle quelle et lancer la revue humaine."];
  if (result.total_score >= 4) {
    steps.push("Partager l'export de review avec le thread de discussion equipe.");
  }
  return steps.slice(0, 5);
}

function deriveDecision(result) {
  if (result.total_score >= 4.7 && result.suggestions.length === 0) return "GO";
  if (result.total_score >= 3.6) return "POC_CADRE";
  if (result.total_score >= 2.6) return "A_RETRAVAILLER";
  return "REJET";
}

function deriveConsensus(rows) {
  const rowAverages = rows.map((row) => average(Object.values(row.scores)));
  const spread = Math.max(...rowAverages) - Math.min(...rowAverages);
  if (spread <= 0.45) return "fort";
  if (spread <= 1.1) return "modere";
  return "fragile";
}

function projectReviewFromHeuristic(result) {
  const dimensions = extractDimensionMap(result);
  const architectureBase = clamp((dimensions.context + dimensions.scope) / 2, 0.2, 1);
  const securityBase = clamp(dimensions.delivery * 0.8 + dimensions.acceptance * 0.2, 0.2, 1);
  const valueBase = clamp((dimensions.impact + dimensions.context) / 2, 0.2, 1);
  const deliveryBase = clamp((dimensions.acceptance + dimensions.delivery) / 2, 0.2, 1);
  const strengths = buildStrengths(result);
  const risks = buildRisks(result);
  const nextSteps = buildNextSteps(result);

  const modelConfigs = [
    {
      name: "Claude Opus 4.6",
      offsets: { architecture: 0.18, security: 0.08, value: 0.12, delivery: 0.15 },
      intro:
        "Le consensus est globalement positif sur la structure de la spec, avec une bonne lisibilite des intentions et des limites si le scope reste bien borne.",
      summary:
        "La spec est defendable dans un cadre de POC ou de go cible selon l'axe le plus faible, avec une bonne base pour une discussion architecturale outillee.",
    },
    {
      name: "GPT-5.4",
      offsets: { architecture: 0.0, security: -0.08, value: 0.0, delivery: 0.0 },
      intro:
        "La lecture est plutot robuste, mais les divergences se concentrent sur les zones encore floues qui pourraient produire du bruit ou des interpretations differentes entre equipes.",
      summary:
        "Le besoin est clair et utile, mais la recommandation reste prudente tant que les points faibles explicites n'ont pas ete fermes.",
    },
    {
      name: "Gemini 3.1 Pro",
      offsets: { architecture: -0.04, security: -0.1, value: 0.0, delivery: -0.04 },
      intro:
        "La spec est bien structuree pour une revue d'equipe, tout en laissant apparaitre des points de vigilance sur l'industrialisation et le bruit operationnel.",
      summary:
        "La trajectoire la plus saine est un POC cadre ou un go borne selon le niveau de risque accepte et la maturite du contexte technique.",
    },
  ];

  const scoreRows = [
    { agent: "Architecture", tone: "architecture", base: architectureBase },
    { agent: "Securite / Ops", tone: "security", base: securityBase },
    { agent: "Valeur / Produit", tone: "value", base: valueBase },
    { agent: "Delivery / Maintenance", tone: "delivery", base: deliveryBase },
  ].map((row) => {
    const scores = {};
    modelConfigs.forEach((config) => {
      const key =
        row.agent === "Architecture"
          ? "architecture"
          : row.agent === "Securite / Ops"
            ? "security"
            : row.agent === "Valeur / Produit"
              ? "value"
              : "delivery";
      scores[config.name] = Math.round(clamp((row.base + config.offsets[key]) * 5, 1, 5));
    });
    return { agent: row.agent, tone: row.tone, scores };
  });

  const consensus = deriveConsensus(scoreRows);
  const decision = deriveDecision(result);
  const averageScore = roundOne(result.total_score);

  const metadata = [
    { label: "Source", value: "Projection UI a partir du scorer V1" },
    { label: "Score heuristique", value: `${averageScore.toFixed(2)} / ${result.max_score.toFixed(0)}` },
    { label: "Gate initial", value: result.gate.toUpperCase() },
    { label: "Suggestions", value: `${result.suggestions.length}` },
  ];

  const models = modelConfigs.map((config) => {
    const modelAverage = average(Object.values(scoreRows.reduce((scores, row) => {
      scores[row.agent] = row.scores[config.name];
      return scores;
    }, {})));
    return {
      name: config.name,
      consensus: modelAverage >= 4 ? "fort" : modelAverage >= 3 ? "modere" : "fragile",
      decision,
      intro: config.intro,
      summary: config.summary,
      recurringRisks: risks.slice(0, 4),
      recurringStrengths: strengths.slice(0, 4),
      nextSteps: nextSteps.slice(0, 5),
    };
  });

  return {
    title: `Synthese consolidee - ${averageScore.toFixed(2)} / ${result.max_score.toFixed(0)}`,
    consensus,
    decision,
    callout: `${consensusLabel(consensus)} sur la spec evaluee: ${result.summary}`,
    summary:
      "Le backend actuel renvoie un scoring heuristique unique. La page projette ce resultat dans une presentation multi-modeles afin de valider l'UX cible avant branchement du moteur natif multi-agents.",
    metadata,
    models,
    scoreRows,
  };
}

function normalizeReviewPayload(payload) {
  if (payload.review) {
    return payload.review;
  }
  if (payload.result) {
    return projectReviewFromHeuristic(payload.result);
  }
  return DEMO_REVIEW;
}

function renderMetadata(items) {
  overviewMetadata.innerHTML = "";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "metadata-card";
    card.innerHTML = `
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(item.value)}</strong>
    `;
    overviewMetadata.appendChild(card);
  });
}

function renderOverview(review) {
  overviewTitle.textContent = review.title;
  consensusBadge.textContent = consensusLabel(review.consensus);
  consensusBadge.dataset.tone = review.consensus;
  decisionBadge.textContent = decisionLabel(review.decision);
  decisionBadge.dataset.tone = review.decision;
  overviewCallout.textContent = review.callout;
  overviewSummary.textContent = review.summary;
  renderMetadata(review.metadata);
}

function renderBulletList(items) {
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderModelReviews(models) {
  modelReviewList.innerHTML = "";
  models.forEach((model) => {
    const article = document.createElement("article");
    article.className = "model-card";
    article.innerHTML = `
      <div class="model-card-head">
        <div>
          <p class="section-kicker">Synthese modele</p>
          <h3>Synthese ${escapeHtml(model.name)}</h3>
        </div>
        <div class="badge-row">
          <span class="decision-badge consensus" data-tone="${escapeHtml(model.consensus)}">${escapeHtml(consensusLabel(model.consensus))}</span>
          <span class="decision-badge decision" data-tone="${escapeHtml(model.decision)}">${escapeHtml(decisionLabel(model.decision))}</span>
        </div>
      </div>
      <div class="quote-card">${escapeHtml(model.intro)}</div>
      <p class="model-summary">${escapeHtml(model.summary)}</p>
      <div class="model-grid">
        <section class="model-column danger">
          <h4>Risques recurrents</h4>
          <ul>${renderBulletList(model.recurringRisks)}</ul>
        </section>
        <section class="model-column success">
          <h4>Forces recurrentes</h4>
          <ul>${renderBulletList(model.recurringStrengths)}</ul>
        </section>
        <section class="model-column accent">
          <h4>Prochaines etapes</h4>
          <ul>${renderBulletList(model.nextSteps)}</ul>
        </section>
      </div>
    `;
    modelReviewList.appendChild(article);
  });
}

function scoreTone(score) {
  if (score >= 4) return "good";
  if (score >= 3) return "medium";
  return "weak";
}

function renderScoreTable(rows) {
  if (!rows.length) {
    scoreTableHead.innerHTML = "";
    scoreTableBody.innerHTML = "";
    return;
  }

  const modelNames = Object.keys(rows[0].scores);
  scoreTableHead.innerHTML = `
    <tr>
      <th>Agent</th>
      ${modelNames.map((name) => `<th>${escapeHtml(name)}</th>`).join("")}
      <th>Moyenne</th>
    </tr>
  `;

  scoreTableBody.innerHTML = rows
    .map((row) => {
      const values = modelNames.map((name) => row.scores[name]);
      const rowAverage = roundOne(average(values));
      return `
        <tr>
          <td>
            <div class="agent-cell">
              <span class="agent-dot ${escapeHtml(row.tone)}"></span>
              <span>${escapeHtml(row.agent)}</span>
            </div>
          </td>
          ${modelNames
            .map((name) => {
              const score = row.scores[name];
              return `
                <td>
                  <span class="score-pill ${scoreTone(score)}">${score}/5</span>
                </td>
              `;
            })
            .join("")}
          <td class="average-cell">${rowAverage.toFixed(1)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderReview(review) {
  renderOverview(review);
  renderModelReviews(review.models);
  renderScoreTable(review.scoreRows);
}

function renderRuntime(status) {
  runtimeText.textContent = `Serveur ${status.app_name} sur ${status.host}:${status.port}. keys.js: ${status.keys_source}.`;
  const tags = [
    `API keys: ${status.configured_api_key_count}`,
    `DB: ${status.database_configured ? "configuree" : "non configuree"}`,
    `Dotenv: ${status.dotenv_path}`,
  ];
  runtimeTags.innerHTML = tags.map((tag) => `<span class="runtime-chip">${escapeHtml(tag)}</span>`).join("");
}

async function loadRuntime() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const payload = await response.json();
    renderRuntime(payload.status);
  } catch (error) {
    runtimeText.textContent = "Statut runtime indisponible.";
    runtimeTags.innerHTML = "";
  }
}

async function evaluateSpec() {
  const spec = specInput.value.trim();
  if (!spec) {
    setStatus("Colle une spec avant de lancer l'evaluation.", "warning");
    return;
  }

  evaluateButton.disabled = true;
  setStatus("Evaluation en cours...", "loading");

  try {
    const response = await fetch("/api/evaluate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ spec }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Erreur inconnue");
    }
    renderReview(normalizeReviewPayload(payload));
    setStatus("Evaluation terminee.", "success");
  } catch (error) {
    setStatus(`Echec: ${error.message}`, "danger");
  } finally {
    evaluateButton.disabled = false;
  }
}

sampleButton.addEventListener("click", () => {
  specInput.value = sampleSpec;
  setStatus("Spec exemple chargee.", "neutral");
});

clearButton.addEventListener("click", () => {
  specInput.value = "";
  renderReview(DEMO_REVIEW);
  setStatus("Champ vide, demo restauree.", "neutral");
});

evaluateButton.addEventListener("click", evaluateSpec);

renderReview(DEMO_REVIEW);
loadRuntime();
