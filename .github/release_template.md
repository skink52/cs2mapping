# cs2mapping vYYYY.MM.DD

A known-good state of `main`. Between releases, `main` is the development state.

## What changed since the last release

<!-- The CHANGELOG.md entries for the period, grouped: porting pipeline, autoport, creation toolkit, docs, projects. -->

## Verified with

<!-- Copy the newest row of docs/reference/compatibility.md "Last verified environment", and add: -->
- CS2 build / Workshop Tools:
- Maps ported and built on the PC with this state:
- CI run:

Levels reached (see docs/reference/compatibility.md): unit tested and simulated in CI; compiled / in-game verified / playtested only
for the maps named above.

## Installing

1. Clone or download this tag.
2. `pip install -r requirements/porting.txt -c requirements/constraints.txt` (and `creation.txt` / `models.txt` if you use those parts).
3. Follow docs/porting/setup.md: where each file goes on the PC, the requirements table, the environment variables for a different layout.

## Upgrading from the previous release

<!-- Changed command lines, new required files, anything to copy to the PC again. "Nothing to do" if so. -->

## Known problems

<!-- Open items that affect users of this release. -->
