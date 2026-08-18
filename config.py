import os

# ──────────────────────────────────────────────
# Chargement du fichier .env (cle API, etc.)
# ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # python-dotenv absent : on retombe sur les variables d'environnement

# ──────────────────────────────────────────────
# Claude API Configuration
# ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# claude-sonnet-4-20250514 est deprecie (retrait juin 2026) -> claude-sonnet-5
CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_MAX_TOKENS = 8192

# ──────────────────────────────────────────────
# App Configuration
# ──────────────────────────────────────────────
APP_NAME = "DataAnalyst AI"
APP_ICON = "\U0001f4ca"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Plateforme SaaS d'analyse de donnees intelligente propulsee par Claude AI"
MAX_UPLOAD_SIZE_MB = 200
SUPPORTED_EXTENSIONS = ["csv", "xlsx", "xls"]

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(_BASE_DIR, "data", "dataanalyst.db")
UPLOAD_DIR = os.path.join(_BASE_DIR, "data", "uploads")
EXPORT_DIR = os.path.join(_BASE_DIR, "data", "exports")

# ──────────────────────────────────────────────
# Agent temperature settings
# ──────────────────────────────────────────────
# Conserve pour compatibilite : les temperatures ne sont plus envoyees a
# l'API (rejetees par les modeles Claude recents) mais restent des attributs
# des agents.
AGENT_TEMPERATURES = {
    "orchestrator": 0.3,
    "profiler": 0.1,
    "cleaning": 0.1,
    "analysis": 0.4,
    "visualization": 0.3,
    "reporter": 0.2,
    "documentation": 0.2,
    "kpi": 0.3,
}

# ──────────────────────────────────────────────
# Subscription Tiers
# ──────────────────────────────────────────────
TIERS = {
    "free": {
        "name": "Gratuit",
        "max_uploads_per_day": 3,
        "max_file_size_mb": 10,
        "max_rows": 10_000,
        "ai_queries_per_day": 10,
        "export_formats": ["csv"],
        "features": ["profiling", "cleaning_manual", "basic_charts"],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 29,
        "max_uploads_per_day": 50,
        "max_file_size_mb": 100,
        "max_rows": 500_000,
        "ai_queries_per_day": 200,
        "export_formats": ["csv", "excel", "pdf"],
        "features": [
            "profiling", "cleaning_manual", "cleaning_ai",
            "basic_charts", "ai_dashboard", "segmentation",
            "time_analysis", "correlations", "export_reports",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 99,
        "max_uploads_per_day": -1,
        "max_file_size_mb": 500,
        "max_rows": -1,
        "ai_queries_per_day": -1,
        "export_formats": ["csv", "excel", "pdf"],
        "features": [
            "profiling", "cleaning_manual", "cleaning_ai",
            "basic_charts", "ai_dashboard", "segmentation",
            "time_analysis", "correlations", "export_reports",
            "geo_maps", "custom_agents", "api_access", "priority_support",
        ],
    },
}

# ──────────────────────────────────────────────
# Ensure directories exist
# ──────────────────────────────────────────────
for _dir in [os.path.dirname(DATABASE_PATH), UPLOAD_DIR, EXPORT_DIR]:
    os.makedirs(_dir, exist_ok=True)
