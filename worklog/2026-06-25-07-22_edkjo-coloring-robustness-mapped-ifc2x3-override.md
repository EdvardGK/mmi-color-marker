# Session: edkjo (Windows 11) — coloring robustness: mapped geometry, IFC2X3, color-everything, hard-override

| Field | Value |
|---|---|
| Machine | **edkjo** |
| Platform | **Windows 11** |
| Repo | [EdvardGK/mmi-color-marker](https://github.com/EdvardGK/mmi-color-marker) |
| Remote impact | 4 commits pushed to `main`: `87a16f6`, `b5db832`, `9eedc01`, `24c503b`. Authored `EdvardGK <ed.subscript@gmail.com>` (personal repo). |
| Deploy | `mmi-farger.streamlit.app` (Streamlit Community Cloud, IFC4 1.58.0). Each push auto-redeploys. |
| Driver | Continuation of the OOM-fix session. edkjo reported coloring gaps in escalating order: "doesn't color every type" → "NOTHING colored" → "color everything + detect schema" → "override everything no excuses". Plus a one-off lookup of the S8 rivemodell demolition red. |

## Summary

Four coloring fixes shipped, each uncovering the next. The throughline: the app's
coloring was only valid for **direct-geometry IFC4** models, and silently failed
on everything else. Now it colours every element on both schemas and can hard-
override any competing colour source.

1. `87a16f6` — colour elements whose geometry is reused via **IfcMappedItem**.
2. `b5db832` — render colours on **IFC2X3** models (wrap style in PresentationStyleAssignment).
3. `9eedc01` — **colour everything** via schema-aware geometry resolution (mapped + type fallback).
4. `24c503b` — **hard-override** competing material/layer colours so the chosen colour always wins.

Also: located the **S8 rivemodell** demolition red for reuse (no code change).

## The bug chain (why each fix exposed the next)

Repeated lesson: **I kept diagnosing from stand-in models and missing the real
failure mode.** The app worked on the IFC4 LBK test model, so each fix looked
verified — but edkjo's real exports are **IFC2X3** (Revit/Solibri), which the
stand-in never exercised. Burned a cycle each time. The fix that finally stuck
came from testing the **actual S8 ARK export** (`L05_S8A_ARK_eksisterende.ifc`,
IFC2X3, 169 MB) instead of LBK.

### `87a16f6` — IfcMappedItem
"Doesn't colour every type." Types whose geometry is reused from a type definition
(`IfcMappedItem` → `MappingSource.MappedRepresentation`) were getting the
`IfcStyledItem` attached to the **mapped item**, which viewers ignore. The real
geometry lives one level down. In the LBK model this silently dropped all 4,784
`IfcMechanicalFastener`; in other models it's doors/windows/furniture/MEP.
Fix: recurse into the mapped representation and style the real (shared) geometry.

### `b5db832` — IFC2X3 styling
"NOTHING colored." The S8 export is **IFC2X3**, where `IfcStyledItem.Styles` must
contain an `IfcPresentationStyleAssignment` — a bare `IfcSurfaceStyle` (IFC4
syntax) is schema-invalid and **every viewer silently drops it** → whole model
grey. ifcopenshell writes it anyway, so it round-trips but doesn't render. This is
the exact gotcha documented in edkjo's own S8 `remove_demolished.py`. The cloud
log confirmed nothing threw — it was a silent render failure, not a crash.
Fix: `get_style_ref()` returns the schema-correct value (bare on IFC4, wrapped on
IFC2X3), reusing one assignment per run.

### `9eedc01` — colour everything
edkjo: "we need to colour everything and also detect ifc schema and tailor to
that." Generalised geometry resolution into `resolve_geometry_items()` (mapped
recursion + **type RepresentationMaps fallback** for occurrences with no own
representation) and `get_element_type()` (IsTypedBy on IFC4, shared IsDefinedBy on
IFC2X3). `find_all_products` now also includes type-only-geometry occurrences.
Schema shown in the UI. Verified 0 unstyled products on both: IFC4 LBK (34,371)
and IFC2X3 S8 (3,480).

### `24c503b` — hard-override
edkjo raised IFC style **priority** (styled item > material > layer), then "override
everything no excuses." Scanned the real S8 model: **0** layer styles, **98**
material styles (`IfcMaterialDefinitionRepresentation`/`IfcStyledRepresentation`),
9,404 existing styled items, 0 duplicates — so on these models the competitor is
**material colour**, not layers. `override_competing_styles()` removes material +
layer colour sources outright, leaving our styled items as the only appearance.
Material **data** (IfcMaterial + associations) is kept — only colour stripped.
Default-on checkbox "Overstyr alle eksisterende farger".

## Changes — `app.py`

- `resolve_geometry_items(element)` / `get_element_type(element)` — schema-aware geometry walk (mapped recursion + type fallback).
- `find_all_products` — now includes occurrences whose geometry is only on the type.
- `apply_color_to_element(ifc, element, styles, styled_index)` — folded `_style_geometry_item` in; styles every resolved geometry item; takes a `styles` list (schema-correct).
- `get_style_ref(ifc, surface_style)` — bare IfcSurfaceStyle on IFC4, IfcPresentationStyleAssignment wrapper on IFC2X3 (one reused per run).
- `override_competing_styles(ifc)` — strips IfcPresentationLayerWithStyle + material def/styled representations; keeps IfcMaterial.
- UI: `st.caption("📐 Skjema: …")` + default-on "Overstyr alle eksisterende farger" checkbox.

## Process notes / gotchas

- **Stop testing against stand-ins.** The IFC4 LBK model passed every time while the real IFC2X3 export failed. Two wrong/incomplete diagnoses came from this. For this tool, always test on a real IFC2X3 export (S8 ARK) AND an IFC4 model.
- **IFC2X3 vs IFC4 styling** is the recurring trap (bit S8 and mmi-color-marker): `IfcStyledItem.Styles` = bare `IfcSurfaceStyle` on IFC4, `IfcPresentationStyleAssignment([IfcSurfaceStyle])` on IFC2X3. Bare on 2X3 = silent no-render.
- **IFC style precedence**: direct `IfcStyledItem` (on geometry) > material style > presentation-layer style. Most specific wins, but viewer-dependent — hence the hard-override.
- **Mapped geometry is shared** across instances; styling the map source once colours all instances (correct for colour-all; in property-filter mode it can tint siblings — accepted vs the previous total miss).
- **Verification perf**: per-element `any(... in by_type("IfcStyledItem"))` is O(N×M) and times out on big models — precompute a set of styled-item Item ids first.
- **Norwegian labels + cp1252**: set `PYTHONIOENCODING=utf-8` when printing `Blå`/`Grønn` from Bash python.

## S8 rivemodell demolition red (lookup, no code change)

Project: `c:\workspace\skiplum\client-projects\10033-sørkedalsveien-8\underprosjekter\S8_Fjerne-vegger-riveplan`.
- **Demolition ("Rives") red: `#d7191c`** = RGB (215, 25, 28) = (0.843, 0.098, 0.110). Authoritative in the 2D plan-render scripts (`render_final.py`, `build_ark_map.py`).
- Web viewer variant: `#d62728` (S8Compare.ts, classify_scope.py "demolished").
- **Nuance:** the IFC *deliverable* doesn't colour demo walls red — `remove_demolished.py` **removes** them and colours the **kept** walls **gold** `(0.85, 0.65, 0.2)` ≈ `#d9a633` (HI90 "existing" gold, lifted from mmi-color-marker). Red was 2D/viewer markup only.

## Untested / known-unknowns

- Still **not verified against edkjo's exact failing upload** — its schema/size unknown; all testing used the S8 ARK export (IFC2X3) and LBK (IFC4) as proxies. If a model still comes out grey, trace that specific file.
- **Override scope**: with override on, material/layer colours are stripped **file-wide**, not just for selected elements. Correct for colour-all; in property-filter mode it neutralises unselected elements' colours too (usually desired for a marking deliverable). Could be made surgical if edkjo wants.
- Property-filter mode + mapped/shared geometry can tint sibling instances of a type.
- `requirements.txt` still unpinned (cloud pulls latest streamlit/pandas/numpy).

## Pointers

- Commits: [87a16f6](https://github.com/EdvardGK/mmi-color-marker/commit/87a16f6), [b5db832](https://github.com/EdvardGK/mmi-color-marker/commit/b5db832), [9eedc01](https://github.com/EdvardGK/mmi-color-marker/commit/9eedc01), [24c503b](https://github.com/EdvardGK/mmi-color-marker/commit/24c503b)
- Diff base: `a266526..24c503b`
- Local clone: `C:\workspace\toolkit\mmi-color-marker\`
- Real IFC2X3 test model: `…\S8_Fjerne-vegger-riveplan\01_Inn\Export_2026-06-02_1828_IFC\L05_S8A_ARK_eksisterende.ifc`
- Prior session worklog: `worklog/2026-06-22-16-19_edkjo-oom-crash-fix-and-hosting-architecture.md`
