# Patient Recruitment Eligibility System

A comprehensive system for evaluating patient eligibility for clinical trials and ranking clinical trial sites based on eligible patient pools and site performance metrics.

## Features

- **AI-Powered Eligibility Evaluation**: Uses Google Gemini AI to extract eligibility criteria from protocol PDFs and evaluate patient eligibility
- **Batch Processing**: Processes patients in batches for efficient evaluation
- **Site Ranking**: Computes site rankings based on eligible patient pools and site performance factors
- **Modern Web Interface**: React-based frontend with drag-and-drop file uploads
- **Excel Output**: Generates comprehensive Excel reports with multiple sheets

## Architecture

### Backend (FastAPI)
- **API Endpoint**: `/run` - Accepts 4 files and returns Excel results
- **Pipeline**: Processes files through eligibility evaluation and site ranking
- **AI Integration**: Google Gemini for criteria extraction and eligibility evaluation

### Frontend (React + Vite)
- **Modern UI**: Built with React, Tailwind CSS, and Vite
- **File Upload**: Drag-and-drop interface for 4 required files
- **Real-time Progress**: Visual progress tracking during processing
- **Results Display**: Summary statistics and downloadable results

## Quick Start

### Backend Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   # or
   uv sync
   ```

2. **Configure environment variables:**
   Create a `.env` file:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   AGENTOPS_API_KEY=your_agentops_key  # optional
   ```

3. **Start the backend server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

4. **Open your browser:**
   Navigate to `http://localhost:3000`

## Input Files

The system requires 4 input files:

1. **Protocol PDF** - Clinical trial protocol document (criteria extracted from pages 38-41)
2. **Patients.xlsx** - Patient data with required columns:
   - Patient_ID, Age, Weight_kg, T_cruzi_Diagnosis
   - Informed_Consent_Signed, Lives_in_Vector_Free_Area
   - Chronic_Chagas_Symptoms, Previous_Chagas_Treatment
   - History_of_Azole_Hypersensitivity, Concomitant_CYP3A4_Meds
3. **Patient↔Site mapping.xlsx** - Maps patients to sites (requires Patient_ID and Site_ID)
4. **Site history.xlsx** - Site performance history (requires siteId, status, screeningFailureRate)

## Output

The system generates an Excel file with 4 sheets:

1. **Site Ranking** - Ranked sites by enrollment probability
2. **Eligible Patients Roster** - Patients marked as eligible
3. **All Patients Roster** - Complete patient list with eligibility status
4. **Extracted Criteria** - Eligibility criteria extracted from protocol

## Project Structure

```
Patient-Recruitment/
├── app/                    # Backend application
│   ├── agents/            # AI agents for eligibility evaluation
│   ├── routers/           # API routes
│   ├── services/          # Business logic services
│   ├── utils/             # Utility functions
│   └── main.py            # FastAPI application
├── frontend/              # React frontend
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── services/     # API services
│   │   └── App.jsx        # Main app component
│   └── package.json
├── Data/                  # Sample data files
└── requirements.txt       # Python dependencies
```

## API Endpoints

### POST `/run`
Upload 4 files and receive Excel results.

**Request:**
- `protocol_pdf`: PDF file
- `patients_xlsx`: Excel file
- `mapping_xlsx`: Excel file
- `site_history_xlsx`: Excel file

**Response:**
- Excel file with 4 sheets
- Metadata in `X-Metadata` header (JSON)

### GET `/health`
Check server health status.

## Technologies

### Backend
- FastAPI - Web framework
- Google Generative AI - AI model for eligibility evaluation
- Pandas - Data processing
- OpenPyXL - Excel file handling
- PyPDF2 - PDF processing

### Frontend
- React 18 - UI library
- Vite - Build tool
- Tailwind CSS - Styling
- Axios - HTTP client
- Lucide React - Icons

## Configuration

Key configuration options in `app/config.py`:

- `BATCH_SIZE`: Number of patients processed per batch (default: 25)
- `GEMINI_MODEL`: AI model to use (default: gemini-2.5-flash)
- `DEFAULT_SITE_PERF_FACTOR`: Default site performance factor (default: 0.50)

## Development

### Running Tests
```bash
# Backend tests (if available)
pytest

# Frontend tests (if available)
cd frontend && npm test
```

### Building for Production

**Backend:**
```bash
# No build step needed, just deploy with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm run build
# Serve the dist/ directory
```

