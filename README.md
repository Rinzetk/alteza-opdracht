# Github Commits

[![CI](https://github.com/Rinzetk/alteza-opdracht/actions/workflows/ci.yml/badge.svg)](https://github.com/Rinzetk/alteza-opdracht/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

Een command-line client die via de GitHub REST API de commits van een publieke repository ophaalt binnen een tijdsbestek, en ze groepeert per auteur.

```console
$ github-commits django/django --since 2026-09-01 --until 2026-10-31 --branch main
```

## Inhoud
 
- [Requirements](#requirements)
- [Functionaliteit](#functionaliteit)
- [Installatie](#installatie)
- [Gebruik](#gebruik)
- [Configuratie](#configuratie)
- [Architectuur](#architectuur)
- [Ontwerpkeuzes](#ontwerpkeuzes)
- [Ontwikkeling](#ontwikkeling)
- [Roadmap](#roadmap)

## Requirements
 
Dit project is een technische opdracht. De opdrachtgever vraagt het volgende:
 
### Functioneel
 
| # | Requirement | Details |
| --- | --- | --- |
| 1 | **Input** | Een repositorynaam (bijv. `python/cpython`, `django/django`) en een start- en einddatum |
| 2 | **Commits ophalen** | Alle commits binnen het opgegeven tijdsbestek ophalen, voor een specifieke branch |
| 3 | **Groeperen per auteur** | Per auteur het aantal commits en de commit-berichten tonen |
| 4 | **Caching** | API-responses lokaal opslaan met een standaard caching-oplossing, zodat ze hergebruikt worden |
| 5 | **Foutafhandeling** | Rate limiting (wachten en opnieuw proberen), verlopen of ontbrekende tokens, ongeldige repositorynamen en netwerkproblemen |
| 6 | **CLI** | Een eenvoudige command-line interface om de client te bedienen |
 
### Technisch
 
| # | Requirement | Details |
| --- | --- | --- |
| 7 | **Framework** | Laatste versie van Django of Flask, of pure Python (aanbevolen met `requests` of `httpx`) |
| 8 | **Tests** | Unit- en integratietests met een testframework naar keuze (bijv. `unittest` of `pytest`) |
| 9 | **CI/CD** | Een pipeline (GitHub Actions, GitLab CI of CircleCI) die bij elke push de tests draait en de codekwaliteit controleert (bijv. flake8 of pylint) |
| 10 | **Docker** | Een Docker-omgeving om de client lokaal uit te voeren en te testen |
| 11 | **Documentatie** | Duidelijke documentatie over het gebruik en de implementatiekeuzes, waarbij de code leidend is |
 
De nadruk ligt op de kwaliteit van de code en de architectuur.
 
## Functionaliteit
 
- Haalt alle commits op voor een repository, branch en datumbereik (met paginatie)
- Groepeert commits per auteur, met per auteur het aantal commits en de commit-berichten
- Slaat API-responses lokaal op in een cache (`requests-cache`, SQLite)
- Wacht automatisch bij rate limiting en probeert het daarna opnieuw
- Geeft duidelijke foutmeldingen bij een ongeldige of ontbrekende token, een onbekende repository of branch, en netwerkproblemen
- Output als leesbare tekst of als JSON


## Installatie

### Lokaal

Vereist Python 3.12 of hoger.

```bash
git clone https://github.com/Rinzetk/alteza-opdracht.git
cd alteza-opdracht
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Docker

```bash
docker compose build
docker compose run --rm app django/django --since 2025-01-01 --until 2025-01-31
```

- **Token:** zet `GITHUB_TOKEN` in een `.env`-bestand naast `docker-compose.yml`. Compose geeft het mee bij het starten van de container; het komt nooit in het image (`.dockerignore` sluit `.env` uit). Zonder `.env` werkt het ook, met de lagere limiet.
- **Cache:** de cache staat in het Docker-volume `cache`, zodat hij tussen runs behouden blijft. Legen kan met `--clear-cache` of met `docker compose down -v`.
- **Image:** gebaseerd op `python:3.12-slim` en draait als non-root user `app`. De dependencies worden vóór de broncode geïnstalleerd, zodat die laag uit de cache komt zolang `requirements*.txt` niet verandert.

## Gebruik

```text
github-commits REPOSITORY --since DATUM --until DATUM [opties]
```

| Argument | Verplicht | Beschrijving |
| --- | --- | --- |
| `REPOSITORY` | ja | Repository in de vorm `owner/repo`, bijv. `python/cpython` |
| `--since` | ja | Startdatum (`YYYY-MM-DD`), inclusief |
| `--until` | ja | Einddatum (`YYYY-MM-DD`), inclusief |
| `--branch` | nee | Branch om te doorzoeken; standaard de default branch van de repository |
| `--format` | nee | `text` (standaard) of `json` |
| `--no-cache` | nee | Cache overslaan voor deze aanroep |
| `--clear-cache` | nee | Cache legen voordat de aanroep start |

Voorbeelden:

```bash
# Commits op de main-branch van CPython in januari 2025
github-commits django/django --since 2026-09-01 --until 2026-10-31 --branch main

# Output als JSON, bijvoorbeeld om verder te verwerken met jq
github-commits django/django --since 2026-09-01 --until 2026-10-31 --format json | jq '.[0]'
```

### Exit codes

| Code | Betekenis |
| --- | --- |
| `0` | Gelukt |
| `1` | Fout bij de GitHub API (authenticatie, niet gevonden, rate limit, netwerk) |
| `2` | Ongeldige invoer (bijv. verkeerd datumformaat of `--until` vóór `--since`) |

## Configuratie

| Omgevingsvariabele | Standaard | Beschrijving |
| --- | --- | --- |
| `GITHUB_TOKEN` | — | Personal access token. Optioneel, maar verhoogt de limiet van 60 naar 5000 requests per uur. |
| `GH_COMMITS_CACHE_PATH` | `~/.cache/github-commits` | Locatie van de cache-database |
| `GH_COMMITS_CACHE_TTL` | `3600` | Hoe lang een response geldig blijft (seconden) |

Alle variabelen zijn optioneel. Zonder token werkt de client ook, met de lagere limiet.

### Waar de variabelen vandaan komen

| Manier van draaien | Bron | Wordt `.env` gelezen? |
| --- | --- | --- |
| Docker Compose (`app` en `test`) | Het `.env`-bestand naast `docker-compose.yml` | Ja, als het bestaat |
| Lokaal (`github-commits`, `pytest`) | De omgeving van je shell | Nee |
| CI (GitHub Actions) | Het automatische `secrets.GITHUB_TOKEN` | Nee |

De client leest alleen omgevingsvariabelen en laadt zelf geen `.env`-bestand. Buiten Docker zet je ze dus in je shell.

### Met Docker: een `.env`-bestand

```bash
cp .env.example .env
```

Vul daarna `GITHUB_TOKEN=` in. Docker Compose geeft de waarden mee bij het starten van de container:

- `.env` staat in `.gitignore` en `.dockerignore`: het komt nooit in git of in het image.
- `GH_COMMITS_CACHE_PATH` laat je in Docker leeg; de cache staat daar in het volume `cache`.
- Met een token in `.env` draaien ook de live tests mee in `docker compose run --rm test`.

### Lokaal: in je shell

```bash
# bash / zsh
export GITHUB_TOKEN=ghp_...
github-commits python/cpython --since 2026-01-01 --until 2026-01-31

# fish
set -x GITHUB_TOKEN ghp_...

# alleen voor één commando
env GITHUB_TOKEN=ghp_... github-commits python/cpython --since 2026-01-01 --until 2026-01-31
```

### Een token aanmaken

Maak op GitHub een *fine-grained personal access token* aan (Settings → Developer settings → Personal access tokens). Voor publieke repositories zijn geen extra rechten nodig. De token wordt alleen in de `Authorization`-header naar GitHub gestuurd; hij komt niet in de cache, de output of de logs.

## Architectuur

De client bestaat uit drie gescheiden lagen: netwerk, domeinlogica en presentatie. Elke laag is los te testen.

```text
src/gh_commits/
├── cli.py        # Presentatie: argumenten parsen, invoer valideren, output, exit codes
├── client.py     # Netwerk: GitHubClient met authenticatie, paginatie en retries
├── cache.py      # Opbouw van de gecachte HTTP-sessie
├── grouping.py   # Domeinlogica: commits groeperen per auteur (geen I/O)
├── models.py     # Dataclasses: Commit, AuthorSummary
└── errors.py     # Exception-hiërarchie
```

```text
cli ──> client ──> GitHub API
 │         └─ gebruikt een (gecachte) requests.Session
 └──> grouping ──> models
```

## Ontwerpkeuzes

**Geen framework.** De opdracht vraagt om een CLI-client. Django en Flask zijn webframeworks en zouden een ORM, settings en routing toevoegen die hier niet nodig zijn. Pure Python met `requests` en `argparse` houdt de code klein en goed leesbaar.

**De HTTP-sessie als dependency.** `GitHubClient` maakt zijn sessie niet zelf aan, maar krijgt hem mee. Daardoor zijn caching en tests in te pluggen zonder de client aan te passen.

**Caching met `requests-cache`.** Dit is een standaardoplossing die transparant onder `requests` werkt. Het gebruikt conditional requests (ETag): een `304 Not Modified`-antwoord telt bij GitHub niet mee voor de rate limit.

**Groeperen per auteur.** Het `author`-veld van GitHub (de login) is `null` als het e-mailadres van een commit niet aan een account gekoppeld is. De client groepeert daarom op login als die bekend is, en anders op de naam en het e-mailadres uit de commit zelf.

**Datumbereik.** Beide datums zijn inclusief en worden in UTC geïnterpreteerd. `--until 2026-10-31` betekent dus tot en met 31 januari 23:59:59 UTC.

**Foutafhandeling en retries.**

| Situatie | Gedrag |
| --- | --- |
| Primaire rate limit (`X-RateLimit-Remaining: 0`) | Wachten tot `X-RateLimit-Reset`, daarna opnieuw proberen; stoppen met een `RateLimitError` als de wachttijd te lang is |
| Secundaire rate limit | `Retry-After` respecteren |
| `5xx` of verbindingsfout | Opnieuw proberen met exponentiële backoff (`urllib3.Retry`) |
| `401` | `AuthenticationError`: token ongeldig of verlopen |
| `404` | `RepositoryNotFoundError` of `BranchNotFoundError` |
| `409` | Lege repository: geen commits |

## Ontwikkeling

### Opzetten

```bash
pip install -e ".[dev]"
```

### Tests

```bash
pytest                      # alle tests; de live tests alleen als GITHUB_TOKEN gezet is
pytest -m integration       # alleen de live tests tegen de GitHub API (vereist GITHUB_TOKEN)
pytest -m "not integration" # alles behalve de live tests
pytest --cov                # met coverage
```

Er zijn drie soorten tests:

| Soort | Bestanden | Wat ze testen |
| --- | --- | --- |
| Unittests | `test_grouping.py`, `test_client.py`, `test_cache.py`, `test_cli.py` | Elke laag apart; HTTP-calls worden gemockt met `responses` |
| End-to-end | `test_end_to_end.py` | `main([...])` door alle lagen heen (CLI, cache, client, paginatie, groeperen, output), met alleen de GitHub API gemockt: stdout, stderr en exit codes |
| Live | `test_live.py` | De CLI tegen de echte API, op de vaste geschiedenis van `octocat/Hello-World`; gemarkeerd met `@pytest.mark.integration` en overgeslagen zonder `GITHUB_TOKEN` |

Met Docker:

```bash
docker compose run --rm test
```

### Codekwaliteit

```bash
flake8 src tests
pylint src
```

### CI

GitHub Actions (`.github/workflows/ci.yml`) draait bij elke push en pull request:

1. Linting met flake8 en pylint
2. Tests met coverage, inclusief de live tests (met het automatische `secrets.GITHUB_TOKEN`); het coverage-rapport staat in de samenvatting van elke run
3. Bouwen van de Docker-images, controleren dat de CLI als non-root user start, en de tests in de container draaien

## Roadmap

- [x] Projectskelet, tooling en `pyproject.toml`
- [x] CI-pipeline (linting + tests)
- [x] Domeinmodellen en groepeerlogica
- [x] Basis-API-client
- [x] Paginatie, datumbereik en branch
- [x] Foutafhandeling
- [x] Rate limiting en retries
- [x] Caching
- [x] CLI
- [x] Integratietests
- [x] Docker
- [ ] Documentatie en afronding