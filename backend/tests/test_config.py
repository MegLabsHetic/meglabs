import pytest

from app.core.config import (
    MODEL_ROUTING,
    Provider,
    Settings,
    Task,
    cost_in_cents,
    model_for,
    unpriced_routed_models,
)


def test_every_routed_model_has_a_price():
    """Une faute de frappe dans le routing rendrait le compteur de cout muet."""
    assert unpriced_routed_models() == []


def test_every_provider_covers_every_task():
    for provider in Provider:
        assert set(MODEL_ROUTING[provider]) == set(Task)


def test_classification_is_never_routed_to_a_costlier_model_than_sql():
    """La tache courte ne doit jamais couter plus cher que la tache lourde.

    L'egalite est acceptee : un fournisseur peut n'exposer qu'un seul modele — c'est
    le cas de Scaleway, dont le petit gpt-oss n'est pas propose en Serverless. On y
    perd le gain du routing, pas la coherence du routage.
    """
    for provider in Provider:
        courte = cost_in_cents(model_for(provider, Task.CLASSIFICATION), 1_000_000, 0)
        lourde = cost_in_cents(model_for(provider, Task.SQL_GENERATION), 1_000_000, 0)
        assert courte <= lourde, provider


def test_cost_is_computed_in_cents():
    # claude-sonnet-5 : 3 $ par million de tokens en entree, 15 $ en sortie.
    assert cost_in_cents("claude-sonnet-5", 1_000_000, 0) == pytest.approx(300.0)
    assert cost_in_cents("claude-sonnet-5", 0, 1_000_000) == pytest.approx(1500.0)
    assert cost_in_cents("claude-sonnet-5", 0, 0) == 0.0


def test_unknown_model_costs_nothing_rather_than_raising():
    assert cost_in_cents("modele-inexistant", 1_000, 1_000) == 0.0


def test_missing_api_key_names_the_variable_to_set():
    settings = Settings(anthropic_api_key="", openai_api_key="sk-test")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        settings.api_key_for(Provider.ANTHROPIC)

    assert settings.api_key_for(Provider.OPENAI) == "sk-test"


def test_cors_origins_are_split_and_trimmed():
    settings = Settings(cors_origins="http://a.test , http://b.test ,")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]
