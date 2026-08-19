import os
import json
import time
import pandas as pd
import matplotlib.pyplot as plt
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
- "Original Unit": The unit of measurement (e.g., "Cu.m", "Sq.m").
- "Schedule Item Code": The DSR 1989 Code No. (e.g., "2.8", "4.5.10"). If empty, use null.
- "Material Category": Infer the primary material (e.g., "Concrete", "Earthwork", "Steel", "Brick", "Wood").
- "Discipline": Infer one of: "Civil & Sitework", "Structural", "Architectural".

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
        
        # Step A: Metadata Extraction
        if not metadata_done:
            print("Extracting Building Metadata...")
            meta_response, used_model = generate_with_fallback(client, [boq_file, meta_prompt])
            meta_data = json.loads(meta_response.text)
            metadata_done = True
            print(f"✔ Metadata extraction successful (using {used_model}).")
            time.sleep(10)

        # Step B: Micro-Batch BoQ Extraction
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
# 5. SAVE RAW JSON OUTPUTS & EXCEL
# ---------------------------------------------------------
print("\nSaving Output Files...")

with open("output/building_meta.json", "w") as f:
    json.dump(meta_data, f, indent=4)
print("✔ Metadata saved to output/building_meta.json")

with open("output/passport.json", "w") as f:
    json.dump(all_extracted_items, f, indent=4)
print(f"✔ Extracted {len(all_extracted_items)} items saved to output/passport.json")

print("Mapping data to Excel Template and applying Carbon Factors...")
df_template = pd.read_excel(TEMPLATE_PATH, sheet_name="Material Passport", header=2)
columns = df_template.columns.tolist()

new_rows = []
for item in all_extracted_items:
    row = {col: "" for col in columns} 
    row["BOQ Item No."] = item.get("BOQ Item No.")
    row["Description"] = item.get("Description")
    row["Original Quantity"] = item.get("Original Quantity")
    row["Original Unit"] = item.get("Original Unit")
    row["Schedule Item Code"] = item.get("Schedule Item Code")
    row["Material Category"] = item.get("Material Category")
    row["Discipline"] = item.get("Discipline")
    
    mat_cat = str(item.get("Material Category", "")).lower()
    if "concrete" in mat_cat:
        row["Density (kg/m³)"] = 2400
        row["GWP / kg (kg CO₂e/kg)"] = 0.15
        row["Comment"] = "ICE Database V3.0 (Concrete)"
    elif "steel" in mat_cat:
        row["Density (kg/m³)"] = 7850
        row["GWP / kg (kg CO₂e/kg)"] = 2.50
        row["Comment"] = "ICE Database V3.0 (Steel)"
    elif "brick" in mat_cat:
        row["Density (kg/m³)"] = 1900
        row["GWP / kg (kg CO₂e/kg)"] = 0.24
        row["Comment"] = "ICE Database V3.0 (Bricks)"
    elif "wood" in mat_cat or "timber" in mat_cat:
        row["Density (kg/m³)"] = 650
        row["GWP / kg (kg CO₂e/kg)"] = 0.45
        row["Comment"] = "ICE Database V3.0 (Timber/Wood)"
    elif "earth" in mat_cat or "sand" in mat_cat:
        row["Density (kg/m³)"] = 1600
        row["GWP / kg (kg CO₂e/kg)"] = 0.01
        row["Comment"] = "ICE Database V3.0 (Aggregates/Sand)"
        
    new_rows.append(row)

df_output = pd.DataFrame(new_rows)
df_output.to_excel("output/passport_filled.xlsx", index=False)
print("✔ Excel file saved to output/passport_filled.xlsx")

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