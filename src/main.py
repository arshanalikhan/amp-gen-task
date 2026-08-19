import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from google import genai
from google.genai import types

# 1. Setup & Configuration
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Please set the GEMINI_API_KEY environment variable.")

# Using the modern SDK syntax exactly like AI Learning Tracker Pro
client = genai.Client(api_key=API_KEY)

PDF_PATH = "data/BoQ_CBRI_Principals_Residence.pdf"
TEMPLATE_PATH = "data/AMP_Passport_Template.xlsx"

# 2. Upload the file
print("Uploading PDF to Gemini...")
boq_file = client.files.upload(file=PDF_PATH, config={'display_name': 'BoQ_Principals_Residence'})
print(f"Uploaded securely as: {boq_file.name}")

# 3. Extract Metadata (Bonus B3)
print("Extracting Building Metadata...")
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
meta_response = client.models.generate_content(
    model='gemini-3.1-pro-preview',
    contents=[boq_file, meta_prompt],
    config=types.GenerateContentConfig(response_mime_type="application/json")
)
with open("output/building_meta.json", "w") as f:
    json.dump(json.loads(meta_response.text), f, indent=4)
print("✔ Metadata saved to output/building_meta.json")

# 4. Extract Line Items (Core Task)
print("Extracting 64 Line Items... (This will take ~60 seconds)")
extract_prompt = """
You are an expert Quantity Surveyor and Data Engineer. 
Read the entire Bill of Quantities PDF. There are 64 line items.
Extract every line item into a structured JSON array of objects. 
Map the extracted data to these specific keys exactly:
- "BOQ Item No.": The serial number (e.g., "1.", "2.").
- "Description": The full text description of the work.
- "Original Quantity": The quantity number (e.g., 32.0). If empty, use null.
- "Original Unit": The unit of measurement (e.g., "Cu.m", "Sq.m").
- "Schedule Item Code": The DSR 1989 Code No. (e.g., "2.8", "4.5.10"). If empty, use null.
- "Material Category": Infer the primary material (e.g., "Concrete", "Earthwork", "Steel", "Brick", "Wood").
- "Discipline": Infer one of: "Civil & Sitework", "Structural", "Architectural".

Respond ONLY with the JSON array. Ensure all 64 items are captured.
"""
boq_response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=[boq_file, extract_prompt],
    config=types.GenerateContentConfig(response_mime_type="application/json")
)
extracted_items = json.loads(boq_response.text)

with open("output/passport.json", "w") as f:
    json.dump(extracted_items, f, indent=4)
print(f"✔ Extracted {len(extracted_items)} items to output/passport.json")

# 5. Process Data & Map to Excel Template
print("Mapping to Excel Template and applying Carbon Factors...")
df_template = pd.read_excel(TEMPLATE_PATH, sheet_name="Material Passport", header=2)
columns = df_template.columns.tolist()

new_rows = []
for item in extracted_items:
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
        
    new_rows.append(row)

df_output = pd.DataFrame(new_rows)
df_output.to_excel("output/passport_filled.xlsx", index=False)
print("✔ Excel saved to output/passport_filled.xlsx")

# 6. Generate Visualization
print("Generating Material Distribution Chart...")
df_plot = df_output.groupby("Material Category").size().reset_index(name="Count")
df_plot = df_plot.sort_values("Count", ascending=False)

plt.figure(figsize=(10, 6))
plt.bar(df_plot["Material Category"], df_plot["Count"], color="#2ecc71")
plt.title("Distribution of Materials across BoQ Items")
plt.xlabel("Material Category")
plt.ylabel("Number of Line Items")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("output/visualization.png", dpi=300)
print("✔ Visualization saved to output/visualization.png")

print("\nPipeline complete! All deliverables generated.")