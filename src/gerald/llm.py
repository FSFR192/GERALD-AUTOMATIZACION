"""get_llm(): modelo intercambiable (Gemini con visión u Ollama local) y traducción de errores."""

from typing import Any

from gerald.config import settings
from gerald.errores import ErrorSistema, ErrorTransitorio


def get_llm(rol: str = "general"):
    """Devuelve un ChatModel de LangChain según GERALD_LLM_PROVEEDOR. `rol` sirve para trazas."""
    cfg = settings()
    if cfg.llm_proveedor == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if cfg.google_api_key is None:
            raise ErrorSistema("llm", "falta GERALD_GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(
            model=cfg.modelo_google,
            api_key=cfg.google_api_key.get_secret_value(),
            temperature=0,
            timeout=30,
            max_retries=0,  # los reintentos los gestiona RetryPolicy del grafo
        ).with_config(tags=[f"rol:{rol}"])
    from langchain_ollama import ChatOllama

    return ChatOllama(model=cfg.modelo_ollama, temperature=0).with_config(tags=[f"rol:{rol}"])


def invocar_con_errores(modelo: Any, mensajes: Any, origen: str) -> Any:
    """Invoca el modelo y traduce errores técnicos a la jerarquía de P05."""
    try:
        return modelo.invoke(mensajes)
    except TimeoutError as exc:
        raise ErrorTransitorio(origen, "tiempo de espera del modelo agotado") from exc
    except Exception as exc:
        texto = str(exc).lower()
        if any(c in texto for c in ("429", "503", "unavailable", "rate limit", "timeout")):
            raise ErrorTransitorio(origen, "servicio del modelo no disponible") from exc
        if any(c in texto for c in ("quota", "cuota", "401", "403", "permission", "api key")):
            raise ErrorSistema(origen, "cuota agotada o credencial inválida del modelo") from exc
        raise
