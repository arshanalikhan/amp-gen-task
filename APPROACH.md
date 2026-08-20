# Technical Approach: AMP-GEN Material Passport Automation

## 1. Tools Chosen & Why
*   **OCR & Extraction Pipeline (Gemini via `google-genai`):** Given my experience building the *SafeStruct AI* parsing pipeline with PyMuPDF, my initial instinct was programmatic extraction. However, because the input is a hand-annotated, dot-matrix scan, traditional text-layer extraction fails. I opted for Google's Gemini models to act as a Vision-Language Model capable of reading the noisy scan and outputting structured JSON.
*   **Python (Regex, Pandas):** Selected for deterministic data cleaning, enforcing unit conventions, and mapping the extracted quantities to the target Excel schema.
*   **OpenPyXL:** Chosen over Pandas `to_excel()` to write data directly into the provided `.xlsx` template. This preserved the client's pre-formatted color-coded headers (Rows 1-3) and allowed me to programmatically apply "Wrap Text" and Top-Alignment for a professional finish.
*   **Visualization (Matplotlib):** Used to generate a clear, building-level material distribution chart, reflecting the data science visualization techniques I employ at IIT Madras.

## 2. What Worked Perfectly
*   **Hierarchical Sub-Item Splitting:** Legacy BoQs nest multiple distinct physical assets under a single description (e.g., *16.i, 16.ii*). A strict prompt rule successfully split these into discrete JSON objects, allowing the generation of globally unique, relational identifiers (`GMAP Id`: `AMP-CBRI-PR-16-i`).
*   **Dynamic Derived Quantities (Area to Volume):** To accurately calculate Embodied Carbon (A1-A3), Area metrics (`sqm`) often require conversion to Volume (`cum`). The prompt was engineered to extract hidden dimensions (e.g., `Thickness (mm)`). My Python script then dynamically calculates the `Derived Quantity` (Area × Thickness) to compute final carbon yields.
*   **Domain-Aware Data Cleaning & Forward Filling:** 
    *   **Grades:** If the LLM failed to extract a Concrete/Mortar Grade, the Python script cross-referenced the `Mix Ratio` against IS 456 standards (e.g., `1:2:4` -> `M15`, `1:6` -> `Mortar 1:6`).
    *   **Headers:** BoQs omit repeating section headers. I implemented a contextual forward-fill algorithm that memorized valid `Floor / Section` headers and applied them to child items while filtering out OCR garbage text (e.g., "Bill of Quantities").
*   **Automated QA/QC Audit Trail:** To mirror professional data engineering standards, I instructed the LLM to generate audit tags (`[OK]`, `[FLAG]` for messy handwriting, `[MULTI-SUB]`). This was merged into the `Comment` column alongside the ICE Database V3.0 citations.

## 3. What Broke / Did Not Work (and How It Was Fixed)
*   **SDK Migration & Deprecation Cascades:** My initial calls using legacy Gemini model tags threw `404` errors. Drawing from my experience building *AI Learning Tracker Pro*, I investigated the API and realized legacy models and the old `google.generativeai` SDK were deprecated. I successfully migrated the entire pipeline to the modern `google.genai` SDK and pinned it to `gemini-3.6-flash` mid-task.
*   **Token Limits & Dual-Rotation Architecture:** To bypass strict preview-model rate limits, I engineered a **Stateful, Chunked API Key Rotation architecture**. I broke extraction into micro-batches of 7 items. If a model throws a `503` (high demand), a custom helper function falls back through a ranked list of Flash models. If a key hits a `429` rate limit, the script rotates the API key and resumes exactly where it left off, ensuring uninterrupted extraction.
*   **LLM Blindspots for Standard Codes & Units:** The LLM frequently failed to extract Indian Standard codes (IS: 9103) and output raw unit variations ("Mtr.", "Cubic decimetre"). *Fix:* I bypassed the LLM's JSON output for these fields. I applied an aggressive `re.findall()` Regex directly against the raw description string to achieve 100% capture of IS Codes, and wrote a strict Python normalizer to map units before JSON serialization.

## 4. With 2 More Weeks...
*   **Vector Search & RAG:** I would implement a FAISS-based vector search (similar to my *SafeStruct AI* architecture) to automatically match the extracted 1989 DSR descriptions to modern, standardized material databases for automated EPD (Environmental Product Declaration) carbon mapping.
*   **Automated Circularity Scoring:** I would implement Madaster-style algorithms to automatically calculate the skipped grey columns (`Circularity`, `Detachability`, `Lifespan`) based on the extracted Material Categories and Discipline constraints.
*   **Deployment:** I would wrap the extraction logic into a FastAPI backend and deploy it via Google Cloud Run, leveraging the cloud deployment workflows I learned while earning my Google Cloud Arcade badges.