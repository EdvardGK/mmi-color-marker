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
