# Hotel Casa Jacaranda: mock PMS API

A small mock Property Management System (PMS) for a fictional hotel in Mexico. It exposes a few
tool endpoints that a voice agent can call to look up reservations, check availability, request
late checkout and hand off to staff.

**All data is fictional.** Hotel Casa Jacaranda, its guests, phone numbers and reservations are
invented. This project does not imitate any real PMS product or company.

Design notes:

- Business outcomes always return HTTP 200 with a status field (`found`, `available`, `approved`,
  `status`) and a short `message` written to be read aloud.
- 401 means a missing or wrong `X-Tool-Secret`, 422 means an invalid request, and 503 means a
  simulated outage.
- Phone numbers in 10-digit, `+52` and legacy `+521` formats all match the same stored E.164
  number. Logs mask phone numbers to their last 4 digits and never include the secret.
- Seed dates are relative to today in `America/Mexico_City`, so the demo never goes stale.
- Messages are in English. The voice agent uses the data and answers the guest in Spanish.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | none | Liveness check, also shows the current failure mode |
| POST | `/tools/find-reservation` | `X-Tool-Secret` | Find by phone, or by confirmation code plus last name |
| POST | `/tools/check-availability` | `X-Tool-Secret` | Room types, nightly price and stay total in MXN |
| POST | `/tools/request-late-checkout` | `X-Tool-Secret` | Late checkout until 14:00, if the rules allow it |
| POST | `/tools/create-ticket` | `X-Tool-Secret` | Hand off to hotel staff |

## Setup (macOS)

Requires Python 3.9 or newer. The repo uses one virtual environment at the root, as described in
the [main README](../README.md). Short version, from the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r pms/requirements.txt
cd pms
cp .env.example .env.local   # then set TOOL_SECRET to a long random string
```

Run all the commands below from the `pms/` folder, with the virtual environment active.

Settings in `.env.local`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `TOOL_SECRET` | (required) | Value the client must send in `X-Tool-Secret` |
| `DB_PATH` | `pms.sqlite3` | SQLite file, relative to `pms/` |
| `PMS_FAILURE_MODE` | `none` | `none`, `timeout` (wait past the timeout, then 503) or `error` (503 right away) |
| `PMS_TIMEOUT_SECONDS` | `5` | In `timeout` mode the server waits this long plus 1 second |

## Seed, run, test

```bash
python -m scripts.seed                              # resets and reloads demo data
uvicorn app.main:create_app --factory --reload      # http://127.0.0.1:8000/docs
pytest -q                                           # uses a temporary database
```

Re-run the seed script each day you demo so "arriving today" stays true. Restart the server
after changing `PMS_FAILURE_MODE`.

## Demo data

| Code | Guest | Case |
| --- | --- | --- |
| CJ1001 | Lucía Hernández, 55 5010 0001 | Arriving today |
| CJ1002 | Mateo Ramírez, 55 5010 0002 | Staying now, checks out in 2 days |
| CJ1003 | Sofía Castillo, 55 5010 0003 | Checks out tomorrow; late checkout can be approved |
| CJ1004 | Diego Morales, 55 5010 0004 | Checks out tomorrow; next guest arrives in the same room |
| CJ1005 | Valentina Ortiz, 55 5010 0005 | Future reservation, arrives tomorrow |
| CJ1006 | Andrés Navarro, 55 5010 0006 | Cancelled |
| CJ1007, CJ1009 | Carmen Flores, 55 5010 0007 | Guest with two reservations |
| CJ1008 | Javier Mendoza, 55 5010 0008 | With CJ1007, sells out the Jacaranda Suite 5 to 8 days from today |

## curl examples

```bash
export PMS=http://127.0.0.1:8000
export SECRET=$(grep '^TOOL_SECRET=' .env.local | cut -d= -f2-)
```

Health:

```bash
curl -s $PMS/health
```

Find a reservation by phone (also try `5550100001` or `+5215550100001`):

```bash
curl -s -X POST $PMS/tools/find-reservation \
  -H "X-Tool-Secret: $SECRET" -H "Content-Type: application/json" \
  -d '{"phone": "+52 55 5010 0001"}'
```

Find a reservation by confirmation code and last name:

```bash
curl -s -X POST $PMS/tools/find-reservation \
  -H "X-Tool-Secret: $SECRET" -H "Content-Type: application/json" \
  -d '{"confirmation_code": "CJ1003", "last_name": "Castillo"}'
```

Check availability (dates must be today or later):

```bash
curl -s -X POST $PMS/tools/check-availability \
  -H "X-Tool-Secret: $SECRET" -H "Content-Type: application/json" \
  -d "{\"check_in\": \"$(date -v+10d +%F)\", \"check_out\": \"$(date -v+12d +%F)\", \"guests\": 2}"
```

Request late checkout (use a `reservation_id` from find-reservation):

```bash
curl -s -X POST $PMS/tools/request-late-checkout \
  -H "X-Tool-Secret: $SECRET" -H "Content-Type: application/json" \
  -d '{"reservation_id": 3, "requested_time": "13:30"}'
```

Create a ticket:

```bash
curl -s -X POST $PMS/tools/create-ticket \
  -H "X-Tool-Secret: $SECRET" -H "Content-Type: application/json" \
  -d '{"reservation_id": 3, "category": "housekeeping", "priority": "normal",
       "summary": "Guest asked for extra pillows.", "guest_phone": "5550100003"}'
```

## Project layout

```
app/config.py     settings from .env.local, hotel timezone
app/phone.py      Mexican phone normalization
app/schemas.py    Pydantic request and response models
app/db.py         SQLite schema and queries
app/services.py   business rules
app/routes.py     endpoints, auth, failure simulation
app/main.py       app factory, JSON logging, validation error format
scripts/seed.py   demo data
tests/            pytest suite
```
