# Github Commits

[![CI](https://github.com/Rinzetk/alteza-opdracht/actions/workflows/ci.yml/badge.svg)](https://github.com/Rinzetk/alteza-opdracht/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

Een command-line client die via de GitHub REST API de commits van een publieke repository ophaalt binnen een tijdsbestek, en ze groepeert per auteur.

```console
$ gh-commits django/django --since 2026-09-01 --until 2026-10-31 --branch main
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

De cache wordt bewaard in een Docker-volume, zodat hij tussen runs behouden blijft.

## Gebruik

```text
gh-commits REPOSITORY --since DATUM --until DATUM [opties]
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
gh-commits django/django --since 2026-09-01 --until 2026-10-31 --branch main

# Output als JSON, bijvoorbeeld om verder te verwerken met jq
gh-commits django/django --since 2026-09-01 --until 2026-10-31 --format json | jq '.[0]'
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
| `GH_COMMITS_CACHE_PATH` | `~/.cache/gh-commits` | Locatie van de cache-database |
| `GH_COMMITS_CACHE_TTL` | `3600` | Hoe lang een response geldig blijft (seconden) |

Voor Docker kun je deze waarden in een `.env`-bestand zetten (zie `.env.example`).

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
pytest                      # unit- en integratietests (met gemockte HTTP)
pytest -m integration       # live tests tegen de GitHub API (vereist GITHUB_TOKEN)
pytest --cov=gh_commits     # met coverage
```

In de unittests worden HTTP-calls gemockt met `responses`. De integratietests draaien de volledige CLI end-to-end. Live tests zijn gemarkeerd met `@pytest.mark.integration` en worden overgeslagen als er geen token is.

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
2. Tests met coverage
3. Bouwen van het Docker-image

## Roadmap

- [ ] Projectskelet, tooling en `pyproject.toml`
- [ ] CI-pipeline (linting + tests)
- [ ] Domeinmodellen en groepeerlogica
- [ ] Basis-API-client
- [ ] Paginatie, datumbereik en branch
- [ ] Foutafhandeling
- [ ] Rate limiting en retries
- [ ] Caching
- [ ] CLI
- [ ] Integratietests
- [ ] Docker
- [ ] Documentatie en afronding