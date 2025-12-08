# JUSTICE
MD
```markdown
# JUSTICE — server/JUSTICE

Minimal Node/Express scaffold.

Run locally:
1. cd JUSTICE
2. npm install
3. npm start
```
# JUSTICE – серверная часть

## Что это?

Node.js + Express сервер, который реализует API для проекта Justice.  
Подключает аутентификацию (JWT), CRUD‑операции над пользователями и постами, а также отправку писем.

## Структура
server/ ├─ src/ │ ├─ config/ │ ├─ controllers/ │ ├─ middleware/ │ ├─ models/ │ ├─ routes/ │ ├─ services/ │ ├─ utils/ │ ├─ validators/ │ ├─ index.js │ └─ app.js ├─ test/ ├─ .env.example ├─ package.json └─ README.md

## Установка и запуск

```bash
git clone https://github.com/ivanm696/justice.git
cd justice/server
cp .env.example .env
# заполните .env
npm install
npm run dev    # для разработки
npm start      # для продакшна
