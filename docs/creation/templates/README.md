# Project-doc templates

Copy these into a new addon project and fill in the `<…>` parts. Which ones ship with the addon and why: [../guide.md](../guide.md#8-project-docs).
They follow the conventions of Hellmatch, Space Racer, mg_trenchwarfare and Puppet Brawl.

| Template | Becomes | Ships in the addon |
|---|---|---|
| [README_ADDON.md](README_ADDON.md) | `README_<GAME>.md` | yes (content and game folder) |
| [TESTING.md](TESTING.md) | `TESTING_<GAME>.md` | yes |
| [CREDITS.md](CREDITS.md) | `CREDITS.md` (addon root) | yes |
| [HANDOVER.md](HANDOVER.md) | `HANDOVER.md` + `NOTES_<topic>.md` | no (repo) |
| [SERVER_ISSUES.md](SERVER_ISSUES.md) | `docs/SERVER_ISSUES.md` | no |
| [WORKSHOP_CHANGELOG.md](WORKSHOP_CHANGELOG.md) | `docs/WORKSHOP_CHANGELOG.md` | no |
| [WORKSHOP_COMPLIANCE.md](WORKSHOP_COMPLIANCE.md) | `docs/WORKSHOP_COMPLIANCE.md` | no |

Rules for all of them: the handle skink52 only (no real names, emails or `C:\Users\…` paths); say "AI-written code directed by skink52"; keep "written",
"verified offline" and "tested in game" apart, and mark anything not seen in CS2 as **NOT YET TESTED IN CS2**.
