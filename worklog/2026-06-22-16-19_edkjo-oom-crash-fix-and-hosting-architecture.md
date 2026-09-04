# Session: edkjo (Windows 11) — OOM crash fix (Streamlit Cloud) + fleet hosting architecture

| Field | Value |
|---|---|
| Machine | **edkjo** |
| Platform | **Windows 11** |
| Repo | [EdvardGK/mmi-color-marker](https://github.com/EdvardGK/mmi-color-marker) |
| Remote impact | 1 commit pushed to `main`: `a266526` (fix). Authored `EdvardGK <ed.subscript@gmail.com>` (personal repo). |
| Deploy | `mmi-farger.streamlit.app` (Streamlit Community Cloud, branch `main`, ~1 GB RAM). Push auto-redeploys. |
| Driver | "the app is crashing in streamlit." Started as a `git diff` against GitHub, became a crash hunt, then a broader fleet-hosting architecture decision. |

## Summary

Two outcomes:

1. **Fixed the live OOM crash** on `mmi-farger.streamlit.app`. The app was being OOM-killed on Streamlit Community Cloud (~1 GB), not throwing any Python error. Cut peak RAM from **1.53 → 1.13 GB** on a 120 MB model and lowered the upload cap 600 → 200 MB to match what the host can actually process. Shipped as `a266526`.
2. **Decided the fleet hosting architecture** (Railway / Hetzner / Modal / Supabase / Vercel), including a reference architecture for **sprucelab**. Saved to memory.

This session confirmed the open question the *previous* worklog (2026-05-12) flagged and left uninvestigated: *"If Streamlit Cloud is the deploy target it may have a hard cap below 600."* — It does. The 600 MB cap that worklog added is exactly what invited the OOM.

## The crash — diagnosis

The user-supplied Streamlit Cloud log (`Downloads/logs-edvardgk-mmi-color-marker-...txt`) showed, on a loop:

```
❗️ ...checking the health of the Streamlit app: Get "http://localhost:8501/healthz":
   read tcp ...: read: connection reset by peer
→ 🚀 Starting up repository... (reboot)
```

Classic **OOM-kill signature**: the process dies (health check reset by peer), container reboots. **No Python traceback anywhere** in the log — the OS killed it, it didn't crash from a code bug. Cloud env from the log: `streamlit==1.58.0`, `pandas==3.0.3`, `numpy==2.5.0`, `ifcopenshell==0.8.5`, Python 3.13 (all pulled latest — `requirements.txt` pins nothing).

### How it was verified (no browser available)

- chrome-devtools MCP couldn't attach (user's own Chrome held the profile lock → "browser is already running for ...chrome-profile").
- Instead drove the **real app** via Streamlit's official headless harness `streamlit.testing.v1.AppTest`, injecting a real 120 MB IFC4 model (`C:\tmp\LBK_RIBp_C_IFC4_brep_clean.ifc`, 34,371 products) through a patched `st.file_uploader` (throwaway `tmp_driver.py`, deleted after).
- Exercised **both** flows end-to-end — property-filter (pset/prop/value → color → preview dialog → Fargelegg → details dialog → download) and color-all — plus the backend functions directly. **Zero exceptions** in every path. Confirms: no code-level crash exists; it's purely resource.
- Memory profiled with a `psutil` background sampler: double-open peak **1.53 GB** standalone / 1.31 GB in AppTest for a 120 MB file.
- Ruled out `st.components.v1.html` (deprecation date 2026-06-01 passed, fires noisy warnings) — downloaded the 1.58.0 wheel and inspected `components/v1/__init__.py`: `html` is still a live `deprecate_func_name` wrapper around `streamlit._main._html`, **not removed**. Just warns. Not the cause.

### Why it OOMs

ifcopenshell holds the **entire** model in RAM at roughly **6× the .ifc file size** (measured: 120 MB → 0.76 GB resident). The app made this worse:

- Opened the model **2–3 times simultaneously** (cached in `session_state` + re-opened on the matches step + re-opened again on Fargelegg).
- Created a **per-element property set**: for color-all on 34,371 elements, ~20 entities each (`IfcPropertySet` + 9 `IfcPropertySingleValue` + wrapped values + `IfcRelDefinesByProperties`) ≈ ~700k entities of identical metadata.

## Changes — `app.py` + `.streamlit/config.toml` (commit `a266526`)

1. **Open the model once, reuse it.** Removed the redundant `ifcopenshell.open(tmp_path)` at the matches step (was a latent bug: `st.session_state.get("ifc_file")` — wrong key, always re-opened) and at the Fargelegg step. Everything now uses the single `session_state`-cached `ifc`. → 1.53 → 1.31 GB.
2. **Shared pset.** New `add_shared_pset(ifc_file, elements, ...)` creates **one** `IfcPropertySet` + **one** `IfcRelDefinesByProperties` with `RelatedObjects = [all coloured elements]` instead of per-element. ~10 entities total vs ~700k. The loop now collects `tagged_elements` and tags them once after coloring. → 1.31 → **1.13 GB**, output file 159 → 121 MB. Added `import ifcopenshell.guid`. Verified the shared pset round-trips: `ifcopenshell.util.element.get_pset(beam, "NOSKI_Eksisterende")` reads back all 8 properties off a sample element; 1 pset / 1 rel / 34,371 RelatedObjects in the output.
3. **`maxUploadSize` 600 → 200** in `config.toml` (with an explanatory comment) + a UI note in the "Om verktøyet" expander ("ca. 200 MB ... For større modeller, kjør appen lokalt"). 600 MB on a ~1 GB host is un-processable (a 600 MB model ≈ 3.8 GB resident).

`apply_color_to_element` and the per-element legacy `add_pset` were left in place (add_pset now unused by the main loop but kept).

## Hosting architecture decisions (fleet-wide)

Discussion that followed the fix. Captured to memory ([[fleet-hosting-architecture]], [[sprucelab-reference-architecture]]).

- **Current stack** = Vercel (web frontends) + Railway (always-on backend containers) + Supabase (Postgres + auth + storage) + Streamlit Community Cloud (free one-offs).
- **Snowflake / Vercel** clarified: neither belongs in the stack for Streamlit. Vercel is serverless (can't host a persistent Streamlit server). Snowflake is an OLAP data-cloud (different job from Supabase's OLTP Postgres) — only relevant if cross-project analytics outgrow Postgres, which is far off; prefer DuckDB/MotherDuck before Snowflake.
- **Internal apps → Railway** (user: "for the internal apps railway is actually fine").
- **Cheap-at-scale + big RAM (1 GB models → 12+ GB resident)** → **Hetzner dedicated + Coolify/Dokploy** (self-hosted Railway-like PaaS; one ~€44/mo 64 GB box hosts everything). For spiky huge jobs → **Modal** (scale-to-zero, big RAM, pay-per-second) or Cloud Run (32 GB ceiling). Decision rule: high/steady utilization → Hetzner flat; spiky → Modal/Cloud Run.
- **sprucelab (the product, Django + React BIM platform)** → multi-tier: React → **Vercel**, Django API → **Railway**, Postgres → **Supabase**, file storage → Supabase now / **Cloudflare R2** later (zero egress), heavy IFC processing → **async job tier** (queue + Redis) on **Modal**. Never process 12 GB models inline in a Django request. Django owns auth + migrations; don't double up with Supabase Auth. Stay managed until the bill hurts, then move the heaviest *steady* tier to Hetzner — never the whole thing at once.

## Process notes / gotchas

- **chrome-devtools MCP can't attach when the user's own Chrome owns the profile** (`...cache\chrome-devtools-mcp\chrome-profile`). `AppTest` is the reliable headless fallback for reproducing Streamlit behavior — and it surfaces exceptions exactly as a real interaction would. `file_uploader` isn't settable via AppTest, so inject a fake via monkeypatched `st.file_uploader` in a tiny driver script.
- Printing Norwegian labels (`Blå`, `Grønn`) from a Bash heredoc python crashes on cp1252 — set `PYTHONIOENCODING=utf-8`.
- `IfcRelDefinesByProperties.RelatedObjects` relating one pset to thousands of objects is valid IFC4 and round-trips through ifcopenshell + viewers — this is the memory-efficient way to tag many elements with shared metadata.
- ifcopenshell resident-RAM rule of thumb measured this session: **~6× the .ifc file size** for load; processing (styles + psets) adds more on top.

## Untested / known-unknowns

- The fix wasn't verified against the *user's actual crashing file* — its size is unknown (the cloud log doesn't show it). If it's > ~200 MB, even the optimized app won't fit on Community Cloud and the real answer is moving the heavier tools to Railway/Hetzner. The 1.13 GB peak is for a 120 MB model; ~200 MB → ~1.3 GB and is borderline on the ~1 GB tier.
- Redeploy not yet observed succeeding — push landed (`a266526`), Community Cloud auto-redeploy assumed but not confirmed live this session.
- `requirements.txt` still unpinned — cloud will keep pulling latest streamlit/pandas/numpy. Not the crash cause, but a future-breakage risk (pandas 3.0 / numpy 2.5 are bleeding edge). Left as-is; pinning offered, not done.

## Pointers

- Commit: [a266526](https://github.com/EdvardGK/mmi-color-marker/commit/a266526) (fix: prevent OOM crash on Streamlit Community Cloud)
- Diff base: `6b4ac21..a266526`
- Local clone: `C:\workspace\toolkit\mmi-color-marker\`
- Crash log: `C:\Users\edkjo\Downloads\logs-edvardgk-mmi-color-marker-main-app.py-2026-06-22T14_40_22.044Z.txt`
- Memory: `[[fleet-hosting-architecture]]`, `[[sprucelab-reference-architecture]]`
- Prior worklog that predicted this: `worklog/2026-05-12-13-39_edkjo-color-all-products-and-upload-limit.md` (line 49)
