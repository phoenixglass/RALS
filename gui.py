#!/usr/bin/env python3
"""
RALS GUI Application - Insurance Rate Calculator

Provides a graphical user interface for processing service appointment data
and calculating client billing based on insurance plan parameters.
"""

import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from decimal import Decimal, InvalidOperation
import traceback

from rals.models import InsurancePlan, Client, RateSchedule
from rals.parser import SpreadsheetParser
from rals.calculator import RateCalculator
from rals.output import generate_billing_report


class RALSApplication:
    """Main GUI application for RALS."""
    
    # UI Constants
    FRAME_PADDING = 15
    BUTTON_PADDING = 20
    WIDGET_PADDING = 5
    
    def __init__(self, root):
        """Initialize the GUI application."""
        self.root = root
        self.root.title("RALS - Rate and Ledger System")
        self.root.geometry("700x550")
        self.root.resizable(True, True)
        
        # Variables
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.deductible = tk.StringVar(value="3272.00")
        self.coinsurance = tk.StringVar(value="0.40")
        self.oop_max = tk.StringVar(value="6500.00")
        self.client_name = tk.StringVar()
        
        # Create UI
        self.create_widgets()
        
    def create_widgets(self):
        """Create and layout all GUI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding=str(self.FRAME_PADDING))
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="RALS Insurance Rate Calculator",
            font=("TkDefaultFont", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Input file section
        row = 1
        ttk.Label(main_frame, text="Input Excel File:").grid(
            row=row, column=0, sticky=tk.W, pady=self.WIDGET_PADDING
        )
        ttk.Entry(
            main_frame, 
            textvariable=self.input_file, 
            width=50
        ).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=self.WIDGET_PADDING, padx=(self.WIDGET_PADDING, self.WIDGET_PADDING))
        ttk.Button(
            main_frame, 
            text="Browse...", 
            command=self.browse_input_file
        ).grid(row=row, column=2, pady=self.WIDGET_PADDING)
        
        # Client name (optional)
        row += 1
        ttk.Label(main_frame, text="Client Name (optional):").grid(
            row=row, column=0, sticky=tk.W, pady=self.WIDGET_PADDING
        )
        ttk.Entry(
            main_frame, 
            textvariable=self.client_name, 
            width=50
        ).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=self.WIDGET_PADDING, padx=(self.WIDGET_PADDING, self.WIDGET_PADDING))
        
        # Separator
        row += 1
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=self.FRAME_PADDING
        )
        
        # Insurance parameters section
        row += 1
        params_label = ttk.Label(
            main_frame, 
            text="Insurance Parameters",
            font=("TkDefaultFont", 11, "bold")
        )
        params_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        # Deductible
        row += 1
        ttk.Label(main_frame, text="Deductible ($):").grid(
            row=row, column=0, sticky=tk.W, pady=self.WIDGET_PADDING
        )
        deductible_entry = ttk.Entry(
            main_frame, 
            textvariable=self.deductible, 
            width=20
        )
        deductible_entry.grid(row=row, column=1, sticky=tk.W, pady=self.WIDGET_PADDING, padx=(self.WIDGET_PADDING, self.WIDGET_PADDING))
        
        # Coinsurance
        row += 1
        ttk.Label(main_frame, text="Coinsurance Rate:").grid(
            row=row, column=0, sticky=tk.W, pady=self.WIDGET_PADDING
        )
        coinsurance_entry = ttk.Entry(
            main_frame, 
            textvariable=self.coinsurance, 
            width=20
        )
        coinsurance_entry.grid(row=row, column=1, sticky=tk.W, pady=self.WIDGET_PADDING, padx=(self.WIDGET_PADDING, self.WIDGET_PADDING))
        ttk.Label(main_frame, text="(e.g., 0.40 = 40%)").grid(
            row=row, column=2, sticky=tk.W, pady=self.WIDGET_PADDING
        )
        
        # OOP Max
        row += 1
        ttk.Label(main_frame, text="Out-of-Pocket Max ($):").grid(
            row=row, column=0, sticky=tk.W, pady=self.WIDGET_PADDING
        )
        oop_entry = ttk.Entry(
            main_frame, 
            textvariable=self.oop_max, 
            width=20
        )
        oop_entry.grid(row=row, column=1, sticky=tk.W, pady=self.WIDGET_PADDING, padx=(self.WIDGET_PADDING, self.WIDGET_PADDING))
        
        # Separator
        row += 1
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=self.FRAME_PADDING
        )
        
        # Output file section
        row += 1
        ttk.Label(main_frame, text="Output Excel File:").grid(
            row=row, column=0, sticky=tk.W, pady=self.WIDGET_PADDING
        )
        ttk.Entry(
            main_frame, 
            textvariable=self.output_file, 
            width=50
        ).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=self.WIDGET_PADDING, padx=(self.WIDGET_PADDING, self.WIDGET_PADDING))
        ttk.Button(
            main_frame, 
            text="Browse...", 
            command=self.browse_output_file
        ).grid(row=row, column=2, pady=self.WIDGET_PADDING)
        
        # Calculate button
        row += 1
        self.calculate_btn = ttk.Button(
            main_frame, 
            text="Calculate Billing", 
            command=self.calculate_billing,
            style="Accent.TButton"
        )
        self.calculate_btn.grid(
            row=row, column=0, columnspan=3, pady=self.BUTTON_PADDING
        )
        
        # Status label
        row += 1
        self.status_label = ttk.Label(
            main_frame, 
            text="Ready to process billing data",
            foreground="gray"
        )
        self.status_label.grid(row=row, column=0, columnspan=3, pady=self.WIDGET_PADDING)
        
        # Progress bar
        row += 1
        self.progress = ttk.Progressbar(
            main_frame, 
            mode='indeterminate',
            length=300
        )
        self.progress.grid(row=row, column=0, columnspan=3, pady=self.WIDGET_PADDING)
        
    def browse_input_file(self):
        """Open file dialog to select input Excel file."""
        filename = filedialog.askopenfilename(
            title="Select Input Excel File",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.input_file.set(filename)
            # Auto-set output file if not already set
            if not self.output_file.get():
                input_path = Path(filename)
                output_filename = input_path.stem + "_billing_summary.xlsx"
                output_path = input_path.parent / output_filename
                self.output_file.set(str(output_path))
    
    def browse_output_file(self):
        """Open file dialog to select output Excel file."""
        filename = filedialog.asksaveasfilename(
            title="Save Billing Summary As",
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.output_file.set(filename)
    
    def validate_inputs(self):
        """Validate all input fields."""
        errors = []
        
        # Check input file
        if not self.input_file.get():
            errors.append("Please select an input Excel file")
        elif not Path(self.input_file.get()).exists():
            errors.append(f"Input file not found: {self.input_file.get()}")
        
        # Check output file
        if not self.output_file.get():
            errors.append("Please specify an output file location")
        
        # Validate deductible
        try:
            ded = Decimal(self.deductible.get())
            if ded < 0:
                errors.append("Deductible must be a positive number")
        except (InvalidOperation, ValueError):
            errors.append(f"Invalid deductible value: {self.deductible.get()}")
        
        # Validate coinsurance
        try:
            coins = Decimal(self.coinsurance.get())
            if coins < 0 or coins > 1:
                errors.append("Coinsurance must be between 0 and 1 (e.g., 0.40 for 40%)")
        except (InvalidOperation, ValueError):
            errors.append(f"Invalid coinsurance value: {self.coinsurance.get()}")
        
        # Validate OOP max
        try:
            oop = Decimal(self.oop_max.get())
            if oop < 0:
                errors.append("Out-of-pocket maximum must be a positive number")
        except (InvalidOperation, ValueError):
            errors.append(f"Invalid OOP maximum value: {self.oop_max.get()}")
        
        return errors
    
    def update_status(self, message, color="black"):
        """Update the status label."""
        self.status_label.config(text=message, foreground=color)
        self.root.update_idletasks()
    
    def calculate_billing(self):
        """Main calculation function - processes the billing data."""
        # Validate inputs
        errors = self.validate_inputs()
        if errors:
            messagebox.showerror(
                "Input Validation Error",
                "Please correct the following errors:\n\n" + "\n".join(f"• {err}" for err in errors)
            )
            return
        
        # Disable button and show progress
        self.calculate_btn.config(state="disabled")
        self.progress.start(10)
        self.update_status("Processing...", "blue")
        
        try:
            # Parse input file
            input_path = Path(self.input_file.get())
            self.update_status(f"Reading input file: {input_path.name}...", "blue")
            
            parser = SpreadsheetParser(start_row=2, end_row=None)
            services = parser.parse_file(input_path)
            
            if not services:
                raise ValueError("No service records found in input file")
            
            self.update_status(f"Found {len(services)} service records", "blue")
            
            # Extract rate schedule
            rate_schedule = parser.extract_rate_schedule(services)
            
            # Create insurance plan
            insurance_plan = InsurancePlan(
                name="Client Insurance",
                deductible=Decimal(self.deductible.get()),
                coinsurance_rate=Decimal(self.coinsurance.get()),
                oop_max=Decimal(self.oop_max.get())
            )
            
            # Create client
            mrn = services[0].mrn
            client_name = self.client_name.get() or f"Client {mrn}"
            client = Client(
                name=client_name,
                mrn=mrn,
                insurance_plan=insurance_plan
            )
            
            # Calculate billing
            self.update_status("Calculating billing...", "blue")
            calculator = RateCalculator(client, rate_schedule)
            billing_items = calculator.calculate_all_services(services)
            
            # Generate output
            output_path = Path(self.output_file.get())
            self.update_status(f"Writing output file: {output_path.name}...", "blue")
            generate_billing_report(billing_items, output_path, include_details=False)
            
            # Calculate totals
            total_charges = sum(item.charge_amount for item in billing_items)
            
            # Success!
            self.progress.stop()
            self.update_status("✓ Billing calculation completed successfully!", "green")
            
            # Show success message with details
            messagebox.showinfo(
                "Success",
                f"Billing calculation completed!\n\n"
                f"Services processed: {len(services)}\n"
                f"Billable items: {len(billing_items)}\n"
                f"Total patient responsibility: ${total_charges:,.2f}\n\n"
                f"Output saved to:\n{output_path}"
            )
            
        except Exception as e:
            self.progress.stop()
            self.update_status("✗ Error occurred during processing", "red")
            
            # Show detailed error message
            error_msg = str(e)
            if not error_msg:
                error_msg = "An unknown error occurred"
            
            # Include traceback for debugging
            tb = traceback.format_exc()
            print(f"Error during calculation:\n{tb}", file=sys.stderr)
            
            messagebox.showerror(
                "Calculation Error",
                f"An error occurred during processing:\n\n{error_msg}\n\n"
                f"Please check your input file and parameters."
            )
        
        finally:
            # Re-enable button
            self.calculate_btn.config(state="normal")
            self.progress.stop()


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    
    # Note: To add an icon, place an .ico file (Windows) or .icns file (macOS)
    # in the same directory and use: root.iconbitmap('icon.ico')
    
    app = RALSApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
