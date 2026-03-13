# Backend Sistema Olimpíadas de Matemática

## Visão Geral

Backend moderno e performático para sistema de gestão de olimpíadas de matemática, desenvolvido com **FastAPI**, **PostgreSQL** e **Python 3.11+**. 

### Principais Funcionalidades

- **Autenticação JWT** com refresh tokens
- **Gestão de usuários** (Admin, Professor, Rvisor, Estudante)
- **CRUD completo de questões** matemáticas
- **Upload e processamento** de imagens
- **Suporte nativo ao LaTeX** para fórmulas
- **Geração de PDFs** profissionais
- **Sistema de provas** com questões ordenadas
- **Categorização avançada** de questões
- **Busca e filtros** poderosos
- **API documentada** automaticamente

## Tecnologias

- **Python 3.11+**
- **FastAPI** - Framework web moderno e rápido
- **PostgreSQL** - Banco de dados relacional robusto
- **SQLAlchemy** - ORM Python avançado
- **Pydantic** - Validação de dados com type hints
- **Alembic** - Migrações de banco de dados
- **Gunicorn** - Servidor WSGI para produção
- **Redis** - Cache e sessões
- **Docker** - Containerização

### Bibliotecas Matemáticas

- **SymPy** - Matemática simbólica
- **LaTeX** - Renderização de fórmulas
- **ReportLab** - Geração de PDFs profissionais
- **Pillow** - Processamento de imagens
- **NumPy** - Computação numérica

## Arquitetura

```
app/
├── main.py              # FastAPI app principal
├── config.py            # Configurações
├── database.py          # Conexão PostgreSQL
├── dependencies.py      # Dependencies FastAPI
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── api/v1/              # Rotas da API
├── services/            # Lógica de negócio
├── utils/               # Utilitários (LaTeX, PDF)
└── tests/               # Testes pytest
```

## Instalação Rápida

### Pré-requisitos

- Python 3.11+
- PostgreSQL 13+
- Redis (opcional, mas recomendado)
- Git

### 1. Clone o repositório

```bash
git clone <https://github.com/JoJoaoVictor/Backend-Olimpiadas-Matematica.git>
cd backend-olimpiadas-python
```

### 2. Crie ambiente virtual

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instale dependências

```bash
pip install -r requirements/development.txt
```

### 4. Configure variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas configurações:

```env
# Servidor
ENVIRONMENT=development
DEBUG=True
HOST=0.0.0.0
PORT=8000

# Banco PostgreSQL
DATABASE_URL=postgresql://olimpiadas_user:senha123@localhost:5432/olimpiadas_db

# Segurança (MUDE EM PRODUÇÃO!)
SECRET_KEY=sua-chave-super-secreta-aqui
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### 5. Configure o banco de dados

```bash
# Crie o banco PostgreSQL
createdb olimpiadas_db

# Execute migrações
alembic upgrade head

# Popule dados iniciais
python scripts/seed_database.py
```

### 6. Inicie o servidor

```bash
# Desenvolvimento (com hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Ou use o script de desenvolvimento
python -m uvicorn app.main:app --reload
```

Acesse: http://localhost:8000

- **Documentação interativa**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Instalação com Docker

### Docker Compose (Recomendado)

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

Isso irá subir:
- FastAPI app (porta 8000)
- PostgreSQL (porta 5432) 
- Redis (porta 6379)
- Nginx (portas 80/443 - apenas produção)

## Comandos Úteis

```bash
# Executar testes
pytest

# Testes com coverage
pytest --cov=app --cov-report=html

# Formatar código
black app/
isort app/

# Linter
flake8 app/

# Type checking
mypy app/

# Criar migração
alembic revision --autogenerate -m "Descrição da mudança"

# Aplicar migrações
alembic upgrade head

# Criar usuário admin
python scripts/create_admin.py

# Backup do banco
python scripts/backup_database.py
```

## Endpoints da API

###  Autenticação

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/v1/auth/register` | Registrar usuário |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/refresh` | Renovar token |
| GET | `/api/v1/auth/profile` | Perfil do usuário |
| PATCH | `/api/v1/auth/profile` | Atualizar perfil |
| POST | `/api/v1/auth/forgot-password` | Esqueci senha |
| POST | `/api/v1/auth/reset-password/{token}` | Resetar senha |

###  Usuários

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/api/v1/users` | Listar usuários | Admin |
| GET | `/api/v1/users/{id}` | Buscar usuário | Admin |
| PATCH | `/api/v1/users/{id}` | Atualizar usuário | Admin |
| DELETE | `/api/v1/users/{id}` | Remover usuário | Admin |

### Questões

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/api/v1/questions` | Listar questões | Professor+ |
| POST | `/api/v1/questions` | Criar questão | Professor+ |
| GET | `/api/v1/questions/{id}` | Buscar questão | Professor+ |
| PATCH | `/api/v1/questions/{id}` | Atualizar questão | Autor/Admin |
| DELETE | `/api/v1/questions/{id}` | Remover questão | Autor/Admin |
| POST | `/api/v1/questions/{id}/approve` | Aprovar questão | Admin |

### Provas

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/api/v1/exams` | Listar provas | Professor+ |
| POST | `/api/v1/exams` | Criar prova | Professor+ |
| GET | `/api/v1/exams/{id}` | Buscar prova | Professor+ |
| PATCH | `/api/v1/exams/{id}` | Atualizar prova | Autor/Admin |
| DELETE | `/api/v1/exams/{id}` | Remover prova | Autor/Admin |
| GET | `/api/v1/exams/{id}/pdf` | Gerar PDF | Professor+ |

### Imagens

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| POST | `/api/v1/images/upload` | Upload imagem | Professor+ |
| GET | `/api/v1/images/{id}` | Buscar imagem | Professor+ |
| DELETE | `/api/v1/images/{id}` | Remover imagem | Autor/Admin |

## Exemplos de Uso

### Registrar Usuário

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "João Professor",
    "email": "joao@escola.com",
    "password": "MinhaSenh@123",
    "role": "PROFESSOR"
  }'
```

### Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@escola.com",
    "password": "MinhaSenh@123"
  }'
```

### Criar Questão

```bash
curl -X POST "http://localhost:8000/api/v1/questions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  -d '{
    "name": "Equação do Segundo Grau",
    "professor_name": "João Professor",
    "serie_ano": "9º ano",
    "phase_level": "3ª fase",
    "difficulty_level": 3,
    "bncc_theme": "Álgebra",
    "knowledge_objects": "Equações quadráticas",
    "ability_code": "EF09MA09",
    "ability_description": "Resolver equações do 2º grau",
    "question_statement": "Resolva a equação x² - 5x + 6 = 0",
    "alternatives": "a) x = 1 e x = 6  b) x = 2 e x = 3  c) x = -2 e x = -3  d) x = 0 e x = 5  e) x = 1 e x = 5",
    "correct_alternative": "b",
    "detailed_resolution": "Usando a fórmula de Bhaskara...",
    "latex_formula": "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}",
    "category_id": 1,
    "grau_id": 2
  }'
```
### Estrutura de Testes

```
tests/
├── conftest.py          # Configurações pytest
├── test_auth.py         # Testes autenticação  
├── test_users.py        # Testes usuários
├── test_questions.py    # Testes questões
├── test_exams.py        # Testes provas
└── test_utils.py        # Testes utilitários
```

##  Monitoramento

### Logs Estruturados

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Usuário logado", extra={"user_id": 123, "email": "user@example.com"})
```

### Health Check

```bash
curl http://localhost:8000/health
```

Resposta:
```json
{
  "success": true,
  "status": "healthy", 
  "timestamp": 1640995200.0,
  "environment": "development",
  "version": "1.0.0"
}
```

### Métricas (Sentry)

Configure `SENTRY_DSN` no `.env` para monitoramento automático de erros.

# 1. Variáveis de Ambiente

```env
ENVIRONMENT=production
DEBUG=False
DATABASE_URL=postgresql://user:pass@hostname:5432/dbname
SECRET_KEY=chave-super-secreta-256-bits
SENTRY_DSN=https://key@sentry.io/project
```

### 2. Docker Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Serviços Externos

- **Banco**: PostgreSQL (AWS RDS, DigitalOcean, etc)
- **Cache**: Redis (ElastiCache, Redis Cloud)
- **Storage**: AWS S3, Cloudinary
- **Monitoramento**: Sentry, DataDog

##  Segurança

### Implementado

- ✅ Hash de senhas com bcrypt
- ✅ JWT com expiração configurable
- ✅ Rate limiting por IP
- ✅ Validação rigorosa de entrada
- ✅ Headers de segurança (CORS, CSP)
- ✅ SQL injection protection (SQLAlchemy)
- ✅ XSS protection (Pydantic escaping)

### Configurações de Produção

```python
# Senhas fortes obrigatórias
MIN_PASSWORD_LENGTH = 12

# Rate limiting
REQUESTS_PER_MINUTE = 60

# Tokens de vida curta
ACCESS_TOKEN_EXPIRE_MINUTES = 15
```

## Performance

### Otimizações

- **Async/Await**: Todas operações I/O são assíncronas
- **Connection Pooling**: Pool de conexões PostgreSQL
- **Query Optimization**: Eager loading, índices otimizados  
- **Caching**: Redis para dados frequentes
- **Compression**: Gzip para responses
- **CDN**: Imagens servidas via CDN

### Benchmarks

- **Throughput**: ~2000 req/s (4 cores)
- **Latência**: ~50ms (P95)
- **Memory**: ~256MB por worker

##  Troubleshooting

### Problemas Comuns

**1. Erro de conexão PostgreSQL**
```bash
# Verifique se PostgreSQL está rodando
pg_isready -h localhost -p 5432

# Teste conexão
psql postgresql://user:pass@localhost:5432/dbname
```

**2. Erro de migração Alembic**
```bash
# Reset migrações (cuidado em produção!)
alembic downgrade base
alembic upgrade head
```

**3. Token JWT inválido**
```python
# Gere nova SECRET_KEY
import secrets
print(secrets.token_urlsafe(32))
```

### Debug Mode

```bash
# Ative logs detalhados
DEBUG=True LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

## Contribuição

### Setup de Desenvolvimento

```bash
# Clone e configure
git clone <repo>
cd backend-olimpiadas-python

# Ambiente virtual
python -m venv venv
source venv/bin/activate

# Dependências de desenvolvimento
pip install -r requirements/development.txt

# Pre-commit hooks
pre-commit install

# Executar testes
pytest
```

### Padrões de Código

- **Black** para formatação
- **isort** para imports
- **flake8** para linting
- **mypy** para type checking
- **Conventional Commits** para mensagens

### Pull Requests

1. Fork o repositório
2. Crie branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'feat: adiciona nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra Pull Request

## Documentação Adicional

- [ **Guia de API**](docs/api.md) - Documentação completa da API
- [ **Deploy**](docs/deployment.md) - Guia de deploy detalhado
- [ **LaTeX**](docs/latex_support.md) - Suporte a fórmulas matemáticas
- [ **Testes**](docs/testing.md) - Guia de testes
- [ **Segurança**](docs/security.md) - Práticas de segurança


Este projeto está licenciado sob a [MIT License](LICENSE).
