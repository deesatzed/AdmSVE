"""LLM port: stub determinism, default-to-stub, env config, cloud PHI gate."""

import pytest

from admission_engine.llm import StubLLMClient, get_client


def test_stub_is_deterministic_and_keyless():
    a = StubLLMClient().complete("chest pain troponin", system="extract")
    b = StubLLMClient().complete("chest pain troponin", system="extract")
    assert a.text == b.text
    assert a.provider == "stub"
    assert a.prompt_hash == b.prompt_hash


def test_default_client_is_stub_without_env(monkeypatch):
    monkeypatch.delenv("ADMISSION_ENGINE_LLM_PROVIDER", raising=False)
    # build_from_env loads .env once; ensure provider resolves to stub when unset.
    client = get_client()
    assert client.provider in ("stub",)  # no real provider configured by default


def test_force_stub_always_stub():
    assert get_client(force_stub=True).provider == "stub"


def test_unknown_provider_raises(monkeypatch):
    from admission_engine.llm.env_client import build_from_env

    monkeypatch.setenv("ADMISSION_ENGINE_LLM_PROVIDER", "nonsense")
    with pytest.raises(ValueError):
        build_from_env()


def test_cloud_provider_requires_model_and_key(monkeypatch):
    from admission_engine.llm.env_client import build_from_env

    monkeypatch.setenv("ADMISSION_ENGINE_LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError):
        build_from_env()  # no model/key -> refuse
