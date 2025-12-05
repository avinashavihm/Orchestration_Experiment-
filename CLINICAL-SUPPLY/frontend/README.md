# Clinical Supply Copilot - React UI

Modern React frontend for the Clinical Supply Copilot application.

## Features

- 🎨 Beautiful, modern UI with gradient design
- 📤 Drag-and-drop file upload interface
- 📊 Interactive results display with filtering and sorting
- 📈 Summary statistics dashboard
- 🔍 Expandable site details with AI analysis
- 📱 Fully responsive design

## Setup

1. Install dependencies:
```bash
npm install
```

2. Make sure the FastAPI backend is running on `http://localhost:8000`

3. Start the development server:
```bash
npm start
```

The app will open at `http://localhost:3000`

## Usage

1. **Upload Files**: Upload all 6 required CSV files (sites, enrollment, dispense, inventory, shipment_logs, waste)
2. **Run Analysis**: Click "Run Analysis" to process the files
3. **View Results**: Browse through the forecasting results with filtering and sorting options
4. **Explore Details**: Click on any site card to see detailed recommendations and AI analysis

## Build for Production

```bash
npm run build
```

This creates an optimized production build in the `build` folder.

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── FileUpload.js       # File upload interface
│   │   ├── ResultsDisplay.js   # Results table with filtering
│   │   ├── SummaryStats.js     # Dashboard statistics
│   │   └── LoadingSpinner.js   # Loading state
│   ├── App.js                  # Main app component
│   ├── App.css                 # App styles
│   ├── index.js                # Entry point
│   └── index.css               # Global styles
└── package.json
```

