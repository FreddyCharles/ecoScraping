import os
import logging
import pandas as pd
import numpy as np
from sec_edgar_downloader import Downloader
import requests.exceptions
import argparse
from pathlib import Path

# --- Configuration ---

# Phase 1: Acquisition
COMPANY_IDENTIFIERS_FILE = 'tickers.txt' # File containing Tickers or CIKs, one per line
FILING_TYPE = '10-K'
NUM_RECENT_FILINGS = 3 # Number of recent filings to download
# Optional: Define date range if not using NUM_RECENT_FILINGS (set NUM_RECENT_FILINGS to None)
# START_DATE = "2020-01-01" # e.g., "2020-01-01"
# END_DATE = "2023-12-31"   # e.g., "2023-12-31"
DOWNLOAD_DIR = 'sec_edgar_filings'
# User Agent is correctly set now
USER_AGENT = "Freddy Charles freddycharles04@gmail.com"

# Phase 2: Analysis
INPUT_CSV_PATH = 'input_financials.csv' # Assumed pre-processed CSV
OUTPUT_CSV_PATH = 'output_ratios.csv'
RATIOS_TO_CALCULATE = [
    'CurrentRatio',
    'DebtToEquityRatio',
    'NetProfitMargin'
]
# Required columns in input_financials.csv for the above ratios
REQUIRED_COLUMNS = [
    'CompanyName', 'Ticker', 'Year',
    'TotalCurrentAssets', 'TotalCurrentLiabilities',
    'TotalDebt', 'TotalEquity',
    'Revenue', 'NetIncome'
]

# Shared Configuration
LOG_FILE_PATH = 'acquisition_analysis.log'
LOG_LEVEL = logging.INFO # Set to logging.DEBUG for more detailed logs

# --- Logging Setup ---

def setup_logging():
    """Configures logging to console and file."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    root_logger = logging.getLogger()

    # Prevent duplicate handlers if setup_logging is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(LOG_LEVEL)

    # File Handler
    log_path = Path(LOG_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True) # Ensure log directory exists
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a') # Append mode
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

    logging.info("Logging initialized.")

# --- Phase 1: Data Acquisition ---

def acquire_filings(identifiers, filing_type, num_filings, download_dir, user_agent):
    """Downloads SEC filings for the given identifiers."""
    logging.info("[ACQUISITION] Starting data acquisition phase.")

    if not user_agent or user_agent == "Your Name Your Email":
        # This check should technically not be needed anymore but kept for robustness
        logging.error("[ACQUISITION] User agent (email) is not set. Please configure USER_AGENT in the script.")
        print("ERROR: User agent (email) is not set. Please configure USER_AGENT in the script.")
        return False # Indicate failure

    try:
        # Ensure download directory exists
        os.makedirs(download_dir, exist_ok=True)
        logging.info(f"[ACQUISITION] Download directory set to: {download_dir}")

        # Initialize the downloader
        dl = Downloader(company_name=download_dir, email_address=user_agent) # Correct initialization
        logging.info(f"[ACQUISITION] SEC Edgar Downloader initialized.")
        # Note: User agent is passed during initialization now in recent versions

    except Exception as e:
        logging.error(f"[ACQUISITION] Failed to initialize downloader or create directory: {e}", exc_info=True)
        return False # Indicate failure

    successful_downloads = 0
    failed_downloads = 0
    total_files_downloaded = 0 # Track total files

    for identifier in identifiers:
        identifier = identifier.strip()
        if not identifier:
            continue

        log_message_suffix = f"(limit: {num_filings} filings)"
        # Uncomment below if using date range
        # log_message_suffix = f"(dates: {START_DATE} to {END_DATE})"

        logging.info(f"[ACQUISITION] Attempting to download {filing_type} for {identifier} {log_message_suffix}.")
        try:
            # ================== FIX APPLIED HERE ==================
            # Use 'limit' instead of 'amount'
            # Also, pass download_filings=True explicitly if needed (usually default)
            # Provide date range if NUM_RECENT_FILINGS is None
            # after_date_val = START_DATE if NUM_RECENT_FILINGS is None else None
            # before_date_val = END_DATE if NUM_RECENT_FILINGS is None else None

            count = dl.get(
                filing_type,
                identifier,
                limit=num_filings # Use limit here
                # after=after_date_val, # Uncomment if using date range
                # before=before_date_val # Uncomment if using date range
                # download_filings=True # Usually defaults to True, specify if needed
                )
            # =====================================================

            if count > 0:
                logging.info(f"[ACQUISITION] Successfully downloaded {count} {filing_type} filing(s) for {identifier}.")
                successful_downloads += 1
                total_files_downloaded += count
            else:
                logging.info(f"[ACQUISITION] No {filing_type} filings found for {identifier} in the specified criteria.")
                # Consider if no filings found should count as failure or just 0 success
                # Current logic counts it as neither success nor failure explicitly in the counters

        except requests.exceptions.RequestException as e:
            logging.error(f"[ACQUISITION] Network error downloading for {identifier}: {e}", exc_info=False) # Set exc_info=False for cleaner logs unless debugging network
            failed_downloads += 1
        except ValueError as e:
             # Catch specific errors like invalid ticker/CIK more precisely if possible
             if "Invalid ticker" in str(e) or "Invalid CIK" in str(e):
                 logging.warning(f"[ACQUISITION] Invalid identifier {identifier}: {e}")
             else:
                 logging.error(f"[ACQUISITION] Value error for {identifier}: {e}", exc_info=True)
             failed_downloads += 1
        except Exception as e:
            # Catch other potential exceptions from the library or network stack
             logging.error(f"[ACQUISITION] Failed to download {filing_type} for {identifier}: {e}", exc_info=True)
             failed_downloads += 1
             # Check for rate limiting hints
             if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 429:
                 logging.warning(f"[ACQUISITION] Rate limiting encountered (HTTP 429) for {identifier}.")
             elif "429" in str(e):
                 logging.warning(f"[ACQUISITION] Possible rate limiting encountered for {identifier}.")

    logging.info(f"[ACQUISITION] Acquisition phase completed. Tickers processed: {len(identifiers)}. Successful tickers (>=1 filing): {successful_downloads}. Failed tickers: {failed_downloads}. Total filings downloaded: {total_files_downloaded}.")
    logging.warning("[ACQUISITION] Note: This script only downloads raw filings. Parsing these files into structured data (like input_financials.csv) is a separate step required before Phase 2 analysis.")
    print("\n" + "="*50)
    print(" ACQUISITION PHASE COMPLETE ".center(50, "="))
    print(" Raw filings downloaded to: {}".format(DOWNLOAD_DIR))
    print(" IMPORTANT: You must now PARSE these filings into")
    print(f"            '{INPUT_CSV_PATH}' before running the analysis phase.")
    print("="*50 + "\n")
    # Return True if at least one download attempt didn't fail critically, False otherwise
    # Modify this logic if stricter success definition is needed (e.g., all identifiers must succeed)
    return failed_downloads < len([id for id in identifiers if id]) # Return True if not all failed

# --- Phase 2: Data Processing and Analysis ---

def calculate_ratios(df):
    """Calculates financial ratios for the DataFrame."""
    results = []
    required_numeric_cols = [ # Ensure these are checked before calculation
        'TotalCurrentAssets', 'TotalCurrentLiabilities', 'TotalDebt',
        'TotalEquity', 'Revenue', 'NetIncome'
    ]

    for index, row in df.iterrows():
        ticker = row.get('Ticker', 'N/A')
        year = row.get('Year', 'N/A')
        company_name = row.get('CompanyName', 'N/A')
        row_result = {'CompanyName': company_name, 'Ticker': ticker, 'Year': year}

        # Check if all necessary numeric data is present for this row
        missing_data = False
        for col in required_numeric_cols:
            if pd.isna(row.get(col)):
                # logging.debug(f"[ANALYSIS] DEBUG: Missing numeric input '{col}' for Ticker {ticker}, Year {year}.")
                missing_data = True
                # break # Can break early if one is missing, or check all

        # --- Current Ratio ---
        try:
            if missing_data or pd.isna(row['TotalCurrentAssets']) or pd.isna(row['TotalCurrentLiabilities']):
                 row_result['CurrentRatio'] = np.nan
            elif row['TotalCurrentLiabilities'] == 0:
                logging.warning(f"[ANALYSIS] WARNING: Division by zero calculating Current Ratio for Ticker {ticker}, Year {year} (TotalCurrentLiabilities is zero). Setting to NaN.")
                row_result['CurrentRatio'] = np.nan
            else:
                row_result['CurrentRatio'] = row['TotalCurrentAssets'] / row['TotalCurrentLiabilities']
        except (TypeError, KeyError) as e:
            # KeyError should be less likely due to prior column checks, but keep for safety
            logging.error(f"[ANALYSIS] ERROR: Calculation error (Current Ratio) for Ticker {ticker}, Year {year}: {e}", exc_info=True)
            row_result['CurrentRatio'] = np.nan

        # --- Debt-to-Equity Ratio ---
        try:
            if missing_data or pd.isna(row['TotalDebt']) or pd.isna(row['TotalEquity']):
                 row_result['DebtToEquityRatio'] = np.nan
            elif row['TotalEquity'] == 0:
                logging.warning(f"[ANALYSIS] WARNING: Division by zero calculating Debt-to-Equity Ratio for Ticker {ticker}, Year {year} (TotalEquity is zero). Setting to NaN.")
                row_result['DebtToEquityRatio'] = np.nan
            else:
                row_result['DebtToEquityRatio'] = row['TotalDebt'] / row['TotalEquity']
        except (TypeError, KeyError) as e:
            logging.error(f"[ANALYSIS] ERROR: Calculation error (DebtToEquity Ratio) for Ticker {ticker}, Year {year}: {e}", exc_info=True)
            row_result['DebtToEquityRatio'] = np.nan

        # --- Net Profit Margin ---
        try:
            if missing_data or pd.isna(row['NetIncome']) or pd.isna(row['Revenue']):
                 row_result['NetProfitMargin'] = np.nan
            elif row['Revenue'] == 0:
                 logging.warning(f"[ANALYSIS] WARNING: Division by zero calculating Net Profit Margin for Ticker {ticker}, Year {year} (Revenue is zero). Setting to NaN.")
                 row_result['NetProfitMargin'] = np.nan
            else:
                row_result['NetProfitMargin'] = row['NetIncome'] / row['Revenue']
        except (TypeError, KeyError) as e:
            logging.error(f"[ANALYSIS] ERROR: Calculation error (Net Profit Margin) for Ticker {ticker}, Year {year}: {e}", exc_info=True)
            row_result['NetProfitMargin'] = np.nan

        results.append(row_result)

    return pd.DataFrame(results)


def analyze_financial_data(input_csv, output_csv, required_columns):
    """Loads data, cleans it, calculates ratios, and saves the results."""
    logging.info(f"[ANALYSIS] Starting analysis phase. Reading data from {input_csv}.")

    # --- Data Loading ---
    try:
        df = pd.read_csv(input_csv)
        logging.info(f"[ANALYSIS] Successfully loaded data from {input_csv}. Shape: {df.shape}")
        if df.empty:
            logging.warning(f"[ANALYSIS] Input file {input_csv} is empty. No analysis will be performed.")
            print(f"WARNING: Input file '{input_csv}' is empty. No analysis performed.")
            # Create empty output file? Or just skip? Skipping for now.
            return True # Return success as there's nothing to fail on
    except FileNotFoundError:
        logging.error(f"[ANALYSIS] FATAL: Input file not found at {input_csv}. Please ensure the file exists (it should be generated after parsing the downloaded filings).")
        print(f"ERROR: Input file '{input_csv}' not found. Please create this file from the downloaded raw filings.")
        return False # Indicate failure
    except pd.errors.EmptyDataError:
        # This case is handled by df.empty check above after successful load
        logging.error(f"[ANALYSIS] FATAL: Input file {input_csv} is empty (pd.errors.EmptyDataError).")
        print(f"ERROR: Input file '{input_csv}' is empty.")
        return False # Indicate failure
    except pd.errors.ParserError as e:
        logging.error(f"[ANALYSIS] FATAL: Error parsing {input_csv}: {e}", exc_info=True)
        print(f"ERROR: Could not parse '{input_csv}'. Check its format.")
        return False # Indicate failure
    except Exception as e:
        logging.error(f"[ANALYSIS] FATAL: An unexpected error occurred while loading {input_csv}: {e}", exc_info=True)
        print(f"ERROR: An unexpected error occurred loading '{input_csv}'.")
        return False # Indicate failure

    # --- Data Validation and Cleaning ---
    logging.info("[ANALYSIS] Starting data validation and cleaning.")

    # Check for required columns
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        logging.error(f"[ANALYSIS] FATAL: Input CSV {input_csv} is missing required columns: {missing_cols}. Analysis cannot proceed.")
        print(f"ERROR: Input CSV '{input_csv}' is missing required columns: {missing_cols}.")
        return False # Indicate failure

    # Identify numeric columns needed for calculation
    numeric_cols = [
        'TotalCurrentAssets', 'TotalCurrentLiabilities',
        'TotalDebt', 'TotalEquity',
        'Revenue', 'NetIncome'
    ]

    # Convert columns to numeric, coercing errors to NaN
    for col in numeric_cols:
        if col in df.columns: # Should always be true due to check above, but safe
            # Check if column is already numeric to avoid unnecessary warnings
            if not pd.api.types.is_numeric_dtype(df[col]):
                 original_non_numeric = df[col].apply(lambda x: not isinstance(x, (int, float, np.number)) and pd.notna(x) and x != '') # Check non-numeric, non-NaN, non-empty strings
                 df[col] = pd.to_numeric(df[col], errors='coerce')
                 # Log warnings for rows where coercion happened and the original value was truly non-numeric looking
                 coerced_indices = original_non_numeric & df[col].isna() # Indices where original was non-numeric AND result is NaN
                 for index in df[coerced_indices].index:
                      ticker = df.loc[index].get('Ticker', 'N/A')
                      year = df.loc[index].get('Year', 'N/A')
                      original_value = df.loc[index, col] # Get original value *before* coercion (requires re-reading or storing original) - Simplified logging below
                      logging.warning(f"[ANALYSIS] WARNING: Non-numeric value found in column '{col}' for Ticker {ticker}, Year {year}. Coerced to NaN.")
            # Handle case where column might contain mixed types like strings ('-') representing zero or missing data
            df[col] = df[col].replace({'-': np.nan, '': np.nan}) # Replace common non-numeric markers with NaN
            df[col] = pd.to_numeric(df[col], errors='coerce') # Try coercion again after replacement

        # else: # This case is handled by the missing columns check above


    logging.info("[ANALYSIS] Data validation and cleaning complete.")

    # --- Ratio Calculation ---
    logging.info("[ANALYSIS] Starting ratio calculations.")
    ratios_df = calculate_ratios(df)
    logging.info("[ANALYSIS] Ratio calculations complete.")

    # --- Output Generation ---
    try:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
        ratios_df.to_csv(output_csv, index=False, float_format='%.4f') # Format floats for readability
        logging.info(f"[ANALYSIS] Successfully wrote analysis results to {output_csv}.")
        print(f"Analysis complete. Results saved to '{output_csv}'.")
    except IOError as e:
        logging.error(f"[ANALYSIS] ERROR: Could not write output file to {output_csv}: {e}", exc_info=True)
        print(f"ERROR: Could not write output file to '{output_csv}'. Check permissions.")
        return False # Indicate failure
    except Exception as e:
        logging.error(f"[ANALYSIS] ERROR: An unexpected error occurred while saving results to {output_csv}: {e}", exc_info=True)
        print(f"ERROR: An unexpected error occurred saving results to '{output_csv}'.")
        return False # Indicate failure

    logging.info("[ANALYSIS] Analysis phase finished.")
    return True # Indicate success

# --- Main Execution ---

def main():
    """Main function to orchestrate the acquisition and analysis phases."""
    parser = argparse.ArgumentParser(description="Download SEC filings and perform financial ratio analysis.")
    parser.add_argument('--skip-acquisition', action='store_true', help="Skip the data acquisition phase.")
    parser.add_argument('--skip-analysis', action='store_true', help="Skip the data analysis phase.")
    args = parser.parse_args()

    setup_logging() # Initialize logging first

    acquisition_success = True # Assume success unless skipped or failed explicitly
    if not args.skip_acquisition:
        # --- Run Acquisition Phase ---
        try:
            identifiers_path = Path(COMPANY_IDENTIFIERS_FILE)
            if not identifiers_path.is_file():
                logging.error(f"[ACQUISITION] Company identifiers file not found: {COMPANY_IDENTIFIERS_FILE}")
                print(f"ERROR: Company identifiers file '{COMPANY_IDENTIFIERS_FILE}' not found.")
                acquisition_success = False # Mark as failed
            else:
                with open(identifiers_path, 'r') as f:
                    identifiers = [line.strip() for line in f if line.strip()]
                if not identifiers:
                    logging.error(f"[ACQUISITION] Company identifiers file '{COMPANY_IDENTIFIERS_FILE}' is empty.")
                    print(f"ERROR: Company identifiers file '{COMPANY_IDENTIFIERS_FILE}' is empty.")
                    acquisition_success = False # Mark as failed
                else:
                    acquisition_success = acquire_filings(
                        identifiers=identifiers,
                        filing_type=FILING_TYPE,
                        num_filings=NUM_RECENT_FILINGS,
                        download_dir=DOWNLOAD_DIR,
                        user_agent=USER_AGENT
                        # Pass START_DATE, END_DATE here if using date range logic
                    )
                    if not acquisition_success:
                         logging.warning("[ACQUISITION] Acquisition phase finished with errors for one or more tickers.")
                         # Decide if this constitutes overall failure - current logic allows analysis if *some* succeed

        # Removed FileNotFoundError catch here as it's handled by Path check above
        except Exception as e:
            logging.error(f"[ACQUISITION] An unexpected error occurred during acquisition setup or execution: {e}", exc_info=True)
            acquisition_success = False # Mark as failed
    else:
        logging.info("Skipping data acquisition phase as requested.")
        print("Skipping data acquisition phase.")


    analysis_success = True # Assume success unless skipped or failed explicitly
    # Proceed to analysis only if analysis is not skipped AND
    # (acquisition was skipped OR acquisition phase did not fail critically)
    if not args.skip_analysis:
        # Check if acquisition was successful OR if it was skipped
        # If acquisition failed, do not proceed to analysis unless explicitly skipped
        if acquisition_success or args.skip_acquisition:
            input_csv_path = Path(INPUT_CSV_PATH)
            # Check if input file exists, especially important if acquisition was skipped or failed partially
            if not input_csv_path.is_file():
                 logging.error(f"[ANALYSIS] Input CSV '{INPUT_CSV_PATH}' not found. Cannot run analysis.")
                 print(f"ERROR: Input CSV '{INPUT_CSV_PATH}' not found. Please ensure it exists (run acquisition or create manually after parsing).")
                 analysis_success = False # Mark analysis as failed
            else:
                # --- Run Analysis Phase ---
                analysis_success = analyze_financial_data(
                    input_csv=INPUT_CSV_PATH,
                    output_csv=OUTPUT_CSV_PATH,
                    required_columns=REQUIRED_COLUMNS
                )
        else:
             # This case means acquisition was run and acquisition_success is False
             logging.warning("[ANALYSIS] Skipping analysis phase because the acquisition phase failed.")
             print("Skipping analysis phase due to acquisition failure.")
             analysis_success = False # Mark analysis as failed
    else:
        logging.info("Skipping data analysis phase as requested.")
        print("Skipping data analysis phase.")

    logging.info("Script execution finished.")
    print("\nScript execution finished. Check 'acquisition_analysis.log' for details.")

    # Exit with status code 0 if all run phases were successful, 1 otherwise
    # Check if the phase was run AND failed
    acquisition_phase_failed = not args.skip_acquisition and not acquisition_success
    analysis_phase_failed = not args.skip_analysis and not analysis_success

    if acquisition_phase_failed or analysis_phase_failed:
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    # --- Prerequisite Checks ---
    # User agent check (redundant if required in acquire_filings, but good initial check)
    if USER_AGENT == "Your Name Your Email":
        print("="*60)
        print("! IMPORTANT: Please edit the script and set the USER_AGENT !")
        print("!            variable to your actual email address before running. !")
        print("="*60)
        exit(1) # Force exit if placeholder is still there

    # Create dummy input files if they don't exist for demonstration
    if not os.path.exists(COMPANY_IDENTIFIERS_FILE):
        print(f"Creating dummy '{COMPANY_IDENTIFIERS_FILE}'...")
        with open(COMPANY_IDENTIFIERS_FILE, 'w') as f:
            f.write("AAPL\n")
            f.write("MSFT\n")
            f.write("GOOGL\n")
            f.write("INVALIDTICKER\n") # Example invalid ticker

    if not os.path.exists(INPUT_CSV_PATH):
        print(f"Creating dummy '{INPUT_CSV_PATH}' for demonstration (replace with actual parsed data)...")
        dummy_data = {
            'CompanyName': ['Apple Inc.', 'Microsoft Corp', 'Alphabet Inc.'],
            'Ticker': ['AAPL', 'MSFT', 'GOOGL'],
            'Year': [2023, 2023, 2023],
            'TotalCurrentAssets': [143566, 184259, 159877],
            'TotalCurrentLiabilities': [145308, 103170, 80911],
            'TotalDebt': [111088, 47032, 28507],
            'TotalEquity': [62146, 205308, 278633],
            'Revenue': [383285, 211915, 307394],
            'NetIncome': [96995, 72361, 73795]
        }
        pd.DataFrame(dummy_data).to_csv(INPUT_CSV_PATH, index=False)
        print(f"NOTE: '{INPUT_CSV_PATH}' created with sample data. You MUST replace this")
        print("      with data parsed from the actual downloaded filings for real analysis.")
        print("-" * 60)

    main()