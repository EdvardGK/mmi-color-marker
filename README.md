# MMI 700 Fargelegger

Streamlit app for marking existing elements (MMI=700) in IFC models with metallic colors.

## Features

- Scans IFC files for elements with `*MMI*` properties set to `700`
- Applies metallic surface styling with 9 color options
- Adds `NOSKI_Eksisterende` property set with marking info
- Outputs colored IFC with `_farget` suffix

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run app.py
```

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
  - `MarkeringsDato`: Date of marking

## Requirements

- Python 3.10+
- ifcopenshell
- streamlit
- pandas
