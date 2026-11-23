# SmartProps (.vsmart)

SmartProps are Hammer's procedural props: one entity that lays a fence, pipe run, railing, wire set or scatter of debris along a line,
grid or area, with parameters the mapper drags in the viewport. They suit dense, detailed set dressing without hand-placing hundreds of props. Nothing in our projects uses them yet; this page is the starting point.

Sources: the SmartProp guides and linter in [dertwist/Hammer5Tools](https://github.com/dertwist/Hammer5Tools) (MIT), read 23 Nov 2026
and summarised in our own words. Its SmartProp Editor (a GUI) and preset kits (pipe, railing, scaffolding, wire set, fence, ladder, HVAC)
are worth opening when building a kit; they are not copied here. How far this page is checked: the linter is unit tested; no SmartProp
of ours has been compiled or placed in Hammer yet.

## Tool

`python create/vsmart.py tree <file>` prints the element tree; `python create/vsmart.py lint <file or folder> [--content <addon content>]`
reports the mistakes that make a SmartProp place nothing without an error (list in the file's header). Compile with
`python tools/rcompile.py asset <file.vsmart>` after the models it uses are compiled.

## The format in one screen

- KeyValues3 text. Root: `CSmartPropElement_Group` (or `CSmartPropRoot`) with `m_Variables`, `m_Choices`, `m_Children`, `m_Modifiers`.
- **Elements** place things: `Model` (the leaf), `Group`, `PlaceOnPath` (spaced along a spline, oriented), `FitOnLine` (tile or stretch
  between two points: fences, pipes, railings), `Layout2DGrid` (rows and columns, `CENTER` / `CORNER` origin, row shift), `PlaceInSphere`
  (scatter), `PickOne` (choose a child), `PlaceMultiple` (repeat, count from an expression).
- **Modifiers** (`CSmartPropOperation_*`) change what an element places: `SaveState` / `RestoreState`, `TraceInDirection` (snap to a
  surface, align to its normal), `SetOrientation`, seeded `RandomOffset` / `RandomRotation` / `RandomScale`, `MaterialOverride`,
  `SetTintColor`, `CreateSizer` (the viewport handle).
- **Selection criteria** decide whether a branch runs: `EndCap` (`m_bStart` / `m_bEnd`), `PathPosition` (all, every Nth, start, end),
  `LinearLength`, `ChoiceWeight`, `SurfaceAngle`, `SurfaceProperties`, `Expression`.
- Variable names are case-insensitive in expressions. Intrinsics: `InstanceIndex`, `InstanceCount`, `LinearScale()`, `RandomFloat`,
  `RandomInt`, the usual maths.

## Rules that save a compile

- **Guard every divisor** (`round(Length / max(1.0, Spacing))`). A divisor at 0 gives NaN, and one NaN in a transform hides the instance
  with no message. Same for `atan` / `asin` / `acos` of a quotient.
- **Numeric variables need a typed default.** An empty default reads as 0, and a count of 0 places nothing.
- **Linear kit shape:** `FitOnLine` with `m_ScaleMode = SCALE_END_TO_FIT` (Hammer: "Scale last"), the panel model scaled
  `LinearScale()` on X only, and the end post selected by `EndCap m_bEnd = true` at scale 1. `LinearScale()` on the end post distorts it.
- **Element IDs seed the random modifiers.** Renumbering an element moves what it scatters; fix only true duplicates.
- A SmartProp that places nothing is broken, not empty: lint it, then check every model path it names is compiled.
