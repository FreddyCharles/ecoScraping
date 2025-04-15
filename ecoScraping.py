import requests
from bs4 import BeautifulSoup
import csv
import os
import argparse
import sys
import logging
from urllib.parse import urlparse
from socket import timeout

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
    parser.add_argument("company_name", help="The name of the company to scrape data for.")
    parser.add_argument("url", help="The URL of the website to scrape.")
    return parser.parse_args()

def is_valid_url(url):
    """
    Checks if a URL is valid.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def main():
    """
    Main function to run the scraper.
    """
    args = process_command_line()
    company_name = args.company_name
    url = args.url

    logger.info(f"Starting scraper for {company_name} at {url}")
    if scrape_and_store_data(url, company_name):
        logger.info("Scraping process completed successfully.")
    else:
        logger.error("Scraping process failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
