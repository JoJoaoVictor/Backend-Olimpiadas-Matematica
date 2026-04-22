import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="olimpiadas_user",
        password="SenhaForte123",
        database="olimpiadas_db"
    )
    print("✅ Conexão bem‑sucedida!")
    conn.close()
except Exception as e:
    print("❌ Falha na conexão:", e)