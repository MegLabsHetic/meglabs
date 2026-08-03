"""Configuration applicative : environnement, routing des modeles, tarifs fournisseurs.

Le routing tache -> modele et les tarifs vivent ici et nulle part ailleurs : un agent
ne choisit jamais son modele lui-meme, sinon l'arbitrage cout/latence devient
impossible a relire et a modifier.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class Provider(str, Enum):
    """Fournisseurs LLM supportes."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GROQ = "groq"


class Task(str, Enum):
    """Ce que le LLM doit faire. Le modele decoule de la tache, jamais de l'agent."""

    CLASSIFICATION = "classification"
    SQL_GENERATION = "sql_generation"
    INTERPRETATION = "interpretation"
    REPORT = "report"


class ModelPrice(NamedTuple):
    """Tarif public d'un modele, en dollars par million de tokens."""

    input_per_mtok: float
    output_per_mtok: float


# Tarifs releves le 2026-08-03 sur les pages officielles des trois fournisseurs.
# A reverifier a chaque evolution de catalogue : un tarif perime fausse le compteur
# de cout, qui est montre au jury.
MODEL_PRICING: dict[str, ModelPrice] = {
    "claude-opus-5": ModelPrice(5.00, 25.00),
    "claude-sonnet-5": ModelPrice(3.00, 15.00),
    "claude-haiku-4-5": ModelPrice(1.00, 5.00),
    "gpt-5.6-sol": ModelPrice(5.00, 30.00),
    "gpt-5.6-terra": ModelPrice(2.00, 12.00),
    "gpt-5.6-luna": ModelPrice(0.20, 1.20),
    "openai/gpt-oss-120b": ModelPrice(0.15, 0.60),
    "openai/gpt-oss-20b": ModelPrice(0.075, 0.30),
}


# Le petit modele traite ce qui est court et cadre (classer une intention), le grand
# ce qui demande du raisonnement (ecrire du SQL, interpreter, rediger).
MODEL_ROUTING: dict[Provider, dict[Task, str]] = {
    Provider.ANTHROPIC: {
        Task.CLASSIFICATION: "claude-haiku-4-5",
        Task.SQL_GENERATION: "claude-sonnet-5",
        Task.INTERPRETATION: "claude-sonnet-5",
        Task.REPORT: "claude-sonnet-5",
    },
    Provider.OPENAI: {
        Task.CLASSIFICATION: "gpt-5.6-luna",
        Task.SQL_GENERATION: "gpt-5.6-terra",
        Task.INTERPRETATION: "gpt-5.6-terra",
        Task.REPORT: "gpt-5.6-terra",
    },
    Provider.GROQ: {
        Task.CLASSIFICATION: "openai/gpt-oss-20b",
        Task.SQL_GENERATION: "openai/gpt-oss-120b",
        Task.INTERPRETATION: "openai/gpt-oss-120b",
        Task.REPORT: "openai/gpt-oss-120b",
    },
}


class Settings(BaseSettings):
    """Parametres lus depuis l'environnement. Aucune valeur par defaut n'est un secret."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    llm_provider: Provider = Provider.ANTHROPIC
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""

    database_url: str = "sqlite+aiosqlite:///./meglabs.db"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    storage_dir: Path = Path("./storage")

    max_file_size_mb: int = 100
    max_rows: int = 1_000_000
    min_rows_for_ml: int = 50
    max_sql_result_rows: int = 500
    duckdb_timeout_seconds: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        """Les origines autorisees, saisies en une chaine separee par des virgules."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def api_key_for(self, provider: Provider) -> str:
        """Retourne la cle du fournisseur, ou leve si elle n'est pas configuree."""
        keys = {
            Provider.ANTHROPIC: self.anthropic_api_key,
            Provider.OPENAI: self.openai_api_key,
            Provider.GROQ: self.groq_api_key,
        }
        key = keys[provider]
        if not key:
            raise RuntimeError(
                f"Aucune cle API configuree pour {provider.value}. "
                f"Renseigne {provider.value.upper()}_API_KEY dans .env."
            )
        return key


def model_for(provider: Provider, task: Task) -> str:
    """Le modele a utiliser pour cette tache chez ce fournisseur."""
    return MODEL_ROUTING[provider][task]


def cost_in_cents(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cout d'un appel en centimes de dollar.

    Un modele inconnu vaut zero plutot que de faire echouer la requete : perdre la
    mesure de cout est genant, perdre la reponse de l'utilisateur l'est davantage.
    """
    price = MODEL_PRICING.get(model)
    if price is None:
        return 0.0
    dollars = (tokens_in * price.input_per_mtok + tokens_out * price.output_per_mtok) / 1_000_000
    return dollars * 100


def unpriced_routed_models() -> list[str]:
    """Modeles routes dont le tarif manque — une faute de frappe se voit ici."""
    routed = {model for per_task in MODEL_ROUTING.values() for model in per_task.values()}
    return sorted(routed - set(MODEL_PRICING))


@lru_cache
def get_settings() -> Settings:
    """Instance unique, mise en cache : la lecture de l'environnement se fait une fois."""
    return Settings()
