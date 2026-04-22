import psycopg2
conn = psycopg2.connect("postgresql://olimpiadas_user:SenhaForte123@localhost:5432/olimpiadas_db")
print("Conectado!")