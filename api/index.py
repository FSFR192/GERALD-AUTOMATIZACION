import os
import sys

# Agregar la raíz y src al path de Python para imports en Vercel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Forzar modo demo en serverless si no hay postgres externo
os.environ.setdefault("GERALD_MODO", "demo")

from gerald.api.main import app
