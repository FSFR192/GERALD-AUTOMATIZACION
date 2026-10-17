"""Configuración: secretos desde variables de entorno y parámetros de negocio (P03)."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Parametros(BaseModel):
    """Parámetros de la política. En producción se cargan de la tabla `parametros`."""

    umbral_costo_pen: Decimal = Decimal("300.00")
    merma_pct: Decimal = Decimal("8")
    puntaje_minimo_alta: float = 0.85
    puntaje_minimo_media: float = 0.60
    sla_revision_horas: int = 24
    sla_aceptacion_horas: int = 48
    max_reprocesos: int = 3


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GERALD_", extra="ignore")

    modo: Literal["produccion", "demo"] = "produccion"
    database_url: SecretStr = SecretStr("postgresql://gerald:gerald@localhost:5432/gerald")
    jwt_secreto: SecretStr = SecretStr("solo-desarrollo-local-cambiar-en-env-0000")  # ≥ 32 bytes
    llm_proveedor: Literal["google", "ollama"] = "google"
    google_api_key: SecretStr | None = None
    modelo_google: str = "gemini-2.5-flash"
    modelo_ollama: str = "llava"
    dir_bocetos: str = "./data/bocetos"
    tamano_max_mb: int = 10
    limite_por_minuto: int = 10
    smtp_host: str = "localhost"
    correo_admin: str = "admin@geraldsport.pe"
    correo_almacen: str = "almacen@geraldsport.pe"

    @field_validator("google_api_key", mode="before")
    @classmethod
    def _clave_vacia_es_ausente(cls, valor: object) -> object:
        """`GERALD_GOOGLE_API_KEY=` (vacía) equivale a no configurada → ErrorSistema claro en get_llm()."""
        return None if isinstance(valor, str) and not valor.strip() else valor


@lru_cache
def settings() -> Settings:
    return Settings()
