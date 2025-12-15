import sys
import os
from pathlib import Path

# Adicionar diretório atual ao path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print("🔍 Verificando importações...")
print(f"📁 Diretório: {current_dir}")
print(f"📂 Conteúdo: {list(current_dir.iterdir())}")

# Tentar importações uma por uma
modules_to_check = [
    "app.main",
    "app.database", 
    "app.models.base",
    "app.models.user",
    "app.models.question",
    "app.core.config"
]

for module in modules_to_check:
    try:
        __import__(module)
        print(f"✅ {module}")
    except ImportError as e:
        print(f"❌ {module}: {e}")

print("\n🎯 Se todas forem ✅, os testes então funcionar!")