# AuthMicroservice

Microservicio de autenticación de operadores internos (asesores, comerciales y telemarketing) del CRM. Construido con **FastAPI**, emite **JWT** (access + refresh) y persiste sus datos en un schema propio `auth` de la base **Supabase compartida** (mismo patrón que `clientes`, `vehiculos` y `calificacion`).

Solo API + DB. No usa Kafka.

## Stack

- Python 3.12+
- FastAPI + SQLAlchemy 2.0 + Pydantic v2
- PyJWT (JWT HS256) + bcrypt (hash de contraseñas)
- PostgreSQL (Supabase), schema `auth`

## Variables de entorno

Copia el archivo de ejemplo y ajusta los valores:

```bash
cp .env.example .env
```

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión (pooler de Supabase) | `postgresql://user:pass@host:5432/postgres` |
| `DB_SCHEMA` | Schema donde vive este servicio | `auth` |
| `JWT_SECRET` | **Obligatoria.** Clave para firmar los JWT (HS256), de **32 caracteres o más**. El servicio no arranca si falta, es corta o es la del `.env.example`. El orquestador necesita la misma para validar los tokens | `openssl rand -base64 48` |
| `JWT_ALGORITHM` | Algoritmo del JWT | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Vida del access token (minutos) | `15` (por defecto) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Vida del refresh token (días) | `7` |
| `FRONTEND_LIST` | Orígenes permitidos para CORS | `["http://localhost:5173"]` |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | (Opcional) Crea un ADMIN al arrancar si no existe | `admin@example.com` / `...` |

## Modelo de datos (schema `auth`)

- `usuarios` — operadores internos con `rol` (`ADMIN`, `ASESOR`, `COMERCIAL`, `TELEMARKETING`) y `password_hash` bcrypt.
- `refresh_tokens` — solo el hash SHA-256 del refresh token (nunca el token en claro), con rotación en cada `/refresh`.
- `jwt_blacklist` — JWT revocados en logout, por `jti`.

## Endpoints

| Método | Ruta | Descripción | Acceso |
|--------|------|-------------|--------|
| `POST` | `/auth/login` | Autentica con email+password → `access_token` + `refresh_token` | público |
| `POST` | `/auth/refresh` | Rota el refresh token y emite un access token nuevo. Falla (`401`) si el usuario fue desactivado | público |
| `POST` | `/auth/logout` | Revoca refresh token y pone el access token en blacklist | autenticado |
| `GET` | `/auth/me` | Devuelve el usuario autenticado | autenticado |
| `POST` | `/auth/usuarios` | Alta de operador | `ADMIN` |
| `GET` | `/auth/usuarios` | Lista operadores | `ADMIN` |
| `PATCH` | `/auth/usuarios/{id}` | Cambia nombre/rol/activo. Al desactivar un usuario se **revocan todos sus refresh tokens** | `ADMIN` |
| `GET` | `/health` | Health check | público |

## Ejecución local

1. Crear y activar un entorno virtual:

```bash
python -m venv .venv
. .venv/bin/activate   # En Windows: .venv\Scripts\activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Configurar `.env`.

4. Iniciar el servidor:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8086
```

El puerto del ecosistema es el **8086** (el 8000 es de leads y el 8001 de ia-resumen). La documentación interactiva queda en `http://localhost:8086/docs`.

## Ejecución con Docker

```bash
cp .env.example .env
docker compose up --build
```

La API estará en `http://localhost:8086` (mapeado al puerto 8000 del contenedor).

## Pruebas

```bash
pytest
```

Cubre: login (ok / contraseña inválida / usuario inexistente), `/auth/me` con y sin token, refresh (rotación, reuso rechazado y usuario desactivado), logout (blacklist del access token), control de roles (`ADMIN` vs `ASESOR`), revocación de refresh tokens al desactivar un usuario, el claim `email` y la validación del `JWT_SECRET` al arrancar.

## Integración con el resto de microservicios

El JWT emitido incluye los claims `sub` (id de usuario), `email`, `rol` y `jti`.

Quien valida los tokens es el **orquestador** (el API Gateway del ecosistema): los verifica **localmente** con el mismo `JWT_SECRET`, sin llamar a este servicio en cada pedido, y reenvía la identidad a los demás servicios en el header `X-Usuario`. Los demás microservicios (clientes 8082, vehiculos 8083, calificacion 8084, leads 8000) no validan JWT. El logout pasa por el orquestador (`POST /api/auth/logout`), que además invalida ese access token en el acto.
