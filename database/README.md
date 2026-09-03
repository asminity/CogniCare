# Database

PostgreSQL is the prototype database. The backend reads its connection string from `backend/.env` using `DATABASE_URL`. Run `python -m app.db.init_db` from `backend` to create the schema and load demo data.

Expected local database:

```text
database: cognicare
user: cognicare
password: cognicare
host: localhost
port: 5432
```