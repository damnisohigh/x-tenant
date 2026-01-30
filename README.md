## X-TENANT – Multi-tenant demo (Django + DRF)

This is a reference implementation of the test task: multi-tenant architecture with a core
database and per-tenant databases, authenticated access via JWT, and routing based on the
`X-TENANT` HTTP header.

### Tech stack

- **Framework**: Django 5 + Django REST Framework
- **Auth**: `djangorestframework-simplejwt` (JWT with `scope` and `tenant` claims)
- **DBs**:
  - by default: SQLite for quick start
  - optionally: PostgreSQL (see env configuration or use Docker)
- **Containerization**: Docker + Docker Compose (PostgreSQL setup included)

### Project layout

- **`xtenant/`**: Django project, settings and URLs
- **`core/`**:
  - `Organization` model (core DB)
  - API views for both core and tenant operations
- **`common/`**:
  - `middleware.py` – reads `X-TENANT` and sets tenant context
  - `tenant_db.py` – dynamic tenant DB config + provisioning
  - `db_router.py` – routes ORM operations to the current DB alias
  - `authentication.py` – JWT auth aware of core/tenant scope

### Installation

#### Option 1: Local development (Python venv)

```bash
git clone https://github.com/IGLEinvo/x-tenant x-tenant
cd x-tenant

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

#### Option 2: Docker (recommended for PostgreSQL)

The project includes `Dockerfile` and `docker-compose.yml` for easy setup with PostgreSQL.

**Prerequisites**: Docker and Docker Compose installed.

**Quick start**:

```bash
git clone https://github.com/IGLEinvo/x-tenant x-tenant
cd x-tenant

# Build and start services (PostgreSQL + Django app)
docker-compose up --build

# The API will be available at http://127.0.0.1:8000/api/
```

**Docker services**:

- **`db`**: PostgreSQL 15 container
  - Database: `xtenant_core`
  - User: `postgres` / Password: `postgres_pass`
  - Port: `5432` (exposed to host)

- **`web`**: Django application container
  - Automatically runs migrations on startup
  - Runs Django development server on port `8000`
  - Environment variables are pre-configured in `docker-compose.yml`

**Useful Docker commands**:

```bash
# Start services in background
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Run migrations manually
docker-compose exec web python manage.py migrate

# Run tests inside container
docker-compose exec web pytest

# Access Django shell
docker-compose exec web python manage.py shell

# Access PostgreSQL
docker-compose exec db psql -U postgres -d xtenant_core
```

**Note**: When using Docker, the `.env` file is not needed as all environment variables are set in `docker-compose.yml`. The PostgreSQL connection uses the service name `db` as the hostname.

If `CORE_DB_ENGINE` is not set, the app falls back to SQLite and uses file-based DBs
for tenants as well.

### Running migrations and server

#### Local development (venv)

```bash
source .venv/bin/activate

python manage.py migrate
python manage.py runserver 8000
```

The API will be available at `http://127.0.0.1:8000/api/`.

#### Docker

If using Docker, migrations run automatically on container startup. The server is already running after `docker-compose up`.

To run migrations manually:

```bash
docker-compose exec web python manage.py migrate
```

### API – Core operations (no `X-TENANT` header)

- **POST `/api/auth/register`**
  - Registers a **platform (core)** user in the core DB.
  - Body:
    ```json
    { "username": "owner", "email": "owner@example.com", "password": "secret123" }
    ```
  - Response: `201 Created` with JWT tokens (`scope: "core"`).

- **POST `/api/auth/login`**
  - Authenticates against the core DB.
  - Body:
    ```json
    { "username": "owner", "password": "secret123" }
    ```
  - Response: `200 OK` with JWT tokens (`scope: "core"`).

- **POST `/api/organizations`** (requires core JWT)
  - Creates a new organization and provisions a tenant database.
  - Headers:
    - `Authorization: Bearer <core-access-token>`
  - Body:
    ```json
    { "name": "Acme Corp" }
    ```
  - Flow:
    - Creates `Organization` in **core DB**
    - Computes `slug` (e.g. `acme-corp`) and tenant DB name
    - Provisions tenant database (creates DB for Postgres / file for SQLite)
    - Runs migrations on tenant DB
    - Copies the owner user record into tenant DB (same username/password hash)

### API – Tenant operations (with `X-TENANT` header)

All tenant requests must include:

- `X-TENANT: <org_slug>` (e.g. `acme-corp`)

The tenant DB is chosen by this header, and JWT tokens must have `scope: "tenant"`
and `tenant: "<org_slug>"`.

- **POST `/api/auth/register`**
  - Registers a **tenant user** in the tenant DB.
  - Headers:
    - `X-TENANT: <org_slug>`
  - Body:
    ```json
    { "username": "member", "email": "m@example.com", "password": "secret123" }
    ```

- **POST `/api/auth/login`**
  - Authenticates within the tenant DB.
  - Headers:
    - `X-TENANT: <org_slug>`
  - Body:
    ```json
    { "username": "owner", "password": "secret123" }
    ```
  - Response: JWT tokens with `scope: "tenant"` and `tenant: "<org_slug>"`.

- **GET `/api/users/me`**
  - Returns current tenant user profile.
  - Headers:
    - `X-TENANT: <org_slug>`
    - `Authorization: Bearer <tenant-access-token>`

- **PUT `/api/users/me`**
  - Updates current tenant user profile.
  - Headers:
    - `X-TENANT: <org_slug>`
    - `Authorization: Bearer <tenant-access-token>`
  - Body (example):
    ```json
    {
      "email": "owner-new@example.com",
      "first_name": "Alice",
      "last_name": "Owner"
    }
    ```

### Authentication & security details

- JWT tokens are issued with additional claims:
  - `scope`: `"core"` or `"tenant"`
  - `tenant`: tenant slug (only for tenant tokens)
- Middleware + auth rules:
  - If **no** `X-TENANT` → request is in **core** context; only tokens with `scope: "core"` are accepted.
  - If `X-TENANT` is set → request is in **tenant** context; only tokens with `scope: "tenant"` and
    `tenant == X-TENANT` are accepted.
- This guarantees that a tenant token cannot be reused in core context and cannot be used
  against a different tenant.

### Running tests

#### Local development (venv)

```bash
source .venv/bin/activate
pytest
```

#### Docker

```bash
docker-compose exec web pytest
```

Main integration test:

- `tests/test_core_tenant_flow.py`:
  - core register
  - core login
  - organization creation (provisions tenant DB and syncs owner)
  - tenant login
  - tenant register additional user
  - tenant `GET/PUT /api/users/me`

### Notes / possible extensions

- For a production setup you would:
  - use PostgreSQL for both core and tenant DBs
  - restrict DB users so tenants are fully isolated
  - add proper logging & audit trails
  - split core and tenant APIs into separate apps/services if needed.


