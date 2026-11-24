# CLAUDE.md

Instructies voor Claude Code in deze repository.

## Werkafspraken

Vraag altijd eerst toestemming voordat je:

- bestanden verwijdert;
- bestanden aanmaakt of aanpast;
- commit;
- pusht.

Toestemming geldt alleen voor de actie waarvoor ze gegeven is, niet voor volgende acties.
Lezen, zoeken en checks draaien (flake8, pylint, pytest) mag zonder te vragen.
Deze regels worden ook afgedwongen in `.claude/settings.json`.

## Ontwikkelregels

- **Geheimen:** lees `.env` niet en zet `GITHUB_TOKEN` (of een andere token) nooit in code,
  tests, logs of output.
- **Checks niet afzwakken:** zet geen lint-regels uit, sla geen tests over, pas tests niet aan
  zodat ze bij foute code passen en versoepel de coverage-instellingen niet zonder overleg.
- **Klaar = groen:** draai flake8, pylint en pytest voordat je een stap als klaar meldt.
- **Dependencies:** voeg geen nieuwe dependencies toe zonder overleg.
- **Eén stap tegelijk:** werk alleen aan de huidige roadmap-stap uit `README.md`; niet vooruitwerken.
- **Git-geschiedenis:** geen force-push en geen `git reset --hard`; herschrijf geen gepushte commits.
- **Omgeving:** installeer alleen in `.venv`, nooit in de systeem-Python, en pas niets buiten
  de repository aan.

## Project

`gh-commits`: een CLI die via de GitHub REST API de commits van een publieke repository
ophaalt binnen een tijdsbestek en ze groepeert per auteur. Zie `README.md` voor de
functionaliteit, de architectuur en de roadmap.

- Python 3.12+; de code staat in `src/gh_commits/` (src-layout), de tests in `tests/`.
- Alle configuratie (dependencies, pytest, coverage, flake8, pylint) staat in `pyproject.toml`.
- Code is in het Engels: namen, docstrings, comments en testdata.
- Documentatie (README) en commitberichten zijn voorlopig in het Nederlands.

## Commando's

Gebruik de virtualenv in `.venv`:

```bash
.venv/bin/pip install -e ".[dev]"            # installeren
.venv/bin/flake8 src tests                   # linting
.venv/bin/pylint src                         # linting
.venv/bin/pytest --cov --cov-report=term-missing   # tests met coverage
```

CI (`.github/workflows/ci.yml`) draait dezelfde checks op Python 3.12, 3.13 en 3.14.
