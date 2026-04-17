# Supermarket Analysis System

A comprehensive Streamlit application suite for analyzing both refrigeration cabinet temperature data and energy consumption data.

## 🚀 Quick Start

### Refrigeration Cabinet Analysis
```bash
streamlit run refrigeration_dashboard/app.py
```

### Energy Monitoring Dashboard
```bash
streamlit run energy_dashboard/app.py
```

**Login Credentials:**
- Username: `energy`
- Password: `energy`

Then open http://localhost:8501 in your browser.

## 📁 Project Structure

```
analysis/
├── refrigeration_dashboard/        # Refrigeration cabinet analysis (separate app)
│   ├── app.py                      # Main entry point
│   ├── app_cobh_analysis.py        # Original single-file app (PDF functions)
│   └── pages/
│       ├── 01_📊_Overview.py       # Temperature distribution & daily stats
│       ├── 02_🔄_Cooling_Cycles.py # Compressor cycle analysis
│       ├── 03_❄️_Defrost_Cycles.py # Defrost event detection
│       ├── 04_📈_Temperature_Trends.py  # Time-series visualization
│       ├── 05_🎯_Time_in_Range.py   # Food safety compliance
│       ├── 06_🏥_Health_Score.py    # Predictive maintenance
│       ├── 07_🔍_Multi_Cabinet_Comparison.py  # Fleet analysis
│       └── 08_📄_PDF_Reports.py     # Report generation
├── energy_dashboard/               # Energy monitoring (separate app)
│   └── app.py                      # Energy dashboard main entry
└── utils/                          # Shared utilities
    ├── __init__.py
    ├── calculations.py             # Temperature analysis functions
    ├── dynamodb.py                 # DynamoDB integration for energy data
    └── refrigeration.py            # Refrigeration API integration
```

## 📊 Refrigeration Cabinet Analysis Pages

1. **Overview** - Temperature distribution & daily statistics
2. **Cooling Cycles** - Compressor on/off cycle analysis  
3. **Defrost Cycles** - Defrost event detection & recovery
4. **Temperature Trends** - Time-series visualization
5. **Time-in-Range** - Food safety compliance
6. **Health Score** - Predictive maintenance
7. **Multi-Cabinet** - Fleet comparison
8. **PDF Reports** - Generate comprehensive reports

## ⚡ Energy Monitoring Dashboard

Standalone application for monitoring electrical energy consumption from Rayleigh RIF 300 energy meters via Modbus.

**🔒 Authentication**: Protected with login (username: `energy`, password: `energy`)

**Data Source**: DynamoDB table `energy_dev` containing Modbus register data

**Key Features**:
- Real-time energy consumption tracking (kW, kVA, kVAr)
- Power factor monitoring and compliance
- Peak demand analysis vs MIC (Maximum Import Capacity)
- Demand penalty risk alerts
- Hourly load heatmaps
- Historical data visualization

**Tabs**:
1. **Energy Overview** - Power consumption timeline with MIC warnings + Daily summary table
2. **Power Factor** - PF trends and distribution analysis
3. **Peak Demand** - Hourly demand patterns and MIC compliance
4. **Load Heatmap** - Daily/hourly consumption patterns
5. **Efficiency Score** - Daily efficiency heatmap with kWh consumption
6. **Load Forecasting** 🆕 - 7-day ahead predictions using ML (Holt-Winters)
7. **Anomaly Detection** 🆕 - Automatic detection of unusual consumption patterns
8. **Raw Data** - View and export processed data

### 🆕 Advanced Analytics Features

**Load Forecasting:**
- Uses Exponential Smoothing (Holt-Winters) algorithm
- Predicts power consumption 7 days ahead (168 hours)
- Shows 95% confidence intervals
- Highlights predicted demand threshold violations
- Daily breakdown with peak/average/total consumption
- Compares forecast to historical patterns

**Anomaly Detection:**
- Two methods available:
  - Isolation Forest (Machine Learning)
  - Z-Score (Statistical)
- Identifies unusual consumption patterns
- Pattern analysis by hour and day of week
- Detects equipment running at abnormal times
- Exportable anomaly reports
- Visual highlighting of anomalies in time series

## 🔧 Configuration

Create a `.env` file with the following:

```env
# Refrigeration API (for cabinet data)
REFRIGERATION_API_HOST=https://live.refrigeration.sensormatic.com
REFRIGERATION_READINGS_API_HOST=https://api.live.refrigeration.sensormatic.com
REFRIGERATION_API_TOKEN=your_token_here

# AWS DynamoDB (for energy data)
AWS_REGION=eu-west-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
DYNAMODB_TABLE_ENERGY=energy
DYNAMODB_TABLE_ENERGY_DEV=energy_dev
```


## Testing
Install act to test github worlflow locally

    brew install act

### Basic Commands

#### List all workflows and jobs
    
`act --list`
    
#### Run all jobs for push event (what we're doing now)

`act push`
    
#### Run all jobs for pull_request event
    act pull_request

#### Run all jobs (both push and pull_request)
    act
    
### Run Specific Jobs

#### Run only formatting and linting
    act -j formatting-and-linting

#### Run only type checking
    act -j type-checking

#### Run only security checks
    act -j security-check
    
    Useful Options

#### Dry run (show what would run without actually running)
    act --dryrun

#### Run with verbose output
    act -v

#### Specify container architecture (for M-series Mac)
    act --container-architecture linux/amd64

#### Run a specific workflow file
    act -W .github/workflows/code-quality.yml

#### Skip specific jobs
    act --job formatting-and-linting

#### Reuse containers (faster for multiple runs)
    act --reuse
    
    Clean Up
    
#### List running act containers
    docker ps -a | grep act
    
#### Stop and remove act containers
    docker ps -a | grep act | awk '{print $1}' | xargs docker rm -f
    
                                                        