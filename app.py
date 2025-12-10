"""
MMI 700 Fargelegger

Marks IFC elements with MMI=700 property to indicate existing elements.
Adds color and NOSKI_Eksisterende property set.

Run: streamlit run app.py
"""

import tempfile
from pathlib import Path
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import ifcopenshell
import ifcopenshell.api

# =============================================================================
# CONFIGURATION
# =============================================================================

# Unusual metallic shades with simple base color names
COLORS = {
    "Hvit": (1.0, 1.0, 1.0),          # White
    "Rosa": (1.0, 0.5, 0.4),          # Coral shade
    "Grønn": (0.4, 0.9, 0.7),         # Mint shade
    "Magenta": (0.9, 0.2, 0.6),       # Fuchsia shade
    "Gul": (0.85, 0.65, 0.2),         # Gold shade
    "Lilla": (0.7, 0.5, 0.9),         # Lavender shade
    "Blå": (0.1, 0.5, 0.5),           # Petrol shade
    "Oransje": (1.0, 0.7, 0.5),       # Apricot shade
    "Rød": (0.5, 0.2, 0.4),           # Plum shade
}

PSET_NAME = "NOSKI_Eksisterende"

# =============================================================================
# IFC PROCESSING
# =============================================================================


def build_pset_index(ifc_file):
    """Build index of psets attached to elements (one-time scan)."""
    # Structure: {pset_name: {prop_name: {value: count}}}
    index = {}

    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
        # Skip if not attached to any IfcProduct (element)
        if not any(obj.is_a("IfcProduct") for obj in rel.RelatedObjects):
            continue

        pset = rel.RelatingPropertyDefinition
        if not pset.is_a("IfcPropertySet") or not pset.Name:
            continue

        pset_name = pset.Name
        if pset_name not in index:
            index[pset_name] = {}

        for prop in pset.HasProperties:
            if not prop.is_a("IfcPropertySingleValue") or not prop.Name:
                continue

            prop_name = prop.Name
            if prop_name not in index[pset_name]:
                index[pset_name][prop_name] = {}

            nominal_value = prop.NominalValue
            if nominal_value is None:
                value = "Ingen verdi"
            else:
                value = nominal_value.wrappedValue if hasattr(nominal_value, "wrappedValue") else nominal_value
                value = str(value) if value else "Ingen verdi"

            if value not in index[pset_name][prop_name]:
                index[pset_name][prop_name][value] = 0
            index[pset_name][prop_name][value] += 1

    return index


def find_elements_by_property(ifc_file, pset_name, prop_name, prop_value):
    """Find all elements matching a specific pset/property/value combination."""
    matches = []
    for element in ifc_file.by_type("IfcProduct"):
        if not hasattr(element, "IsDefinedBy"):
            continue
        for rel in element.IsDefinedBy:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pset = rel.RelatingPropertyDefinition
            if not pset.is_a("IfcPropertySet"):
                continue
            if pset.Name != pset_name:
                continue

            for prop in pset.HasProperties:
                if not prop.is_a("IfcPropertySingleValue"):
                    continue
                if prop.Name != prop_name:
                    continue

                nominal_value = prop.NominalValue
                if nominal_value is None:
                    value = "Ingen verdi"
                else:
                    value = nominal_value.wrappedValue if hasattr(nominal_value, "wrappedValue") else nominal_value
                    value = str(value) if value else "Ingen verdi"

                if value == prop_value:
                    matches.append((element, prop_name, pset_name))

    return matches


def get_or_create_style(ifc_file, color_name, rgb):
    """Get or create a metallic surface style with the given color."""
    style_name = f"{PSET_NAME}_{color_name}"
    for style in ifc_file.by_type("IfcSurfaceStyle"):
        if style.Name == style_name:
            return style

    style = ifcopenshell.api.run("style.add_style", ifc_file, name=style_name)

    # Create metallic/reflective rendering style
    ifcopenshell.api.run(
        "style.add_surface_style", ifc_file, style=style,
        ifc_class="IfcSurfaceStyleRendering",
        attributes={
            "SurfaceColour": {"Name": None, "Red": rgb[0], "Green": rgb[1], "Blue": rgb[2]},
            "Transparency": 0.0,
            "DiffuseColour": {"Name": None, "Red": rgb[0], "Green": rgb[1], "Blue": rgb[2]},
            "SpecularColour": {"Name": None, "Red": 1.0, "Green": 1.0, "Blue": 1.0},
            "SpecularHighlight": {"IfcSpecularRoughness": 0.2},  # Low roughness = shiny
            "ReflectanceMethod": "METAL",
        }
    )
    return style


def build_styled_item_index(ifc_file):
    """Build index of styled items by their Item reference."""
    index = {}
    for si in ifc_file.by_type("IfcStyledItem"):
        if si.Item:
            index[si.Item.id()] = si
    return index


def apply_color_to_element(ifc_file, element, style, styled_index):
    """Apply surface style to element's representation."""
    if not hasattr(element, "Representation") or element.Representation is None:
        return False
    try:
        applied = False
        for rep in element.Representation.Representations:
            if not rep.is_a("IfcShapeRepresentation"):
                continue

            for item in rep.Items:
                existing_styled = styled_index.get(item.id())

                if existing_styled:
                    # Update existing styled item with our style
                    existing_styled.Styles = [style]
                    applied = True
                else:
                    # Create new styled item
                    new_si = ifc_file.create_entity(
                        "IfcStyledItem",
                        Item=item,
                        Styles=[style],
                        Name=None
                    )
                    styled_index[item.id()] = new_si
                    applied = True

        return applied
    except Exception:
        return False


def add_pset(ifc_file, element, color_name, filter_pset=None, filter_prop=None, filter_value=None):
    """Add NOSKI_Eksisterende property set to element."""
    filter_info = f"{filter_pset}.{filter_prop}={filter_value}" if filter_pset else "MMI=700"
    props = {
        "Info": f'Farget med "{color_name}" basert på {filter_info}.',
        "Farge": color_name,
        "Filter": filter_info,
        "MarkeringsDato": datetime.now().strftime("%Y-%m-%d"),
        "Laget av": "Skiplum",
        "Kontaktperson": "Edvard Granskogen Kjørstad",
        "Epost": "egk@skiplum.no",
        "Generert med": "Python og IfcOpenShell",
    }

    if hasattr(element, "IsDefinedBy"):
        for rel in element.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                pset = rel.RelatingPropertyDefinition
                if pset.is_a("IfcPropertySet") and pset.Name == PSET_NAME:
                    ifcopenshell.api.run("pset.edit_pset", ifc_file, pset=pset, properties=props)
                    return True

    ifcopenshell.api.run("pset.add_pset", ifc_file, product=element, name=PSET_NAME)
    for rel in element.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            pset = rel.RelatingPropertyDefinition
            if pset.is_a("IfcPropertySet") and pset.Name == PSET_NAME:
                ifcopenshell.api.run("pset.edit_pset", ifc_file, pset=pset, properties=props)
                return True
    return False


# =============================================================================
# DIALOGS
# =============================================================================


@st.dialog("Elementer", width="large")
def show_preview_dialog(data):
    st.dataframe(pd.DataFrame(data), hide_index=True, height=500)


@st.dialog("Resultat - detaljer", width="large")
def show_results_dialog(data):
    st.dataframe(pd.DataFrame(data), hide_index=True, height=500)


# =============================================================================
# UI
# =============================================================================

def main():
    st.set_page_config(page_title="MMI 700 Fargelegger", page_icon="🎨", layout="centered")

    # Custom CSS
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #f5f5f0 0%, #e8e4dc 100%); }
        .block-container { padding-top: 3.5rem; max-width: 800px; }
        header[data-testid="stHeader"] { background: transparent; }

        .app-header {
            background: linear-gradient(135deg, #2d4a3e 0%, #3d5a4e 100%);
            color: white;
            padding: 1.5rem 2rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
        }
        .app-header h1 { color: white; margin: 0; font-size: 1.5rem; font-weight: 600; }
        .app-header p { color: #b8c9bf; margin: 0.25rem 0 0 0; font-size: 0.9rem; }

        .summary-card {
            background: white;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            text-align: center;
            border-left: 4px solid #2d4a3e;
        }
        .summary-card h4 { font-size: 0.75rem; color: #64748b; margin: 0; text-transform: uppercase; }
        .summary-card .value { font-size: 1.75rem; font-weight: 700; color: #334155; }

        .result-card {
            background: white;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            text-align: center;
        }
        .result-card.ok { border-left: 4px solid #10b981; }
        .result-card.ok .value { color: #059669; }

        [data-testid="stFileUploader"] {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            border: 2px dashed #94a3b8;
        }

        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        .stDeployButton { display: none; }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="app-header">
        <h1>🎨 MMI 700 Fargelegger</h1>
        <p>Fargelegg eksisterende elementer i IFC-modeller</p>
    </div>
    """, unsafe_allow_html=True)

    # File upload
    uploaded = st.file_uploader("Last opp IFC-fil", type=["ifc"], label_visibility="collapsed")

    if not uploaded:
        st.info("Last opp en IFC-fil for å starte")
        with st.expander("ℹ️ Om verktøyet"):
            st.markdown("""
**Funksjon:** Fargelegg elementer basert på PropertySet-verdier.

**Output:**
- Farget IFC-fil med suffix `_farget`
- PropertySet `NOSKI_Eksisterende` med info om fargingen
            """)
        return

    # Load IFC file (cached)
    file_key = f"ifc_{uploaded.name}_{uploaded.size}"
    if file_key not in st.session_state:
        # Only write temp file when loading new file
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name

        with st.spinner("Laster IFC-fil..."):
            try:
                ifc = ifcopenshell.open(tmp_path)
            except Exception as e:
                st.error(f"Kunne ikke lese IFC-fil: {e}")
                return
            st.session_state[file_key] = ifc
            st.session_state["tmp_path"] = tmp_path
    else:
        ifc = st.session_state[file_key]
        tmp_path = st.session_state["tmp_path"]

    # --- Property Selection (single scan, cached index) ---
    st.markdown("#### Velg egenskap")

    # Build index once per file
    index_key = f"pset_index_{file_key}"
    if index_key not in st.session_state:
        with st.spinner("Indekserer egenskaper..."):
            st.session_state[index_key] = build_pset_index(ifc)
    pset_index = st.session_state[index_key]

    pset_names = sorted(pset_index.keys())
    selected_pset = st.selectbox("PropertySet", pset_names, label_visibility="collapsed")

    selected_prop = None
    selected_value = None

    if selected_pset:
        prop_names = sorted(pset_index[selected_pset].keys())

        col1, col2 = st.columns(2)
        with col1:
            selected_prop = st.selectbox("Egenskap", prop_names, label_visibility="collapsed")
        with col2:
            if selected_prop:
                values = pset_index[selected_pset][selected_prop]
                value_options = sorted(values.keys(), key=lambda v: -values[v])
                value_labels = [f"{v} ({values[v]})" for v in value_options]
                if value_options:
                    selected_idx = st.selectbox("Verdi", range(len(value_options)),
                                               format_func=lambda i: value_labels[i],
                                               label_visibility="collapsed")
                    selected_value = value_options[selected_idx]

    # --- Color Selection ---
    st.markdown("#### Velg farge")
    selected_color = st.session_state.get("selected_color")

    # Clear invalid color selection
    if selected_color and selected_color not in COLORS:
        selected_color = None
        st.session_state.selected_color = None

    # Render color buttons (3x3 grid)
    color_list = list(COLORS.items())
    for row in range(3):
        cols = st.columns(3)
        for i, col in enumerate(cols):
            idx = row * 3 + i
            if idx >= len(color_list):
                break
            name, rgb_val = color_list[idx]
            with col:
                if st.button(name, key=f"btn_{name}", use_container_width=True):
                    st.session_state.selected_color = name
                    st.rerun()

    # Inject JS to color the buttons
    color_js = "const colorMap = {"
    for name, rgb_val in COLORS.items():
        hex_color = f"#{int(rgb_val[0]*255):02x}{int(rgb_val[1]*255):02x}{int(rgb_val[2]*255):02x}"
        is_selected = selected_color == name
        border = "3px solid #333" if is_selected else "none"
        color_js += f'"{name}": {{hex: "{hex_color}", selected: {str(is_selected).lower()}, border: "{border}"}},'
    color_js += "};"

    components.html(f"""
    <script>
        function colorButtons() {{
            {color_js}
            const buttons = window.parent.document.querySelectorAll('button[kind="secondary"]');
            buttons.forEach(btn => {{
                const text = btn.innerText.trim();
                if (colorMap[text]) {{
                    btn.style.background = colorMap[text].hex;
                    btn.style.color = 'white';
                    btn.style.border = colorMap[text].border;
                    btn.style.textShadow = '1px 1px 2px rgba(0,0,0,0.4)';
                    btn.style.fontWeight = '600';
                    btn.style.minHeight = '45px';
                    btn.style.width = '100%';
                }}
            }});
        }}
        colorButtons();
        setTimeout(colorButtons, 100);
        setTimeout(colorButtons, 300);
    </script>
    """, height=0)

    if not selected_color or not selected_value:
        return

    rgb = COLORS[selected_color]

    # Find matching elements (use cached IFC if available)
    matches_key = f"matches_{selected_pset}_{selected_prop}_{selected_value}"
    if matches_key not in st.session_state:
        with st.spinner("Søker etter elementer..."):
            ifc = st.session_state.get("ifc_file") or ifcopenshell.open(tmp_path)
            matches = find_elements_by_property(ifc, selected_pset, selected_prop, selected_value)
            st.session_state[matches_key] = matches
    else:
        matches = st.session_state[matches_key]

    unique_guids = set(m[0].GlobalId for m in matches)

    # Summary cards
    st.markdown("#### Oppsummering")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'''
        <div class="summary-card">
            <h4>Elementer funnet</h4>
            <div class="value">{len(unique_guids)}</div>
        </div>
        ''', unsafe_allow_html=True)
    with col2:
        hex_color = f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"
        st.markdown(f'''
        <div class="summary-card" style="border-left-color: {hex_color};">
            <h4>Valgt farge</h4>
            <div class="value" style="color: {hex_color};">{selected_color}</div>
        </div>
        ''', unsafe_allow_html=True)

    if not unique_guids:
        st.warning(f"Ingen elementer funnet med {selected_pset}.{selected_prop}={selected_value}")
        return

    # Preview button
    preview_data = []
    seen = set()
    for elem, prop, pset in matches:
        if elem.GlobalId in seen:
            continue
        seen.add(elem.GlobalId)
        preview_data.append({"Type": elem.is_a(), "Navn": elem.Name or "-", "Egenskap": prop})

    if st.button("👁️ Vis elementer"):
        show_preview_dialog(preview_data)

    st.markdown("---")

    # Process button
    if st.button(f"🎨 Fargelegg {len(unique_guids)} elementer", type="primary"):
        progress_container = st.empty()

        with progress_container.container():
            st.info(f"🔄 Starter fargelegging av {len(unique_guids)} elementer...")
            progress_bar = st.progress(0, text="Laster IFC-fil...")

        # Load file
        ifc = ifcopenshell.open(tmp_path)
        progress_bar.progress(15, text="Oppretter fargestil...")

        # Create style
        style = get_or_create_style(ifc, selected_color, rgb)
        progress_bar.progress(20, text="Indekserer eksisterende stiler...")

        # Build styled item index for fast lookup
        styled_index = build_styled_item_index(ifc)
        progress_bar.progress(30, text=f"Fargelegger {len(unique_guids)} elementer...")

        # Process elements
        results = {"total": 0, "colored": 0, "elements": []}
        processed = set()
        total = len(unique_guids)

        for idx, (element, prop_name, pset_name) in enumerate(matches):
            if element.GlobalId in processed:
                continue
            processed.add(element.GlobalId)

            colored = apply_color_to_element(ifc, element, style, styled_index)
            add_pset(ifc, element, selected_color, selected_pset, selected_prop, selected_value)

            if colored:
                results["colored"] += 1
            results["total"] += 1
            results["elements"].append({
                "GUID": element.GlobalId,
                "Type": element.is_a(),
                "Navn": element.Name or "-",
                "Egenskap": prop_name,
                "Farget": "OK" if colored else "Feilet",
            })

            # Update progress
            pct = 30 + int((len(processed) / total) * 50)
            progress_bar.progress(pct, text=f"Fargelegger... {len(processed)}/{total}")

        progress_bar.progress(85, text="Lagrer IFC-fil...")

        output_name = f"{Path(uploaded.name).stem}_farget.ifc"
        output_path = Path(tempfile.gettempdir()) / output_name
        ifc.write(str(output_path))

        progress_bar.progress(100, text="Ferdig!")
        progress_container.empty()

        st.session_state.results = results
        st.session_state.output_path = output_path
        st.session_state.output_name = output_name
        st.rerun()

    # Results
    if "results" in st.session_state:
        results = st.session_state.results

        st.markdown("#### Resultat")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'''
            <div class="result-card ok">
                <h4 style="font-size:0.75rem;color:#64748b;margin:0;">Fargelagt</h4>
                <div class="value" style="font-size:1.75rem;font-weight:700;">{results["colored"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        with col2:
            st.markdown(f'''
            <div class="result-card">
                <h4 style="font-size:0.75rem;color:#64748b;margin:0;">Totalt</h4>
                <div class="value" style="font-size:1.75rem;font-weight:700;color:#334155;">{results["total"]}</div>
            </div>
            ''', unsafe_allow_html=True)

        # Downloads
        st.markdown("")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Vis detaljer"):
                show_results_dialog(results["elements"])
        with col2:
            with open(st.session_state.output_path, "rb") as f:
                st.download_button(
                    "⬇️ Last ned IFC",
                    f.read(),
                    st.session_state.output_name,
                    "application/octet-stream",
                    type="primary"
                )


if __name__ == "__main__":
    main()
