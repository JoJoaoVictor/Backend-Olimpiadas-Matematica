import sqlite3
import psycopg2
from psycopg2.extras import Json
import json
import ast
import psycopg2.errors  

SQLITE_PATH = "./test.db"
PG_DSN = "postgresql://olimpiadas_user:SenhaForte123@localhost:5432/olimpiadas_db"

TABLES = [
    "graus",
    "categories",
    "users",
    "images",
    "questions",
    "exams",
    "notifications",
    "exam_questions"
]

def get_pg_columns(pg_cur, table):
    pg_cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    return {row[0] for row in pg_cur.fetchall()}

def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(PG_DSN)
    pg_conn.autocommit = False

    boolean_fields = [
        "is_active", "is_admin", "is_verified", "is_public",
        "is_email_verified", "is_superuser", "is_staff",
        "reviewed", "published", "is_correct", "is_read"
    ]

    with pg_conn.cursor() as pg_cur:
        for table in TABLES:
            rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                continue

            pg_cols = get_pg_columns(pg_cur, table)
            all_cols = rows[0].keys()
            cols_to_insert = [c for c in all_cols if c in pg_cols]

            if not cols_to_insert:
                print(f"⚠️ {table}: nenhuma coluna compatível, pulando")
                continue

            placeholders = ",".join(["%s"] * len(cols_to_insert))
            col_names = ",".join(cols_to_insert)

            with pg_conn.cursor() as insert_cur:
                for row in rows:
                    values = []
                    for col in cols_to_insert:
                        val = row[col]
                        if col in boolean_fields and isinstance(val, int):
                            val = bool(val)
                        if col == "anos":
                            if isinstance(val, str):
                                try:
                                    val = ast.literal_eval(val)
                                except:
                                    try:
                                        val = json.loads(val)
                                    except:
                                        val = []
                            elif val is None:
                                val = []
                            val = Json(val)
                        values.append(val)

                    try:
                        insert_cur.execute(
                            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                            values
                        )
                    except psycopg2.errors.ForeignKeyViolation:
                        # Ignora registros com chave estrangeira inválida
                        pg_conn.rollback()
                    except Exception as e:
                        print(f"Erro na tabela {table}: {e}")
                        pg_conn.rollback()

        # Atualiza sequences
        for table in TABLES:
            try:
                pg_cur.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1))
                """)
                pg_conn.commit()
            except:
                pass
        print("🎉 Migração concluída.")

if __name__ == "__main__":
    migrate()