# Clinical Supply Copilot

A Python backend system for clinical supply forecasting that loads user-uploaded CSV files, computes supply forecasts, generates resupply recommendations, and uses Gemini 2.0 Flash for structured reasoning and natural language justification. All operations are logged to AgentOps.

## Features

- **Multiple Upload Methods**:
  - Modern React web UI with drag-and-drop file upload
  - Local folder upload (place CSV files in `/data`)
  - FastAPI REST endpoint (`POST /upload-and-run`)
  
- **Intelligent Forecasting**:
  - Feature engineering (30-day demand projection, urgency scores, expiry tracking)
  - Rules-based resupply recommendations
  - LLM-powered justification using Gemini 2.0 Flash
  
- **Observability**:
  - Complete logging and tracing with AgentOps
  - Performance metrics and error tracking

## Project Structure

```
clin-supply-copilot/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── upload_handler.py         # CSV upload utilities
│   ├── data_loader.py            # Data loading
│   ├── features.py               # Feature engineering
│   ├── rules_engine.py           # Resupply recommendation rules
│   ├── gemini_client.py          # Gemini 2.0 Flash client
│   ├── agentops_instrumentation.py  # AgentOps integration
│   ├── orchestrator.py           # Main pipeline orchestrator
│   ├── api.py                    # FastAPI endpoints
│   ├── waste_analyzer.py          # Waste pattern analysis
│   ├── temp_excursion_handler.py  # Temperature excursion handling
│   ├── depot_optimizer.py        # Depot optimization
│   └── enrollment_predictor.py   # Enrollment prediction
├── tests/
│   ├── test_features.py
│   └── test_rules.py
├── frontend/                     # React frontend application
├── data/                         # Default data directory for CSV files
├── tests/                        # Unit tests
├── Dockerfile                    # Backend Docker configuration
├── docker-compose.yaml           # Docker Compose configuration
├── requirements.txt              # Python dependencies
├── README.md                     # This file
└── .env.example                  # Environment variables template
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with your API keys. You can use the example template:

```bash
# If .env.example exists, copy it
cp .env.example .env

# Or create a new .env file
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key
AGENTOPS_API_KEY=your_agentops_api_key
DATA_DIR=./data
EOF
```

Edit `.env` and fill in your actual API keys:
```
GEMINI_API_KEY=your_gemini_api_key
AGENTOPS_API_KEY=your_agentops_api_key
GEMINI_API_KEY_1=optional_secondary_key
GEMINI_API_KEY_2=optional_tertiary_key
GEMINI_API_KEY_3=optional_quaternary_key
DATA_DIR=./data
GEMINI_MODEL=gemini-2.0-flash
```

### 3. Prepare Data Directory

Create the data directory and place your CSV files:

```bash
mkdir -p data
# Place CSV files: sites.csv, enrollment.csv, dispense.csv, inventory.csv, shipment_logs.csv, waste.csv
```

## Usage

### Option 1: FastAPI Server

Start the FastAPI server:

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Upload files via API:

```bash
curl -X POST "http://localhost:8000/upload-and-run" \
  -F "sites=@sites.csv" \
  -F "enrollment=@enrollment.csv" \
  -F "dispense=@dispense.csv" \
  -F "inventory=@inventory.csv" \
  -F "shipment=@shipment_logs.csv" \
  -F "waste=@waste.csv"
```

Or use default data directory:

```bash
curl -X POST "http://localhost:8000/run-default"
```

### Option 2: React UI (Recommended)

Start the React frontend:

```bash
cd frontend
npm install
npm start
```

Make sure the FastAPI backend is running on `http://localhost:8000`:

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Then open your browser to `http://localhost:3000` and upload your CSV files through the beautiful web interface.

### Option 3: Local Folder

Place your CSV files in the `./data` directory and use the API endpoint `/run-default` or the React UI "Use Default Data" button.

## Required CSV Files

The system expects exactly 6 CSV files with the following names and required columns:

| File | Required Columns |
|------|-----------------|
| `sites.csv` | `site_id`, `site_name`, `region` |
| `enrollment.csv` | `site_id`, `enrollment_date`, `subject_count` |
| `dispense.csv` | `site_id`, `dispense_date`, `kits_dispensed` |
| `inventory.csv` | `site_id`, `current_inventory`, `expiry_date` |
| `shipment_logs.csv` | `site_id`, `shipment_date`, `quantity_shipped` |
| `waste.csv` | `site_id`, `waste_date`, `quantity_wasted` |

## Output Format

The system returns a JSON response with:

```json
{
  "results": [
    {
      "site_id": "...",
      "site_name": "...",
      "region": "...",
      "projected_30d_demand": 100,
      "current_inventory": 50,
      "weekly_dispense_kits": 23.33,
      "days_to_expiry": 45,
      "urgency_score": 2.0,
      "action": "resupply",
      "quantity": 70,
      "reason": "Projected 30-day demand (100) exceeds current inventory...",
      "llm": {
        "structured_result": {
          "action": "resupply",
          "quantity": 70,
          "confidence": 0.95,
          "reasons": ["High projected demand", "Low inventory levels"]
        },
        "draft_message": "Two-paragraph justification..."
      },
      "latency_ms": 1234.56
    }
  ],
  "summary": {
    "total_sites": 10,
    "sites_needing_resupply": 5,
    "total_quantity": 350,
    "avg_projected_demand": 95.5,
    "avg_latency_ms": 1150.2
  },
  "session_id": "20240101_120000",
  "output_path": "/tmp/uploads/session_id/results.jsonl"
}
```

## Docker

### Option 1: Docker Compose (Recommended)

The easiest way to run the entire application (backend + frontend) is using Docker Compose:

```bash
# Create .env file with your API keys
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key
AGENTOPS_API_KEY=your_agentops_api_key
GEMINI_API_KEY_1=optional_secondary_key
GEMINI_API_KEY_2=optional_tertiary_key
GEMINI_API_KEY_3=optional_quaternary_key
DATA_DIR=/app/data
EOF

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

This will start:
- **Backend API** on `http://localhost:8000`
- **React Frontend** on `http://localhost:3000`

Access the React UI at `http://localhost:3000` in your browser.

### Docker Environment Variables

The following environment variables can be set:

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Primary Gemini API key | Yes* |
| `GEMINI_API_KEY_1` | Secondary Gemini API key (for load balancing) | No |
| `GEMINI_API_KEY_2` | Tertiary Gemini API key | No |
| `GEMINI_API_KEY_3` | Quaternary Gemini API key | No |
| `AGENTOPS_API_KEY` | AgentOps API key for observability | Yes |
| `DATA_DIR` | Data directory path (default: `/app/data`) | No |
| `GEMINI_MODEL` | Gemini model to use (default: `gemini-2.0-flash`) | No |

*At least one `GEMINI_API_KEY` must be set (primary or numbered keys).

## Configuration

Key configuration options in `app/config.py`:

- `MIN_ORDER_QUANTITY`: Minimum resupply quantity (default: 10)
- `SAFETY_STOCK_MULTIPLIER`: Safety stock multiplier (default: 1.2)
- `EXPIRY_THRESHOLD_DAYS`: Days before expiry to trigger resupply (default: 30)


