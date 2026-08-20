# AMP-GEN Material Passport Extraction Pipeline

## Quickstart (Under 5 Minutes)
1. Clone the repository: `git clone https://github.com/arshanalikhan/amp-gen-task.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the pipeline: `python src/main.py`

## Honest Time Estimate
- **Total Hours Spent:** [11]
- **Items Extracted:** [64] of 64

## Bonus Objectives Attempted
- [✅] B1: Live Deployment [(URL: ...)](https://ampgentask.streamlit.app/)
- [✅] B2: EPD Carbon Data included
- [✅] B3: Metadata Extraction (`output/building_meta.json`)
- [✅] B4: Video Walkthrough [(URL: ...)](https://youtu.be/r1BkZNDuAok)


## Project Structure

```text
amp-gen-task/
├── .devcontainer/                  # Development container configurations
├── data/                           # Input BoQ documents and official templates
│   ├── AMP_Passport_Template.xlsx  # Official client Excel template
│   └── BoQ_CBRI_Principals...pdf   # Source document (1989 DSR scan)
├── output/                         # Generated assets and passport deliverables
│   ├── building_meta.json          # Extracted building metadata (Bonus B3)
│   ├── passport.json               # Raw JSON extraction output
│   ├── passport_filled.xlsx        # Fully populated final Material Passport
│   └── visualization.png           # Material distribution chart
├── src/                            # Source code modules
│   ├── main.py                     # Core orchestration script
│   ├── ocr_pipeline.py             # Streamlit live app & Gemini VLM pipeline
│   └── check_models.py             # API connectivity & model validation
├── APPROACH.md                     # Detailed technical architecture document
├── README.md                       # Main repository guide and quickstart
└── requirements.txt                # Python dependencies
