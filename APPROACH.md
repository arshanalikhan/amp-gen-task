# Approach & Methodology

## 1. Tools Chosen & Why
*   **OCR & Extraction Pipeline:** Given my experience building the SafeStruct AI parsing pipeline with PyMuPDF and Regex, my initial instinct was programmatic extraction. However, because the input is a hand-annotated, dot-matrix scan, traditional text-layer extraction fails. Therefore, I opted for **Gemini 2.5 Pro** to act as a Vision-Language Model capable of reading the noisy scan and outputting structured JSON via precise prompt engineering.
*   **Data Processing:** **Python (Pandas & Regex)**. Used to clean the LLM output, enforce data types, and map the extracted quantities to the target Excel schema. 
*   **Visualization:** **Plotly / Matplotlib** to generate a clear, building-level material distribution chart, reflecting the data science visualization techniques I employ at IIT Madras.

## 2. What Worked
*   [To be filled during development]
*   [To be filled during development]

## 3. What Broke / Did Not Work
*   [To be filled during development]
*   [To be filled during development]

## 4. With 2 More Weeks...
*   **Vector Search & RAG:** I would implement a FAISS-based vector search (similar to my SafeStruct AI architecture) to automatically match the extracted 1989 DSR descriptions to modern, standardized material databases for automated EPD (Environmental Product Declaration) carbon mapping.
*   **Deployment:** I would wrap the extraction logic into a FastAPI backend and deploy it via Google Cloud Run, leveraging the cloud deployment workflows I learned while earning my Google Cloud Arcade badges.