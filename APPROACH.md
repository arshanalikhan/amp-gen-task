# Approach & Methodology

## 1. Tools Chosen & Why
*   **OCR & Extraction Pipeline:** Given my experience building the SafeStruct AI parsing pipeline with PyMuPDF and Regex, my initial instinct was programmatic extraction. However, because the input is a hand-annotated, dot-matrix scan, traditional text-layer extraction fails. Therefore, I opted for **Gemini 2.5 Pro** to act as a Vision-Language Model capable of reading the noisy scan and outputting structured JSON via precise prompt engineering.
*   **Data Processing:** **Python (Pandas & Regex)**. Used to clean the LLM output, enforce data types, and map the extracted quantities to the target Excel schema. 
*   **Visualization:** **Plotly / Matplotlib** to generate a clear, building-level material distribution chart, reflecting the data science visualization techniques I employ at IIT Madras.

## 2. What Worked
*   [To be filled during development]
*   [To be filled during development]

## 3. What Broke / Did Not Work
*   **Model Deprecation Cascades:** 
    1. My initial API call using the `gemini-1.5-pro` model tag threw a `404 grpc_status` error. 
    2. I instantly recognized this from when I built *AI Learning Tracker Pro*, where I generated a 50k-sentence synthetic dataset using the Gemini API. I updated the target to `gemini-2.5-pro` (the model I used then).
    3. The API returned another 404, explicitly stating `gemini-2.5-pro` is no longer available to new users and routing me to `gemini-3.1-pro-preview`.
    4. **Resolution:** I pinned the pipeline to the `3.1-pro-preview` model, successfully handling the rapid version shifts characteristic of live cloud APIs.
*   **SDK Migration:** The terminal logged a `FutureWarning` that the legacy `google.generativeai` package is dead. I paused, uninstalled the old library, refactored my codebase, and successfully migrated the entire pipeline to the modern `google.genai` SDK mid-task.
*   **Token Limits & Payload Chunking:** Google's new `3.1-pro-preview` model has an extremely restrictive free-tier input token limit, causing a `429 RESOURCE_EXHAUSTED` error immediately when attempting to extract all 64 items at once. Drawing from my experience generating synthetic datasets, I solved this by engineering a **Stateful, Chunked API Key Rotation architecture**. I broke the extraction into 5 smaller batches (13 items each) to keep the payload lightweight. The script accepts a list of API keys and tracks its own execution state. If a key dies mid-pipeline (e.g., after chunk 2), it rotates to the next key and resumes exactly at chunk 3, successfully processing the data without restarting from scratch.
## 4. With 2 More Weeks...
*   **Vector Search & RAG:** I would implement a FAISS-based vector search (similar to my SafeStruct AI architecture) to automatically match the extracted 1989 DSR descriptions to modern, standardized material databases for automated EPD (Environmental Product Declaration) carbon mapping.
*   **Deployment:** I would wrap the extraction logic into a FastAPI backend and deploy it via Google Cloud Run, leveraging the cloud deployment workflows I learned while earning my Google Cloud Arcade badges.