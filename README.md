# RALS - Rate and Ledger System

Insurance rate calculator that processes service appointment data and calculates client billing based on insurance plan parameters including deductibles, coinsurance, and out-of-pocket maximums.

## Features

- Parses service appointment data from spreadsheet rows
- Extracts rates from PPS Comment field
- Tracks deductible accumulation across services
- Applies coinsurance after deductible is met
- Stops charges when OOP maximum is reached
- Generates billing summary with running totals
- **Web Application** - accessible online via Streamlit Community Cloud
- **GUI Application** for easy use without command line
- **Standalone Executable** - no Python installation required

## For End Users - Using the Web Application

### Quick Start (Easiest Option)

The easiest way to use RALS is through the web application - no installation required!

**🌐 Access the app**: [RALS Web App](https://rals.streamlit.app) *(Coming soon)*

1. **Upload your Excel file** containing service appointment data
2. **Enter client name** (optional)
3. **Configure insurance parameters**:
   - Deductible (default: $3,272.00)
   - Coinsurance rate (default: 0.40 = 40%)
   - Out-of-pocket maximum (default: $6,500.00)
4. **Click "Calculate Billing"** to process the data
5. **Download the billing summary** Excel file

### Features

- No installation required - works in your web browser
- Secure file processing (files are not stored)
- Same calculation engine as the desktop application
- Mobile-friendly interface
- Instant results with summary statistics

## For End Users - Using the Executable

### Quick Start

1. **Download the executable** for your operating system:
   - Windows: `RALS.exe`
   - macOS: `RALS.app`
   - Linux: `RALS`

2. **Double-click** the executable to launch the GUI application

3. **Select your input file** (Excel spreadsheet with service data)

4. **Configure insurance parameters**:
   - Deductible (default: $3,272.00)
   - Coinsurance rate (default: 0.40 = 40%)
   - Out-of-pocket maximum (default: $6,500.00)

5. **Choose output location** for the billing summary

6. **Click "Calculate Billing"** to process the data

7. The application will generate an Excel file with detailed billing information

### System Requirements

- **Windows**: Windows 10 or later
- **macOS**: macOS 10.13 (High Sierra) or later
- **Linux**: Most modern distributions with GTK support

### Troubleshooting

**Windows: "Windows protected your PC" message**
- Click "More info" and then "Run anyway"
- This appears because the executable is not digitally signed

**macOS: "Cannot be opened because it is from an unidentified developer"**
- Right-click the app and select "Open"
- Or go to System Preferences > Security & Privacy and allow the app

**Linux: Permission denied**
- Make the file executable: `chmod +x RALS`

**File format errors**
- Ensure your input file is a valid Excel (.xlsx or .xls) file
- Check that the file contains service data in the expected format

## For Developers

### Installation

```bash
# Clone the repository
git clone https://github.com/phoenixglass/RALS.git
cd RALS

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For Streamlit web app (optional):
pip install -r requirements-streamlit.txt

# For building executables, also install:
pip install pyinstaller
```

### Command-Line Usage

```bash
# Process a spreadsheet
python -m rals.cli input.xlsx --output billing_summary.xlsx

# With custom insurance parameters
python -m rals.cli input.xlsx --deductible 3272 --coinsurance 0.20 --oop-max 6500

# Show detailed calculation breakdown
python -m rals.cli input.xlsx --output billing.xlsx --details

# Specify client name
python -m rals.cli input.xlsx --client-name "John Doe"
```

### GUI Application

Run the GUI application during development:

```bash
python gui.py
```

### Streamlit Web Application

Run the Streamlit web application locally:

```bash
streamlit run streamlit_app.py
```

The application will open in your default web browser at `http://localhost:8501`.

#### Deploying to Streamlit Community Cloud

1. **Fork the repository** on GitHub
2. **Sign up** for [Streamlit Community Cloud](https://streamlit.io/cloud)
3. **Connect your GitHub account** to Streamlit Cloud
4. **Create a new app** and select your forked repository
5. **Set the main file path** to `streamlit_app.py`
6. **Deploy** - your app will be live at `https://[your-app-name].streamlit.app`

**Deployment Notes**:
- Streamlit Cloud uses `requirements.txt` or `requirements-streamlit.txt` automatically
- No additional configuration needed
- The app updates automatically when you push to your repository
- Free tier includes sufficient resources for typical usage
```

### Building the Executable

#### Automated Build

Use the provided build scripts:

**Windows:**
```bash
build.bat
```

**Linux/macOS:**
```bash
./build.sh
# or
python build_exe.py
```

All build scripts will:
1. Check for required dependencies
2. Clean previous build artifacts
3. Build the executable using PyInstaller
4. Output the executable to the `dist/` directory

#### Manual Build

If you prefer to build manually:

```bash
# Install PyInstaller if not already installed
pip install pyinstaller

# Clean previous builds
pyinstaller rals.spec --clean

# The executable will be in dist/
```

#### Platform-Specific Notes

**Windows**:
- Executable: `dist/RALS.exe`
- Can be distributed as a single file
- Optional: Add an `icon.ico` file to set a custom icon

**macOS**:
- Application bundle: `dist/RALS.app`
- Optional: Add an `icon.icns` file to set a custom icon
- For distribution, consider code signing

**Linux**:
- Executable: `dist/RALS`
- Make sure it's executable: `chmod +x dist/RALS`
- Test on target distribution before distributing

### Testing

Run the test suite:

```bash
python -m unittest discover tests
```

### Project Structure

```
RALS/
├── rals/              # Core package
│   ├── __init__.py    # Package initialization
│   ├── cli.py         # Command-line interface
│   ├── calculator.py  # Billing calculation engine
│   ├── models.py      # Data models
│   ├── parser.py      # Excel file parser
│   └── output.py      # Report generation
├── tests/             # Test suite
├── gui.py             # GUI application
├── build_exe.py       # Build automation script
├── rals.spec          # PyInstaller configuration
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests to ensure everything works
5. Submit a pull request

### Development Tips

- The GUI uses the existing `rals` module functions
- Keep the CLI functionality intact when modifying core code
- Test both GUI and CLI after making changes
- Update `rals.spec` if adding new dependencies
- Rebuild the executable after code changes

### License

See LICENSE file for details.
