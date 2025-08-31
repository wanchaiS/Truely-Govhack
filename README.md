# Truely - AI Fact-Checking System

An AI-powered fact-checking system with Chrome extension that analyzes text selections and provides contextual verification using a knowledge base of processed documents.

## What It Does

- **Chrome Extension**: Select any text on any webpage to get instant fact-checking
- **Document Processing**: Upload and process documents (PDF, DOCX, TXT, CSV) into a searchable knowledge base
- **AI Analysis**: Uses RAG (Retrieval-Augmented Generation) with OpenAI for intelligent fact verification
- **Web Interface**: Easy document management through browser interface

### Prerequisites
- Docker installed on your machine
- Chrome browser
- OpenAI API key


##  Step-by-Step Setup

### Step 1: Deploy Backend

**1.1 Clone the repository:**
```bash
git clone https://github.com/wanchaiS/Truely-Govhack.git
```

**1.2 Navigate to backend directory:**
```bash
cd Truely-Govhack/backend
```

**1.3 Configure OpenAI API key:**

```bash
cp .env.example .env
```

Replace `your_openai_key_here` with your actual OpenAI API key, or use this one-liner:
```bash
echo "OPENAI_API_KEY=your_actual_key_here" > .env
```

**1.4 Build and start the system:**
```bash
docker compose up -d --build
```

### Step 2: Install Chrome Extension
1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right toggle)
3. Click "Load unpacked"
4. Select the `Truely` folder (root directory, not backend)
5. The extension should appear with "Truely - AI Fact Checker" name

### Step 3: Verify Everything Works

**3.1 Check backend health:**
```bash
curl http://localhost/api/health
```
Or visit: http://localhost/api/health

**3.2 Check database stats:**
```bash
curl http://localhost/api/stats
```
Or visit: http://localhost/api/stats

**3.3 Open document management interface:**
Visit: http://localhost/manage

**3.4 Test the Chrome extension:**
Select any text on a webpage - you should see the "Fact Check" button appear!

## How It Works

**System Architecture:**
- **Chrome Extension** detects text selection and sends queries
- **Flask Backend** processes documents and provides fact-checking API  
- **ChromaDB Vector Database** stores document embeddings for semantic search
- **OpenAI Integration** provides AI-powered analysis and verification

**Data Flow:**
1. Upload documents through web interface → Text extraction → Vector embeddings → Database storage
2. Select text on webpage → Extension queries database → AI analyzes context → Results displayed
