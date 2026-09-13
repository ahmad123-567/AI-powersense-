# PowerSense AI

Pakistan-focused electricity bill transparency and complaint assistant.

## No demo data
The application does **not** insert demo bills, synthetic consumption history, or a hardcoded tariff calculation. Analysis is based on the bill uploaded by the user and retrieved knowledge-base context.

If a bill cannot be read confidently, the app asks for a clearer file instead of inventing values.

## Stack
- Streamlit
- Groq LLM
- LangChain
- HuggingFace sentence-transformers
- FAISS
- PyPDF + PyMuPDF
- Tesseract OCR

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

Set `GROQ_API_KEY` in Streamlit Secrets for AI extraction and analysis.
