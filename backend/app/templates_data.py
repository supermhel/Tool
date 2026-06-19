"""Built-in evaluation templates.

Each template has a list of criteria. Each criterion has:
- id           : stable identifier
- label        : short display title
- detail       : description of exactly what is measured
- weight       : relative weight in the score (normalised at calculation time)
- max          : maximum slider value (scale 0..max)

Each template also declares its scope: `covered` (what it evaluates) and
`excluded` (what it does not cover, with a pointer to the appropriate template).
"""

TEMPLATES = {
    "process": {
        "id": "process",
        "name": "Process",
        "color": "#5b8cff",
        "description": "Evaluates the maturity and efficiency of a business process.",
        "criteria": [
            {"id": "steps", "label": "Step clarity",
             "detail": "Are the process steps clearly defined, ordered, and unambiguous?",
             "weight": 1.0, "max": 10},
            {"id": "bottlenecks", "label": "Bottlenecks & delays",
             "detail": "Measures the absence of blocking points and adherence to target timelines.",
             "weight": 1.2, "max": 10},
            {"id": "compliance", "label": "Rules compliance",
             "detail": "Does the process comply with applicable business, legal, and internal rules?",
             "weight": 1.0, "max": 10},
            {"id": "automation", "label": "Automation",
             "detail": "Share of automated vs. manual low-value tasks.",
             "weight": 0.8, "max": 10},
            {"id": "repeatability", "label": "Repeatability",
             "detail": "Does the process consistently produce the same outcome when replayed?",
             "weight": 1.0, "max": 10},
        ],
        "scope": {
            "covered": [
                "Step sequencing and clarity",
                "Bottlenecks and delays",
                "Business rules compliance",
                "Automation level and repeatability",
            ],
            "excluded": [
                {"label": "User sentiment about the process", "ref": "sentiment"},
                {"label": "Technical quality of supporting tools", "ref": "system"},
            ],
        },
    },
    "system": {
        "id": "system",
        "name": "System",
        "color": "#36d1b7",
        "description": "Evaluates the technical quality of a system or application.",
        "criteria": [
            {"id": "reliability", "label": "Reliability & uptime",
             "detail": "System stability, availability rate, and incident frequency.",
             "weight": 1.3, "max": 10},
            {"id": "performance", "label": "Technical performance",
             "detail": "Response times, throughput, and load capacity.",
             "weight": 1.1, "max": 10},
            {"id": "security", "label": "Security",
             "detail": "Robustness against threats: authentication, encryption, access control.",
             "weight": 1.3, "max": 10},
            {"id": "maintainability", "label": "Maintainability",
             "detail": "Ease of evolving, fixing, and documenting the system.",
             "weight": 1.0, "max": 10},
            {"id": "scalability", "label": "Scalability",
             "detail": "Ability to absorb increased load without degradation.",
             "weight": 1.0, "max": 10},
        ],
        "scope": {
            "covered": [
                "Reliability and uptime",
                "Performance and technical scalability",
                "Security and maintainability",
            ],
            "excluded": [
                {"label": "Business process organisation", "ref": "process"},
                {"label": "End-user satisfaction", "ref": "sentiment"},
            ],
        },
    },
    "sentiment": {
        "id": "sentiment",
        "name": "Customer sentiment",
        "color": "#a78bfa",
        "description": "Evaluates the perception and satisfaction of a customer.",
        "criteria": [
            {"id": "satisfaction", "label": "Overall satisfaction",
             "detail": "Level of satisfaction expressed by the customer about the product or service.",
             "weight": 1.3, "max": 10},
            {"id": "tone", "label": "Tone",
             "detail": "General tone of interactions: positive, neutral, or negative.",
             "weight": 1.0, "max": 10},
            {"id": "friction", "label": "Absence of friction",
             "detail": "Measures the absence of perceived friction points in the customer journey.",
             "weight": 1.1, "max": 10},
            {"id": "loyalty", "label": "Loyalty / recommendation",
             "detail": "Customer propensity to stay and recommend (NPS logic).",
             "weight": 1.2, "max": 10},
            {"id": "responsiveness", "label": "Perceived responsiveness",
             "detail": "Perception of the speed and quality of responses received.",
             "weight": 0.9, "max": 10},
        ],
        "scope": {
            "covered": [
                "Satisfaction and tone",
                "Perceived friction points",
                "Loyalty and perceived responsiveness",
            ],
            "excluded": [
                {"label": "Root causes related to internal processes", "ref": "process"},
                {"label": "Underlying technical causes", "ref": "system"},
            ],
        },
    },
}


def list_templates():
    """Return templates in order, ready for the API."""
    return [TEMPLATES[k] for k in ("process", "system", "sentiment")]


def get_template(template_id: str):
    return TEMPLATES.get(template_id)
