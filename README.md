# Truely - AI Fact-Checking System

An AI-powered fact-checking system with Chrome extension that analyzes text selections and provides contextual verification using a knowledge base of processed documents.

## What It Does

- **Chrome Extension**: Select any text on any webpage to get instant fact-checking
- **Document Processing**: Upload and process documents (PDF, DOCX, TXT, CSV) into a searchable knowledge base
- **AI Analysis**: Uses RAG (Retrieval-Augmented Generation) with OpenAI for intelligent fact verification
- **Web Interface**: Easy document management through browser interface

## Quick Deploy (2 Minutes)

### Prerequisites
- Docker installed on your machine
- Chrome browser

### Step 1: Deploy Backend
```bash
git clone https://github.com/wanchaiS/Truely-Govhack.git
cd Truely-Govhack/backend

# Configure OpenAI API key (required)

cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=your_key_here

docker compose up -d
```

### Step 2: Install Chrome Extension
1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right toggle)
3. Click "Load unpacked"
4. Select the `Truely` folder (root directory, not backend)
5. The extension should appear with "Truely - AI Fact Checker" name

### Step 3: Verify Everything Works
1. Check backend health: http://localhost:8877/health
2. Check database stats: http://localhost:8877/stats
3. Select text on any webpage - you should see fact-checking buttons appear

## How to Use

### Upload Documents to Knowledge Base
1. Open your browser and go to: **http://localhost:8877**
2. Use the **Document Management** page to:
   - Upload new documents (PDF, DOCX, TXT, CSV)
   - View existing documents
   - Delete unwanted files
   - Monitor database statistics

### Using the Chrome Extension
1. **Select text** on any webpage
2. **Click "Fact Check"** button that appears
3. **See results** in the popup with:
   - Verification status (SUPPORTED/CONTRADICTED/INSUFFICIENT/MIXED)
   - Source references from your knowledge base
   - AI-powered analysis

## How It Works

**System Architecture:**
- **Chrome Extension** detects text selection and sends queries
- **Flask Backend** processes documents and provides fact-checking API  
- **ChromaDB Vector Database** stores document embeddings for semantic search
- **OpenAI Integration** provides AI-powered analysis and verification

**Data Flow:**
1. Upload documents through web interface → Text extraction → Vector embeddings → Database storage
2. Select text on webpage → Extension queries database → AI analyzes context → Results displayed

