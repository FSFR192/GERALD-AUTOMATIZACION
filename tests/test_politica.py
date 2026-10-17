"""Ruta 11: límites de la política determinista."""

from decimal import Decimal

import pytest

from gerald.config import Parametros
from gerald.decision.politica import evaluar
from gerald.schemas.resultados import Decision

P = Parametros()


def dec(puntaje: float, coherente: bool = True) -> Decision:
    return Decision(coherente=coherente, puntaje=puntaje, confianza="alta")


@pytest.mark.parametrize(
    ("costo", "esperado"),
    [
        ("299.99", "aprobar"),
        ("300.00", "aprobar"),
        ("300.01", "revision"),
    ],
)
def test_umbral_de_costo(costo, esperado):
    assert evaluar(dec(0.95), Decimal(costo), P).veredicto == esperado


@pytest.mark.parametrize(
    ("puntaje", "veredicto", "confianza"),
    [
        (0.85, "aprobar", "alta"),
        (0.84, "revision", "media"),
        (0.59, "revision", "baja"),
    ],
)
def test_confianza_se_recalcula_desde_el_puntaje(puntaje, veredicto, confianza):
    v = evaluar(dec(puntaje), Decimal("100"), P)
    assert (v.veredicto, v.confianza) == (veredicto, confianza)


def test_incoherente_siempre_observa():
    assert evaluar(dec(0.99, coherente=False), Decimal("10"), P).veredicto == "observar"
