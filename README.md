# JUSTICE
MD
```markdown
# JUSTICE — server/justice

Minimal Node/Express scaffold.

Run locally:
1. cd justice
2. npm install
3. npm start
```
# justice – серверная часть

## Что это?

Node.js + Express сервер, который реализует API для проекта Justice.  
Подключает аутентификацию (JWT), CRUD‑операции над пользователями и постами, а также отправку писем.

## Структура
server/ ├─ src/ │ ├─ config/ │ ├─ controllers/ │ ├─ middleware/ │ ├─ models/ │ ├─ routes/ │ ├─ services/ │ ├─ utils/ │ ├─ validators/ │ ├─ index.js │ └─ app.js ├─ test/ ├─ .env.example ├─ package.json └─ README.md
