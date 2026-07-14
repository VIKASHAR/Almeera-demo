# Al Meera Grocery Mimic Storefront & Integrated AI Cart Chatbot POC

This repository contains a professional grocery storefront e-commerce demonstration inspired by **Al Meera**, featuring a floating, inventory-aware AI shopping assistant widget. 

The project operates as a **single unified system**: a read-only storefront frontend interacting with a single FastAPI backend that handles both product searches/details and the multi-agent parallel LangGraph checkout chatbot.

---

## 1. System Architecture

```
al-meera-poc/
├── frontend/                        (Vite + React App — Storefront + Floating Chatbot widget)
│   ├── src/
│   │   ├── App.jsx                  → Storefront logic: homepage, product details, cart state, chatbot popup
│   │   ├── index.css                → Theme styles: white bg, Al Meera green/red theme, violet/orange recommendations
│   │   └── main.jsx
│   └── .env.local                   → VITE_API_URL=http://localhost:8000
│
└── src/                             (FastAPI backend server)
    ├── main.py                      → Entrypoint (chatbot /chat, product details, categories API, CORS middleware)
    ├── database.py                  → SQLite database helper module (stock-aware recommendation filters)
    ├── graph.py                     → LangGraph chatbot routing & execution flow
    └── config.py                    → LLM parameters & Groq/Gemini client initializers
```

---

## 2. Local Development Setup

Follow these steps to run both backend and frontend servers on your local machine:

### A. Backend Setup (FastAPI)
1. Navigate to the repository root.
2. Install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Verify your `.env` file at the repository root contains valid API keys:
   ```env
   GROQ_API_KEY=gsk_...
   GEMINI_API_KEY=AIzaSy...
   PORT=8000
   DATABASE_URL=db/mvp_demo.db
   ```
4. Start the FastAPI backend:
   ```bash
   cd src
   py main.py
   ```
   The backend server will run on `http://localhost:8000`.

### B. Frontend Setup (Vite + React)
1. Navigate to the `frontend/` directory.
2. Install npm packages:
   ```bash
   npm install
   ```
3. Verify `frontend/.env.local` contains:
   ```env
   VITE_API_URL=http://localhost:8000
   ```
4. Start the local Vite server:
   ```bash
   npm run dev
   ```
   The frontend will run locally on `http://localhost:5173` (or `http://localhost:3000` depending on terminal port allocations).

---

## 3. Storefront Core Features
1. **Branded Color Scheme**: Uses a clean, professional retail-white background, custom Al Meera Green (`#1b7a3e`) brand details, **violet** personalized recommendations, and **orange** affinity deals.
2. **Channel & Profile Selector**: Adjust shopping contexts between Online vs. In-Store channels, or swap customer personas to test custom search outputs.
3. **Active Cart Drawer**: Adds items to a client-side shopping cart with dynamic subtotal calculations and stock-aware thresholds.
4. **Allergen & Preference Safeguards**: Renders explicit alert panels on product details pages if a item violates the customer's active diet (e.g. low-fat) or triggers allergy warnings (e.g. dairy or nuts).
5. **Popup AI Assistant**: A circular fixed button in the bottom-right opens the chatbot popover. Chat logs and active states persist when opening, closing, or navigating storefront pages.

---

## 4. Deployment Guide (Render / Vercel)

### A. Deploy Backend to Render (or similar)
1. Push this repository to GitHub.
2. Create a new **Web Service** on Render pointing to your repository.
3. Select **Python** as the runtime.
4. Set the build command: `pip install -r requirements.txt` and start command: `python src/main.py` (or use uvicorn command).
5. Add environment variables:
   - `GROQ_API_KEY`
   - `GEMINI_API_KEY`
   - `FRONTEND_ORIGIN` = (Set this to your deployed frontend Vercel URL to authorize CORS requests).

### B. Deploy Frontend to Vercel (or similar)
1. Deploy the `frontend/` directory as a Vercel project.
2. Configure the build command as `npm run build` and output directory as `dist`.
3. Add the environment variable:
   - `VITE_API_URL` = (Set this to the URL of your deployed Render Web Service, e.g., `https://my-backend-render.com`).
