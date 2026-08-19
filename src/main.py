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
# 5. MAP TO EXCEL TEMPLATE & APPLY CARBON FACTORS (Bonus B2)
# ---------------------------------------------------------
print("Mapping data to Excel Template and applying Carbon Factors...")

import openpyxl

# Load the original template workbook to preserve formatting, sheets, and headers
wb = openpyxl.load_workbook(TEMPLATE_PATH)
ws = wb["Material Passport"]

# Clear any existing example rows (rows 5 onwards, keeping headers rows 1-4)
# Row 4 is the first example row in the template (0-indexed or 1-indexed in openpyxl: rows 1,2,3,4 are headers/examples)
# Let's inspect the exact row indices:
# Row 1: Title
# Row 2: Category headers (IDENTIFICATION, ELEMENT & LOCATION, etc.)
# Row 3: Column names (GMAP Id, BOQ Item No., etc.)
# Row 4: Example 1
# So we can remove rows from row 4 downwards, then append our new rows!

max_row = ws.max_row
if max_row >= 4:
    ws.delete_rows(4, max_row - 3)

# Get column names from row 3 of the template
headers = [cell.value for cell in ws[3]]

# Map our extracted items and append to the worksheet
for item in all_extracted_items:
    row_data = []
    item_no = item.get("BOQ Item No.")
    desc = item.get("Description")
    qty = item.get("Original Quantity")
    unit = item.get("Original Unit")
    code = item.get("Schedule Item Code")
    mat_cat = item.get("Material Category")
    discipline = item.get("Discipline")
    
    # Calculate carbon factors
    density, gwp, comment = "", "", ""
    mat_lower = str(mat_cat).lower()
    if "concrete" in mat_lower:
        density, gwp, comment = 2400, 0.15, "ICE Database V3.0 (Concrete)"
    elif "steel" in mat_lower:
        density, gwp, comment = 7850, 2.50, "ICE Database V3.0 (Steel)"
    elif "brick" in mat_lower:
        density, gwp, comment = 1900, 0.24, "ICE Database V3.0 (Bricks)"
    elif "wood" in mat_lower or "timber" in mat_lower:
        density, gwp, comment = 650, 0.45, "ICE Database V3.0 (Timber/Wood)"
    elif "earth" in mat_lower or "sand" in mat_lower:
        density, gwp, comment = 1600, 0.01, "ICE Database V3.0 (Aggregates/Sand)"

    # Build row mapping based on column headers
    row_dict = {
        "BOQ Item No.": item_no,
        "Description": desc,
        "Original Quantity": qty,
        "Original Unit": unit,
        "Schedule Item Code": code,
        "Material Category": mat_cat,
        "Discipline": discipline,
        "Density (kg/m³)": density,
        "GWP / kg (kg CO₂e/kg)": gwp,
        "Comment": comment
    }
    
    # Construct list matching template columns
    row_values = [row_dict.get(col, "") for col in headers]
    ws.append(row_values)

wb.save("output/passport_filled.xlsx")
print("✔ Excel file saved cleanly to output/passport_filled.xlsx preserving template headers.")