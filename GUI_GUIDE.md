# RALS GUI Application - User Guide

## Overview
The RALS GUI provides a user-friendly interface for calculating insurance billing without requiring command-line knowledge.

## GUI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  RALS - Rate and Ledger System v1.0.0                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│         RALS Insurance Rate Calculator                       │
│                                                              │
│  Input Excel File:  [___________________________] [Browse]  │
│  Client Name:       [___________________________]            │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Insurance Parameters                                        │
│                                                              │
│  Deductible ($):         [3272.00___]                       │
│  Coinsurance Rate:       [0.40______]  (e.g., 0.40 = 40%)  │
│  Out-of-Pocket Max ($):  [6500.00___]                       │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Output Excel File: [___________________________] [Browse]  │
│                                                              │
│                  [ Calculate Billing ]                       │
│                                                              │
│  Status: Ready to process billing data                       │
│  [================================]  (Progress Bar)          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Usage Steps

### 1. Select Input File
Click the **Browse** button next to "Input Excel File" and select your spreadsheet containing service appointment data.

### 2. Enter Client Name (Optional)
If desired, enter a client name. Otherwise, it will default to "Client [MRN]".

### 3. Configure Insurance Parameters
Adjust the insurance parameters if needed:
- **Deductible**: Annual deductible amount (default: $3,272.00)
- **Coinsurance Rate**: Patient responsibility after deductible (default: 0.40 = 40%)
- **Out-of-Pocket Max**: Maximum out-of-pocket amount (default: $6,500.00)

### 4. Choose Output Location
Click the **Browse** button next to "Output Excel File" to select where to save the billing summary.

Note: The output file path is automatically suggested based on your input file name.

### 5. Calculate
Click the **Calculate Billing** button to process the data.

The progress bar will animate while processing, and the status message will update with the current operation.

### 6. Results
Upon successful completion, a dialog box will appear with:
- Number of services processed
- Number of billable items
- Total patient responsibility
- Output file location

The status message will show: "✓ Billing calculation completed successfully!"

## Error Handling

The GUI validates all inputs before processing and displays clear error messages for:
- Missing input file
- Invalid file paths
- Invalid numeric values (deductible, coinsurance, OOP max)
- File format errors
- Processing errors

All error messages are displayed in user-friendly dialog boxes with specific guidance on how to fix the issue.

## Features

### Auto-Complete
When you select an input file, the output file path is automatically suggested with the suffix "_billing_summary.xlsx".

### Real-Time Feedback
- Progress bar shows when processing is in progress
- Status messages keep you informed of each step
- Color-coded status (gray=ready, blue=processing, green=success, red=error)

### Input Validation
All fields are validated before processing:
- File paths must exist or be valid
- Numeric fields must contain valid decimal numbers
- Coinsurance must be between 0 and 1

## Tips

1. **Default Values**: The default insurance parameters match common plan configurations. Only change them if needed.

2. **File Formats**: Input files must be Excel format (.xlsx or .xls)

3. **Output Overwriting**: If the output file already exists, it will be overwritten without warning.

4. **Error Messages**: Read error messages carefully - they provide specific information about what went wrong.

5. **Large Files**: For very large spreadsheets, processing may take a few moments. Watch the progress bar.

## Keyboard Shortcuts

- **Tab**: Move between fields
- **Enter**: (when on Calculate button) Start processing
- **Escape**: Close error/success dialogs

## System Requirements

- **Windows**: Windows 10 or later
- **macOS**: macOS 10.13 (High Sierra) or later  
- **Linux**: Most modern distributions with GTK support

No Python installation required when using the standalone executable!
