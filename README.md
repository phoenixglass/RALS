# RALS - Rate and Ledger System

Insurance rate calculator that processes service appointment data and calculates client billing based on insurance plan parameters including deductibles, coinsurance, and out-of-pocket maximums.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Process a spreadsheet
python -m rals.cli input.xlsx --output billing_summary.xlsx

# With custom insurance parameters
python -m rals.cli input.xlsx --deductible 3272 --coinsurance 0.20 --oop-max 6500
```

## Features

- Parses service appointment data from spreadsheet rows
- Extracts rates from PPS Comment field
- Tracks deductible accumulation across services
- Applies coinsurance after deductible is met
- Stops charges when OOP maximum is reached
- Generates billing summary with running totals
