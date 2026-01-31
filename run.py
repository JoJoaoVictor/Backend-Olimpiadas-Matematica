# run.py
import uvicorn
import sys
import asyncio

if __name__ == "__main__":
    # 1. Configura a política para Windows ANTES de qualquer coisa
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("🔧 Política de Eventos Windows configurada para Proactor (Suporte a PDF ativado).")

    print("🚀 Iniciando Servidor (Modo de Produção/Sem Reload)...")

    # 2. Inicia o servidor SEM o reload automático
    # Isso garante que o servidor rode no MESMO processo que configuramos acima.
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False, # <--- IMPORTANTE: Deve ser False para funcionar o PDF no Windows
        workers=1
    )