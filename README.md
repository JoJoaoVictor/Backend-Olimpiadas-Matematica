# Backend — Sistema de Olimpíadas de Matemática

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-17-336791?style=flat&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0+-CC2927?style=flat" />
  <img src="https://img.shields.io/badge/Alembic-1.13+-brightgreen?style=flat" />
  <img src="https://img.shields.io/badge/Playwright-Chromium-45ba4b?style=flat&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/status-em%20desenvolvimento-orange?style=flat" />
</p>

API REST desenvolvida com **FastAPI** para gestão completa de olimpíadas de matemática, incluindo banco de questões, geração de provas e geração de PDFs com suporte nativo a **LaTeX via MathJax + Playwright**.

---

## Sumário

- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Configuração](#instalação-e-configuração)
- [Estrutura de Diretórios](#estrutura-de-diretórios)
- [Banco de Dados e Migrações](#banco-de-dados-e-migrações)
- [Papéis e Permissões](#papéis-e-permissões)
- [Endpoints da API](#endpoints-da-api)
- [Geração de PDF](#geração-de-pdf)
- [Sistema de Notificações](#sistema-de-notificações)
- [Deploy em Produção](#deploy-em-produção)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Comandos Úteis](#comandos-úteis)

---

## Funcionalidades

- **Autenticação JWT** com access token (15 min) e refresh token (7 dias)
- **Login social via Google** (OAuth2 / Google Identity Services)
- **Controle de acesso por papéis** (RBAC) com 4 níveis: Admin, Revisor, Professor, Estudante
- **Banco de questões** com classificação BNCC (tema, objeto, habilidade), grau, dificuldade e LaTeX
- **Fluxo de revisão** — questões passam por pendente → revisado → aprovado com notificações automáticas ao autor
- **Montagem de provas** com ordenação de questões e restrição por papel
- **Geração de PDF** profissional com renderização LaTeX via MathJax + Playwright (Chromium headless)
- **Cabeçalho e rodapé customizáveis** por prova (upload de imagens em Base64)
- **Sistema de notificações** em tempo real (polling) para revisores e professores
- **Upload e processamento de imagens** para questões e layouts de prova
- **Recuperação de senha** por e-mail com token temporário (30 min)
- **Soft-delete seguro** — exclusão de usuário preserva histórico de questões e provas via `SET NULL` + campo `professor_name`

---

## Arquitetura

```
app/
├── main.py                  # Aplicação FastAPI, middlewares, roteamento
├── database.py              # Engine SQLAlchemy + pool de conexões
├── dependencies.py          # Guards de autenticação e RBAC (get_current_user, require_roles...)
│
├── api/v1/                  # Camada de rota (entrada HTTP)
│   ├── auth.py
│   ├── users.py
│   ├── questions.py
│   ├── exams.py
│   ├── images.py
│   ├── categories.py
│   ├── graus.py
│   └── notifications.py
│
├── models/                  # SQLAlchemy ORM
│   ├── base.py              # BaseModel com id, created_at, updated_at
│   ├── user.py              # User + UserRole enum
│   ├── question.py          # Question + reviewed_by_id (rastreamento de revisão)
│   ├── exam.py              # Exam + author_name (snapshot histórico)
│   ├── associations.py      # ExamQuestion (N:N com order_index)
│   ├── notification.py      # Notification + NotificationType enum
│   ├── category.py
│   ├── grau.py
│   └── image.py
│
├── schemas/                 # Pydantic v2 (validação e serialização)
│   ├── question.py          # QuestionCreate, QuestionUpdate, QuestionFilters, QuestionResponse
│   ├── exam.py              # ExamCreate, ExamUpdate, ExamResponse, ExamLayoutUpdate
│   ├── user.py              # UserCreate, UserResponse, ChangePassword...
│   ├── notification.py
│   └── ...
│
├── services/                # Regras de negócio
│   ├── question_service.py  # Filtros por role, reviewed_by_id, notificações
│   ├── exam_service.py      # Montagem de provas, layout, PDF trigger
│   ├── auth_service.py      # Login, Google OAuth, refresh, reset de senha
│   ├── notification_service.py
│   ├── image_service.py
│   └── user_service.py
│
├── core/
│   ├── config.py            # Settings via pydantic-settings (.env)
│   ├── security.py          # JWT, hash de senha (sha256_crypt + bcrypt legado)
│   ├── exceptions.py        # AppException, NotFoundException, ForbiddenException...
│   └── mail.py              # Envio de e-mail (recuperação de senha)
│
└── utils/
    ├── pdf_generator.py     # Geração de PDF com Playwright + MathJax
    ├── playwright_manager.py
    ├── image_processor.py
    └── latex_renderer.py
```

---

## Pré-requisitos

| Componente | Versão mínima |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 16+ (recomendado: 17) |
| Node.js | 18+ (apenas para build do frontend) |
| Chromium (via Playwright) | instalado automaticamente |

---

## Instalação e Configuração

### 1. Clone o repositório

```bash
git clone https://github.com/JoJoaoVictor/Backend-Olimpiadas-Matematica.git
cd Backend-Olimpiadas-Matematica
```

### 2. Crie o ambiente virtual

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements/development.txt
```

### 4. Instale o Playwright + Chromium

```bash
playwright install chromium
playwright install-deps chromium
```

### 5. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas configurações (veja a seção [Variáveis de Ambiente](#variáveis-de-ambiente)).

### 6. Configure o banco e aplique as migrações

```bash
# Crie o banco no PostgreSQL
createdb olimpiadas_db

# Execute os scripts de migração de colunas adicionadas após a criação inicial
python scripts/add_reviewed_by_column.py
python scripts/add_exam_author_name_column.py

# Aplique todas as migrações Alembic
alembic upgrade head

# Popule dados iniciais (categorias, graus)
python scripts/seed_database.py

# Crie o primeiro usuário administrador
python scripts/create_admin.py
```

### 7. Inicie o servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse:
- **API**: http://localhost:8000
- **Documentação interativa (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Estrutura de Diretórios

```
/
├── app/                     # Código da aplicação (ver Arquitetura acima)
├── alembic/                 # Migrações de banco
│   └── versions/
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── scripts/                 # Scripts utilitários
│   ├── create_admin.py
│   ├── seed_database.py
│   ├── add_reviewed_by_column.py
│   ├── add_exam_author_name_column.py
│   ├── backup_database.py
│   └── migrate_from_json.py
├── uploads/                 # Imagens enviadas (criado automaticamente)
│   ├── images/
│   └── layouts/
│       ├── header/
│       └── footer/
├── .env.example
├── alembic.ini
└── requirements.txt         # Aponta para requirements/base.txt
```

---

## Banco de Dados e Migrações

O projeto usa **Alembic** para versionamento do esquema. Após qualquer alteração nos models, gere uma nova migração:

```bash
alembic revision --autogenerate -m "descricao_da_mudanca"
alembic upgrade head
```

### Colunas adicionadas após criação inicial

Duas colunas foram adicionadas via scripts independentes (compatível com bancos existentes):

| Script | Tabela | Coluna | Finalidade |
|---|---|---|---|
| `add_reviewed_by_column.py` | `questions` | `reviewed_by_id` | Rastreia qual revisor aprovou a questão |
| `add_exam_author_name_column.py` | `exams` | `author_name` | Snapshot do nome do autor para preservar histórico |

### Deleção segura de usuários

Todos os relacionamentos com `users.id` foram configurados com `ondelete` explícito para que a exclusão de um usuário não quebre dados históricos:

| Tabela | Comportamento ao deletar usuário |
|---|---|
| `questions.author_id` | `SET NULL` — questão permanece, `professor_name` preserva o nome |
| `questions.reviewed_by_id` | `SET NULL` — questão permanece sem revisor rastreado |
| `exams.author_id` | `SET NULL` — prova permanece, `author_name` preserva o nome |
| `notifications.user_id` | `CASCADE` — notificações do usuário são removidas junto |
| `notifications.triggered_by_user_id` | `SET NULL` — notificação permanece sem remetente |

---

## Papéis e Permissões

| Ação | STUDENT | PROFESSOR | REVISOR | ADMIN |
|---|:---:|:---:|:---:|:---:|
| Ver questões pendentes | Só as próprias | Todas | Todas | Todas |
| Ver questões aprovadas | Só as próprias | Todas | Só as que aprovou | Todas |
| Criar questão | ✅ | ✅ | ✅ | ✅ |
| Editar questão | Só a própria (pendente) | Só a própria | Qualquer | Qualquer |
| Aprovar questão | ✗ | ✗ | ✅ | ✅ |
| Gerenciar provas | ✗ | ✅ (próprias) | ✅ (qualquer) | ✅ |
| Painel administrativo | ✗ | ✗ | ✗ | ✅ |

> **Fluxo de revisão:** Questão criada → status *pendente* → REVISOR comenta/aprova → notificação enviada ao autor → autor pode corrigir enquanto pendente → REVISOR reanalisa → aprovada.

---

## Endpoints da API

### Autenticação

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Registrar usuário |
| `POST` | `/api/v1/auth/login` | Login com e-mail e senha |
| `POST` | `/api/v1/auth/google` | Login via Google OAuth |
| `POST` | `/api/v1/auth/refresh` | Renovar access token |
| `POST` | `/api/v1/auth/forgot-password` | Solicitar reset de senha |
| `POST` | `/api/v1/auth/reset-password/{token}` | Redefinir senha |

### Usuários

| Método | Endpoint | Permissão |
|---|---|---|
| `GET` | `/api/v1/users/me` | Autenticado |
| `PUT` | `/api/v1/users/me` | Autenticado |
| `POST` | `/api/v1/users/change-password` | Autenticado |
| `GET` | `/api/v1/users` | Admin |
| `POST` | `/api/v1/users` | Admin |
| `GET` | `/api/v1/users/{id}` | Admin |
| `PATCH` | `/api/v1/users/{id}` | Admin |
| `PUT` | `/api/v1/users/{id}/role` | Admin |
| `DELETE` | `/api/v1/users/{id}` | Admin |

### Questões

| Método | Endpoint | Permissão |
|---|---|---|
| `GET` | `/api/v1/questions` | Autenticado (filtrado por role) |
| `POST` | `/api/v1/questions` | Autenticado |
| `GET` | `/api/v1/questions/{id}` | Autenticado (ownership verificado) |
| `PATCH` | `/api/v1/questions/{id}` | Autenticado (ownership verificado) |
| `DELETE` | `/api/v1/questions/{id}` | Autenticado (ownership verificado) |
| `POST` | `/api/v1/questions/{id}/approve` | Revisor, Admin |

### Provas

| Método | Endpoint | Permissão |
|---|---|---|
| `GET` | `/api/v1/exams` | Professor+ |
| `POST` | `/api/v1/exams` | Professor+ |
| `GET` | `/api/v1/exams/{id}` | Professor+ |
| `PATCH` | `/api/v1/exams/{id}` | Autor / Revisor / Admin |
| `DELETE` | `/api/v1/exams/{id}` | Autor / Revisor / Admin |
| `GET` | `/api/v1/exams/{id}/pdf` | Professor+ |
| `POST` | `/api/v1/exams/{id}/layout` | Autor / Revisor / Admin |
| `PATCH` | `/api/v1/exams/{id}/questions` | Autor / Revisor / Admin |
| `PATCH` | `/api/v1/exams/{id}/status` | Professor+ |

### Notificações

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/notifications` | Listar notificações do usuário logado |
| `PATCH` | `/api/v1/notifications/{id}/read` | Marcar como lida |
| `PATCH` | `/api/v1/notifications/read-all` | Marcar todas como lidas |

### Auxiliares

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/categories` | Listar categorias de questão |
| `GET` | `/api/v1/graus` | Listar graus escolares |
| `POST` | `/api/v1/images/upload` | Upload de imagem |
| `GET` | `/api/v1/images/{id}` | Buscar imagem |
| `GET` | `/health` | Health check |

---

## Geração de PDF

O sistema utiliza **Playwright (Chromium headless)** para renderizar HTML com **MathJax** e gerar PDFs de alta qualidade. O fluxo é:

1. Backend monta o HTML da prova com as questões e fórmulas LaTeX
2. Playwright abre o HTML em um browser headless
3. MathJax renderiza todas as fórmulas matematicamente
4. `page.pdf()` exporta o documento final em A4

```python
# Exemplo de uso (app/utils/pdf_generator.py)
browser = await playwright.chromium.launch(headless=True)
page = await browser.new_page()
await page.goto(html_url, timeout=60000)
await page.wait_for_function("window.MathJax && MathJax.typesetPromise", timeout=30000)
pdf_bytes = await page.pdf(format="A4", print_background=True)
```

> O endpoint `GET /api/v1/exams/{id}/pdf` retorna o PDF diretamente como blob (`application/pdf`).

---

## Sistema de Notificações

Notificações são geradas automaticamente pelos services quando:

| Evento | Destinatário |
|---|---|
| Questão revisada por REVISOR/ADMIN | Autor da questão |
| Comentário adicionado à questão | Autor da questão |
| Questão aprovada | Autor da questão |
| Prova revisada/alterada por REVISOR/ADMIN | Autor da prova |

O frontend consome via **polling** (requisição periódica a `GET /api/v1/notifications`). Quando `is_read = false`, o sino de notificações exibe o contador de não lidas.

---

## Deploy em Produção

### Stack de produção

```
Internet → Nginx (HTTPS/443) → Gunicorn (9 workers) → FastAPI → PostgreSQL 17
                              ↳ /uploads/ → arquivos estáticos
                              ↳ /         → React SPA (build)
```

### Passos resumidos

```bash
# 1. Instalar dependências de produção
pip install -r requirements/production.txt

# 2. Configurar variáveis de ambiente (.env.production)
cp .env.example .env.production

# 3. Aplicar migrações no banco de produção
alembic upgrade head

# 4. Iniciar com Gunicorn
gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 9 \
  --bind 127.0.0.1:8000 \
  --timeout 120
```

Consulte o **[Guia Técnico de Deploy](docs/deploy_guide.docx)** para o processo completo, incluindo:
- Migração SQLite → PostgreSQL (estrutura + dados)
- Configuração do PostgreSQL 17 no Ubuntu Server 24.04 LTS
- Serviço systemd para autostart
- Configuração completa do Nginx (proxy reverso + SSL)
- Configuração do Playwright no servidor
- Firewall, rate limiting e boas práticas de segurança

---

## Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha:

```env
# Aplicação
ENVIRONMENT=development           # development | production
DEBUG=True

# Banco de dados
DATABASE_URL=postgresql://olimpiadas_user:senha@localhost:5432/olimpiadas_db

# Segurança JWT
SECRET_KEY=                       # gere com: openssl rand -hex 64
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google OAuth (opcional)
GOOGLE_CLIENT_ID=

# CORS (lista separada por vírgula em produção)
ALLOWED_ORIGINS=http://localhost:5173

# Armazenamento
UPLOAD_PATH=./uploads

# Playwright
PLAYWRIGHT_BROWSERS_PATH=         # deixe vazio para usar o padrão
```

> **Nunca comite o arquivo `.env` ou `.env.production` no repositório.** Ambos estão no `.gitignore`.

---

## Comandos Úteis

```bash
# Desenvolvimento
uvicorn app.main:app --reload

# Gerar nova migração
alembic revision --autogenerate -m "descricao"

# Aplicar migrações
alembic upgrade head

# Reverter última migração
alembic downgrade -1

# Ver histórico de migrações
alembic history --verbose

# Criar admin
python scripts/create_admin.py

# Seed de dados iniciais
python scripts/seed_database.py

# Backup do banco
python scripts/backup_database.py

# Executar testes
pytest

# Testes com cobertura
pytest --cov=app --cov-report=html
```

---

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).
