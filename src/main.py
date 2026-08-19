import os
import json
import time
import pandas as pd
import matplotlib.pyplot as plt
import openpyxl
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. SETUP & CONFIGURATION
# ---------------------------------------------------------
keys_env = os.environ.get("GEMINI_API_KEYS")
if not keys_env:
    raise ValueError("Please set the GEMINI_API_KEYS environment variable (comma-separated).")

api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]

PDF_PATH = "data/BoQ_CBRI_Principals_Residence.pdf"
TEMPLATE_PATH = "data/AMP_Passport_Template.xlsx"

# List of Flash models discovered from our check_models.py script
FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite"
]

meta_prompt = """
Analyze the first page of this uploaded document.
Extract the building metadata and return EXACTLY a JSON object with these keys:
- Project_Name
- Institute
- Location
- Depth_of_Foundation
- Plinth_Height
- Plinth_Area
- Seismic_Zone
- Capacity
"""

extract_prompt_template = """
You are an expert Quantity Surveyor and Data Engineer. 
Read the Bill of Quantities PDF. 
Extract ONLY the line items numbered from {start} to {end} inclusive into a structured JSON array of objects. 
Map the extracted data to these specific keys exactly:
- "BOQ Item No.": The serial number (e.g., "1.", "2.").
- "Description": The full text description of the work.
- "Original Quantity": The quantity number (e.g., 32.0). If empty, use null.
- "Original Unit": The unit of measurement (e.g., "Cu.m", "Sq.m", "Quintal").
- "Schedule Item Code": The DSR 1989 Code No. (e.g., "2.8", "4.5.10"). If empty, use null.
- "Material Category": Infer the primary material (e.g., "Concrete", "Earthwork", "Steel", "Brick", "Wood").
- "Discipline": Infer one of: "Civil & Sitework", "Structural", "Architectural".
- "Floor / Section": Identify the heading/sub-head from the BOQ (e.g., "Earth Work", "Concrete Work").
- "Material / Product": A short specific name (e.g., "Ready mix concrete", "TMT Bar", "Clay Bricks", "Earth").
- "Grade": Any material grade mentioned (e.g., "M-15", "Fe-500D"). If none, use null.
- "Mix Ratio": Any concrete/mortar mix ratio mentioned (e.g., "1:4:8", "1:6"). If none, use null.
- "Classification (Matched)": Create a hierarchical classification string (e.g., "Concrete > Nominal-mix > 1:4:8").

Respond ONLY with the JSON array. Do NOT extract items outside the range {start} to {end}.
"""

# ---------------------------------------------------------
# 2. MODEL ROTATION HELPER
# ---------------------------------------------------------
def generate_with_fallback(client, contents):
    """Tries a list of models. If one is overloaded (503) or missing (404), tries the next."""
    for model_name in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return response, model_name
        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "404" in err_str:
                print(f"    [!] Model {model_name} failed (503/404). Falling back to next model...")
                continue
            else:
                # If it's a 429 Quota Error, we raise it so the outer Key Rotation loop catches it
                raise e
    raise RuntimeError("All fallback models are currently unavailable or overloaded.")

# ---------------------------------------------------------
# 3. STATE TRACKING & CHUNKING SETUP
# ---------------------------------------------------------
metadata_done = False
meta_data = {}

chunks = [
    (1, 7), (8, 14), (15, 21), (22, 28), (29, 35),
    (36, 42), (43, 49), (50, 56), (57, 61), (62, 64)
]
completed_chunks = set()
all_extracted_items = []

print(f"Starting Bulletproof Pipeline with {len(api_keys)} Keys and {len(FALLBACK_MODELS)} Models.\n")

# ---------------------------------------------------------
# 4. STATEFUL KEY ROTATION & EXTRACTION LOOP
# ---------------------------------------------------------
for idx, key in enumerate(api_keys):
    if metadata_done and len(completed_chunks) == len(chunks):
        break  
        
    try:
        print(f"\n--- Attempting execution with API Key {idx + 1} of {len(api_keys)} ---")
        client = genai.Client(api_key=key)
        
        print("Uploading PDF to Gemini...")
        boq_file = client.files.upload(file=PDF_PATH, config={'display_name': f'BoQ_Key_{idx}'})
        
        if not metadata_done:
            print("Extracting Building Metadata...")
            meta_response, used_model = generate_with_fallback(client, [boq_file, meta_prompt])
            meta_data = json.loads(meta_response.text)
            metadata_done = True
            print(f"✔ Metadata extraction successful (using {used_model}).")
            time.sleep(10)

        for start, end in chunks:
            if (start, end) in completed_chunks:
                continue 
                
            print(f"Extracting Line Items {start} to {end}...")
            chunk_prompt = extract_prompt_template.format(start=start, end=end)
            
            boq_response, used_model = generate_with_fallback(client, [boq_file, chunk_prompt])
            chunk_items = json.loads(boq_response.text)
            all_extracted_items.extend(chunk_items)
            completed_chunks.add((start, end))
            print(f"✔ Successfully extracted items {start} to {end} (using {used_model}).")
            
            if len(completed_chunks) < len(chunks):
                time.sleep(10)
            
        print("\n✔ All chunks processed successfully!")
        
    except Exception as e:
        print(f"Error encountered: {e}")
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print(f"⚠ Rate limit reached on API Key {idx + 1}.")
            if idx < len(api_keys) - 1:
                print("Rotating to the next API key and resuming exactly where it left off...")
            else:
                print("All provided API keys exhausted.")
        else:
            print("Fatal error encountered. Halting execution.")
            break

os.makedirs("output", exist_ok=True)

# ---------------------------------------------------------
# 5. SAVE RAW JSON OUTPUTS
# ---------------------------------------------------------
print("\nSaving Output Files...")
with open("output/building_meta.json", "w") as f:
    json.dump(meta_data, f, indent=4)
print("✔ Metadata saved to output/building_meta.json")

with open("output/passport.json", "w") as f:
    json.dump(all_extracted_items, f, indent=4)
print(f"✔ Extracted {len(all_extracted_items)} items saved to output/passport.json")

# ---------------------------------------------------------
# 6. MAP TO EXCEL TEMPLATE, ROUTE DIMENSIONS & APPLY CARBON MATH
# ---------------------------------------------------------
print("Mapping data to Excel Template and applying Carbon Math...")

wb = openpyxl.load_workbook(TEMPLATE_PATH)
ws = wb["Material Passport"]

# Clear existing example rows (preserve headers in rows 1-3)
max_row = ws.max_row
if max_row >= 4:
    ws.delete_rows(4, max_row - 3)

# Get column names from row 3
headers = [cell.value for cell in ws[3]]

for item in all_extracted_items:
    qty = item.get("Original Quantity")
    unit = str(item.get("Original Unit") or "").lower().strip()
    mat_cat = str(item.get("Material Category", "")).lower()
    
    # Automated Carbon & Density Lookup
    density, gwp, comment = "", "", ""
    if "concrete" in mat_cat:
        density, gwp, comment = 2400, 0.15, "ICE Database V3.0 (Concrete)"
    elif "steel" in mat_cat or "reinforcement" in mat_cat:
        density, gwp, comment = 7850, 2.50, "ICE Database V3.0 (Steel)"
    elif "brick" in mat_cat:
        density, gwp, comment = 1900, 0.24, "ICE Database V3.0 (Bricks)"
    elif "wood" in mat_cat or "timber" in mat_cat:
        density, gwp, comment = 650, 0.45, "ICE Database V3.0 (Timber/Wood)"
    elif "earth" in mat_cat or "sand" in mat_cat:
        density, gwp, comment = 1600, 0.01, "ICE Database V3.0 (Aggregates/Sand)"

    # Base Row Dictionary (Fills ALL GREEN required columns now)
    row_dict = {
        "BOQ Item No.": item.get("BOQ Item No."),
        "Description": item.get("Description"),
        "Original Quantity": qty,
        "Original Unit": item.get("Original Unit"),
        "Schedule Item Code": item.get("Schedule Item Code"),
        "Material Category": item.get("Material Category"),
        "Discipline": item.get("Discipline"),
        "Floor / Section": item.get("Floor / Section"),
        "Material / Product": item.get("Material / Product"),
        "Grade": item.get("Grade"),
        "Mix Ratio": item.get("Mix Ratio"),
        "Classification (Matched)": item.get("Classification (Matched)"),
        "Schedule (DSR/SOR)": "DSR 1989", 
        "Density (kg/m³)": density,
        "GWP / kg (kg CO₂e/kg)": gwp,
        "Comment": comment
    }

    # Dynamic Dimensional Routing (Transforms Original Qty into proper column)
    try:
        q = float(qty) if qty else 0
    except:
        q = 0

    if q > 0:
        if "cum" in unit or "cu.m" in unit or "m3" in unit or "cubic" in unit:
            row_dict["Volume (m³)"] = q
        elif "sqm" in unit or "sq.m" in unit or "m2" in unit or "square" in unit:
            row_dict["Area (m²)"] = q
        elif unit in ["rm", "m", "metre", "meter", "running meter"]:
            row_dict["Length (m)"] = q
        elif "kg" in unit or "kilogram" in unit:
            row_dict["Weight (kg)"] = q
        elif "quintal" in unit:
            row_dict["Weight (kg)"] = q * 100
        elif "mt" in unit or "tonne" in unit:
            row_dict["Weight (kg)"] = q * 1000
        elif "each" in unit or "nos" in unit or "number" in unit:
            row_dict["Count (Nos)"] = q

    # Calculate Total Embodied Carbon (A1-A3) mathematically for AMBER columns
    if "Volume (m³)" in row_dict and density and gwp:
        row_dict["Embodied Carbon A1-A3 (kg CO₂e)"] = round(row_dict["Volume (m³)"] * density * gwp, 2)
    elif "Weight (kg)" in row_dict and gwp:
        row_dict["Embodied Carbon A1-A3 (kg CO₂e)"] = round(row_dict["Weight (kg)"] * gwp, 2)

    # Construct list matching template columns exactly
    row_values = [row_dict.get(col, "") for col in headers]
    ws.append(row_values)

wb.save("output/passport_filled.xlsx")
print("✔ Excel file saved cleanly to output/passport_filled.xlsx with dynamic dimensions and carbon math.")

# ---------------------------------------------------------
# 7. GENERATE VISUALIZATION CHART
# ---------------------------------------------------------
df_output = pd.DataFrame(all_extracted_items)
if not df_output.empty and "Material Category" in df_output.columns:
    print("Generating Material Distribution Chart...")
    df_plot = df_output["Material Category"].value_counts().reset_index()
    df_plot.columns = ["Material Category", "Count"]

    plt.figure(figsize=(10, 6))
    plt.bar(df_plot["Material Category"], df_plot["Count"], color="#2ecc71")
    plt.title("Distribution of Materials across BoQ Items")
    plt.xlabel("Material Category")
    plt.ylabel("Number of Line Items")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig("output/visualization.png", dpi=300)
    print("✔ Visualization chart saved to output/visualization.png")

print("\nPipeline execution complete! All deliverables generated.")