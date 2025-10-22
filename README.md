# String Analyzer Service

Backend  Stage 1 — String Analysis API

A small FastAPI service that stores analyzed strings and exposes query endpoints. Each stored string is identified by its SHA-256 hash and keeps computed properties (length, palindrome flag, unique characters, word count, character frequency map, created timestamp).

## Key features
- Add a string and compute properties
- Retrieve strings by value or id (sha256)
- List strings with filterable query params
- Natural-language filter endpoint (basic parsing)
- SQLite by default, configurable via DATABASE_URL

## Quick start

Requirements:
- Python 3.9+
- pip

Install and run:
- pip install -r requirements.txt
- export DATABASE_URL="sqlite:///./strings.db"  # optional
- uvicorn main:app --reload

(The app creates tables automatically with SQLAlchemy Base.metadata.create_all)

## Environment
- DATABASE_URL (optional) — default: sqlite:///./strings.db

## Endpoints

- POST /strings
    - Create and store an analyzed string.
    - Request JSON: { "value": "your string here" }
    - Responses:
        - 201 Created: stored object with id (sha256), properties and created_at
        - 409 Conflict: string already exists
        - 422 Unprocessable Entity: invalid input

- GET /strings/{string_value}
    - Retrieve by exact string value, or by id (sha256).
    - 200 OK: string object
    - 404 Not Found: not present

- GET /strings
    - List stored strings with optional filters:
        - is_palindrome (bool)
        - min_length (int, >=0)
        - max_length (int, >=0)
        - word_count (int)
        - contains_character (single char)
    - Returns: { data: [...], count: n, filters_applied: {...} }

- GET /strings/filter-by-natural-language?query=...
    - Accepts a natural-language query and attempts to parse it into filters.
    - Examples it understands (basic):
        - "single word" or "one word" -> word_count = 1
        - "longer than 5" -> min_length = 6
        - "palindrome" -> is_palindrome = true
        - "containing the letter x" -> contains_character = "x"
        - "first vowel" -> contains_character = "a" (heuristic)
    - Errors:
        - 400 Bad Request: could not parse
        - 422 Unprocessable Entity: parsed but conflicting filters (e.g., min > max)

- DELETE /strings/{string_value}
    - Delete by value or id
    - 204 No Content on success
    - 404 Not Found if missing

## Data model (high-level)
Stored row fields:
- id: sha256(value) — primary key
- value: original string
- properties_json: JSON containing:
    - length (int)
    - is_palindrome (bool)
    - unique_characters (int)
    - word_count (int)
    - sha256_hash (string)
    - character_frequency_map (object)
- created_at: ISO8601 UTC timestamp

## Examples (curl)

Create:
curl -X POST -H "Content-Type: application/json" -d '{"value":"racecar"}' http://localhost:8000/strings

Get:
curl http://localhost:8000/strings/racecar
curl http://localhost:8000/strings/<sha256-id>

List with filters:
curl "http://localhost:8000/strings?is_palindrome=true&min_length=3"

NL filter:
curl "http://localhost:8000/strings/filter-by-natural-language?query=single%20word%20palindrome"

Delete:
curl -X DELETE http://localhost:8000/strings/racecar

## Notes & limitations
- The natural-language parser is intentionally simple and pattern-based; complex NL queries may not be parsed and will return errors.
- Character frequency counts are case-sensitive.
- Palindrome check is case-insensitive but does not strip punctuation or whitespace.
- SQLite is used by default; if using a server DB, set DATABASE_URL and ensure SQLAlchemy connect args are adjusted.

