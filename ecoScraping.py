import requests
from bs4 import BeautifulSoup
import csv
import os
import argparse
import sys
import logging
from urllib.parse import urlparse
from socket import timeout
import re

# Constants for file paths and data directory
DATA_DIR = "economic_data"
os.makedirs(DATA_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(DATA_DIR, "scraper.log")),
    ],
)
logger = logging.getLogger(__name__)

# List of UK companies and their URLs (example - you'll need to fill this with real data)
UK_COMPANIES = {
    "Company1": "https://example.com/company1-financials",  # Replace with actual URLs
    "Company2": "https://example.com/company2-financials",
    "Company3": "https://example.com/company3-financials",
    # Add more companies and URLs here...
}


def scrape_and_store_data(url, company_name):
    """
    Scrapes economic data from a given URL and stores it in a CSV file.

    Args:
        url (str): The URL to scrape.
        company_name (str): The name of the company.

    Returns:
        bool: True on success, False on failure.
    """
    filename = os.path.join(DATA_DIR, f"{company_name}_economic_data.csv")
    headers = ["Metric", "Value", "Source URL"]
    file_exists = os.path.isfile(filename)

    try:
        logger.info(f"Fetching data from {url} for {company_name}...")
        # Check URL validity
        if not is_valid_url(url):
            logger.error(f"Invalid URL: {url}")
            return False

        try:
            response = requests.get(url, timeout=10)  # Add timeout
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        except requests.exceptions.Timeout:
            logger.error(f"Request timed out for {url}")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error occurred for {url}: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from {url}: {e}")
            return False

        soup = BeautifulSoup(response.content, "lxml")
        logger.debug(f"Successfully fetched and parsed HTML from {url}")

        # Example data extraction
        data_dict = {
            "Revenue": extract_data(soup, 'span', class_='revenue-value'),
            "Profit": extract_data(soup, 'div', id='net-profit'),
            "Market Cap": extract_data(soup, 'span', class_='market-cap'),
        }

        # Check if any data was extracted
        if not any(value != "N/A" for value in data_dict.values()):
            logger.warning(f"No data extracted from {url}.  Check the website structure.")
            return False

        try:
            with open(filename, "a+", newline="", encoding="utf-8") as csvfile: # changed to a+
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow(headers)
                for metric, value in data_dict.items():
                    writer.writerow([metric, value, url])
        except (IOError, OSError) as e:
            logger.error(f"Error writing to file {filename}: {e}")
            return False

        logger.info(f"Data for {company_name} successfully written to {filename}")
        return True

    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}")
        return False

def extract_data(soup, tag, attrs):
    """
    Helper function to extract data from the HTML.

    Args:
        soup (BeautifulSoup): The parsed HTML.
        tag (str): The HTML tag to find.
        attrs (dict): The attributes to match.

    Returns:
        str: The extracted text, or "N/A" if not found.
    """
    try:
        element = soup.find(tag, attrs=attrs)
        if element:
            text = element.text.strip()
            logger.debug(f"Extracted '{text}' from tag '{tag}' with attrs: {attrs}")
            return text
        else:
            logger.warning(f"Element not found for tag '{tag}' with attrs: {attrs}")
            return "N/A"
    except Exception as e:
        logger.error(f"Error extracting data: {e}")
        return "N/A"  # Return "N/A" on error to keep the program running

def process_command_line():
    """
    Processes command-line arguments.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Scrape economic data and store it in CSV files.")
    parser.add_argument(
        "-a", "--all", action="store_true", help="Scrape data for all UK companies in the list."
    )
    parser.add_argument("company_name", nargs="?", help="The name of the company to scrape data for.")
    parser.add_argument("url", nargs="?", help="The URL of the website to scrape.")
    return parser.parse_args()

def get_ftse_100_companies():
    """
    Scrapes the list of FTSE 100 companies and their information from Wikipedia.

    Returns:
        dict: A dictionary of company names and their corresponding Wikipedia URLs,
              or None on failure.
    """
    url = "https://en.wikipedia.org/wiki/FTSE_100_Index"
    try:
        logger.info(f"Fetching FTSE 100 list from {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")

        # Find the table containing the list of companies
        table = soup.find("table", {"class": "wikitable sortable"})
        if not table:
            logger.error("Could not find FTSE 100 company table on Wikipedia")
            return None

        companies = {}
        # Iterate through the table rows, skipping the header row
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) > 1:  # Ensure the row has enough columns
                company_name = cells[1].text.strip()
                # Get the link to the company's Wikipedia page.
                link = cells[1].find("a")
                if link:
                    company_url = "https://en.wikipedia.org" + link["href"]
                    companies[company_name] = company_url
                else:
                    companies[company_name] = None
        return companies
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching FTSE 100 list: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None



def find_financial_data_url(company_name, wikipedia_url):
    """
    Finds the URL for the financial data of a company.  This is a complex
    problem, as there is no single, consistent source.  This function
    implements a heuristic approach, and may need to be adapted.

    Args:
        company_name (str): The name of the company.
        wikipedia_url(str): the wikipedia url of the company

    Returns:
        str: The URL of the financial data, or None if not found.
    """
    # First, try searching on Google Finance
    search_query = f"{company_name} financials"
    try:
        logger.info(f"Searching for financial data URL for {company_name} on Google Finance")
        google_search_url = f"https://www.google.com/search?q={search_query}&tbm=fin" #tbm=fin for finance
        response = requests.get(google_search_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        #google search result parsing is fragile, and often breaks.
        link = soup.find("a", href=re.compile(r"finance\.yahoo\.com"))
        if link:
            finance_url = link["href"]
            logger.info(f"Found financial data URL for {company_name} on Google Finance: {finance_url}")
            return finance_url
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error searching on Google Finance: {e}")

    #second, try company wikipedia page.
    if wikipedia_url:
      try:
        logger.info(f"Looking for financial data URL for {company_name} on wikipedia: {wikipedia_url}")
        response = requests.get(wikipedia_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        #look for external link
        link = soup.find("a", {"class": "external text"}, href=re.compile(r"finance\.yahoo\.com"))
        if link:
            finance_url = link["href"]
            logger.info(f"Found financial data URL for {company_name} on wikipedia: {finance_url}")
            return finance_url
      except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching wikipedia page: {e}")

    logger.warning(f"Could not find financial data URL for {company_name}")
    return None



def main():
    """
    Main function to run the scraper.
    """
    args = process_command_line()

    # Always run with -a
    args.all = True

    if args.all:
        logger.info("Scraping data for all UK companies...")
        ftse_100_companies = get_ftse_100_companies()
        if ftse_100_companies:
            for company_name, wikipedia_url in ftse_100_companies.items():
                financial_data_url = find_financial_data_url(company_name, wikipedia_url)
                if financial_data_url:
                    if not scrape_and_store_data(financial_data_url, company_name):
                        logger.error(f"Failed to scrape data for {company_name} at {financial_data_url}")
                else:
                    logger.error(f"Failed to find financial data URL for {company_name}")
        else:
            logger.error("Failed to retrieve FTSE 100 company list.")
            sys.exit(1)
        logger.info("Scraping process completed.")
    elif args.company_name and args.url:
        company_name = args.company_name
        url = args.url
        logger.info(f"Starting scraper for {company_name} at {url}")
        if scrape_and_store_data(url, company_name):
            logger.info("Scraping process completed successfully.")
        else:
            logger.error("Scraping process failed.")
            sys.exit(1)
    else:
        logger.error("Please provide either a company name and URL, or use the -a flag to scrape all companies.")
        sys.exit(1)



if __name__ == "__main__":
    main()

