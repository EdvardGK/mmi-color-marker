# MMI 700 Fargelegger

Streamlit app for marking IFC elements with metallic colors based on property values.

## Features

- Browse and select any PropertySet, property, and value from your IFC model
- Applies metallic surface styling with 9 color options
- Adds `NOSKI_Eksisterende` property set with marking info
- Outputs colored IFC with `_farget` suffix
- Lazy loading for fast performance with large files

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run app.py
```

1. Upload an IFC file
2. Select PropertySet from dropdown
3. Select property name
4. Select value to filter by
5. Choose a color
6. Click "Fargelegg" to process

## Colors

Unusual metallic shades that stand out from typical BIM colors:

| Name | Shade |
|------|-------|
| Hvit | White |
| Rosa | Coral |
| Grønn | Mint |
| Magenta | Fuchsia |
| Gul | Gold |
| Lilla | Lavender |
| Blå | Petrol |
| Oransje | Apricot |
| Rød | Plum |

## Output

- **IFC file**: `{original}_farget.ifc` with colored elements
- **Property set**: `NOSKI_Eksisterende` added to each marked element
  - `Info`: Description of marking
  - `Farge`: Selected color name
  - `Filter`: Property filter used (e.g., `Pset_Name.Property=Value`)
  - `MarkeringsDato`: Date of marking

## Requirements

- Python 3.10+
- ifcopenshell
- streamlit
- pandas

## Hosting

- **Streamlit Community Cloud** (`mmi-farger.streamlit.app`) deploys from `requirements.txt`
  on push to `main`. ~1 GB RAM, hence the 200 MB upload cap in `.streamlit/config.toml`.
- **Self-hosted** (`mmi-farger.skiplum.com`, since 2026-09-04): the `Dockerfile` here, run on
  skiplum-apps-1 behind Caddy. The stack, deploy and status scripts live in
  `C:\workspace\skiplum\internal\infra\apps-server\` (`bash deploy.sh mmi-farger` ships this
  working tree and rebuilds on the server). Pins in the Dockerfile are the versions the app
  was verified against; `requirements.txt` stays unpinned for Community Cloud.
