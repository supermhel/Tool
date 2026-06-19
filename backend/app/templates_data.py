"""Définition des trois templates d'évaluation.

Chaque template porte une liste de critères. Chaque critère a :
- id            : identifiant stable
- label         : titre court affiché
- detail        : description fine de CE QUI EST MESURE
- weight        : poids dans le score (les poids n'ont pas besoin de sommer à 1,
                  ils sont normalisés au moment du calcul)
- max           : note maximale du curseur (échelle 0..max)

Chaque template décrit aussi son périmètre : `covered` (ce qu'il évalue) et
`excluded` (ce qu'il ne couvre pas, avec renvoi vers le bon template).
"""

TEMPLATES = {
    "process": {
        "id": "process",
        "name": "Processus",
        "color": "#5b8cff",
        "description": "Évalue la maturité et l'efficacité d'un processus métier.",
        "criteria": [
            {"id": "steps", "label": "Clarté des étapes",
             "detail": "Les étapes du processus sont-elles définies, ordonnées et sans ambiguïté ?",
             "weight": 1.0, "max": 10},
            {"id": "bottlenecks", "label": "Goulots & délais",
             "detail": "Mesure l'absence de points de blocage et le respect des délais cibles.",
             "weight": 1.2, "max": 10},
            {"id": "compliance", "label": "Conformité aux règles",
             "detail": "Le processus respecte-t-il les règles métier, légales et internes applicables ?",
             "weight": 1.0, "max": 10},
            {"id": "automation", "label": "Automatisation",
             "detail": "Part des tâches automatisées vs manuelles à faible valeur ajoutée.",
             "weight": 0.8, "max": 10},
            {"id": "repeatability", "label": "Reproductibilité",
             "detail": "Le processus produit-il un résultat constant quand il est rejoué ?",
             "weight": 1.0, "max": 10},
        ],
        "scope": {
            "covered": [
                "Enchaînement et clarté des étapes",
                "Goulots d'étranglement et délais",
                "Conformité aux règles métier",
                "Niveau d'automatisation et reproductibilité",
            ],
            "excluded": [
                {"label": "Le ressenti des utilisateurs du processus", "ref": "sentiment"},
                {"label": "La qualité technique des outils support", "ref": "system"},
            ],
        },
    },
    "system": {
        "id": "system",
        "name": "Système",
        "color": "#36d1b7",
        "description": "Évalue la qualité technique d'un système ou d'un applicatif.",
        "criteria": [
            {"id": "reliability", "label": "Fiabilité & disponibilité",
             "detail": "Stabilité du système, taux de disponibilité, fréquence des incidents.",
             "weight": 1.3, "max": 10},
            {"id": "performance", "label": "Performance technique",
             "detail": "Temps de réponse, débit et tenue en charge du système.",
             "weight": 1.1, "max": 10},
            {"id": "security", "label": "Sécurité",
             "detail": "Robustesse face aux menaces : authentification, chiffrement, gestion des accès.",
             "weight": 1.3, "max": 10},
            {"id": "maintainability", "label": "Maintenabilité",
             "detail": "Facilité à faire évoluer, corriger et documenter le système.",
             "weight": 1.0, "max": 10},
            {"id": "scalability", "label": "Scalabilité",
             "detail": "Capacité à absorber une montée en charge sans dégradation.",
             "weight": 1.0, "max": 10},
        ],
        "scope": {
            "covered": [
                "Fiabilité et disponibilité",
                "Performance et scalabilité techniques",
                "Sécurité et maintenabilité",
            ],
            "excluded": [
                {"label": "L'organisation et le processus métier", "ref": "process"},
                {"label": "La satisfaction des utilisateurs finaux", "ref": "sentiment"},
            ],
        },
    },
    "sentiment": {
        "id": "sentiment",
        "name": "Sentiment client",
        "color": "#a78bfa",
        "description": "Évalue le ressenti et la satisfaction d'un client.",
        "criteria": [
            {"id": "satisfaction", "label": "Satisfaction globale",
             "detail": "Niveau de satisfaction exprimé par le client vis-à-vis du produit/service.",
             "weight": 1.3, "max": 10},
            {"id": "tone", "label": "Tonalité",
             "detail": "Tonalité générale des échanges : positive, neutre ou négative.",
             "weight": 1.0, "max": 10},
            {"id": "friction", "label": "Absence de friction",
             "detail": "Mesure l'absence de points de friction perçus dans le parcours client.",
             "weight": 1.1, "max": 10},
            {"id": "loyalty", "label": "Fidélité / recommandation",
             "detail": "Propension du client à rester et à recommander (logique NPS).",
             "weight": 1.2, "max": 10},
            {"id": "responsiveness", "label": "Réactivité perçue",
             "detail": "Perception de la rapidité et de la qualité des réponses reçues.",
             "weight": 0.9, "max": 10},
        ],
        "scope": {
            "covered": [
                "Satisfaction et tonalité",
                "Points de friction perçus",
                "Fidélité et réactivité ressentie",
            ],
            "excluded": [
                {"label": "Les causes liées au processus interne", "ref": "process"},
                {"label": "Les causes techniques sous-jacentes", "ref": "system"},
            ],
        },
    },
}


def list_templates():
    """Retourne les templates dans l'ordre, prêts pour l'API."""
    return [TEMPLATES[k] for k in ("process", "system", "sentiment")]


def get_template(template_id: str):
    return TEMPLATES.get(template_id)
