import pandas as pd
import requests
from bs4 import BeautifulSoup
from time import sleep
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('seo_analysis.log')
    ]
)

class SEOAnalyzer:
    def __init__(self, csv_path: str, branded_terms: List[str], request_delay: float = 1.0):
        """
        Initialize the SEO Analyzer.
        
        Args:
            csv_path: Path to the Google Search Console CSV file
            branded_terms: List of branded terms to exclude
            request_delay: Delay between URL requests in seconds
        """
        self.csv_path = csv_path
        self.branded_terms = [term.strip().lower() for term in branded_terms]
        self.request_delay = request_delay
        self.session = requests.Session()
        # Set a reasonable timeout and user agent
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def load_and_filter_data(self) -> pd.DataFrame:
        """Load the CSV file and filter out branded terms."""
        try:
            df = pd.read_csv(self.csv_path)
            logging.info(f"Loaded {len(df)} rows from CSV file")
            
            # Filter out branded terms
            pattern = '|'.join(map(lambda x: rf"{x}", self.branded_terms))
            if pattern:
                df = df[~df['Query'].str.lower().str.contains(pattern, na=False)]
                logging.info(f"Filtered data to {len(df)} rows after removing branded terms")
            
            return df
        except Exception as e:
            logging.error(f"Error loading CSV file: {e}")
            raise

    def select_top_queries(self, group: pd.DataFrame) -> pd.DataFrame:
        """
        Select top 8 queries by clicks and top 2 by impressions.
        If less than 8 queries have clicks, fill with top impression queries.
        """
        # Sort by clicks (descending) and get queries with clicks > 0
        queries_with_clicks = group[group['Clicks'] > 0].sort_values('Clicks', ascending=False)
        
        # Get top 8 by clicks or all if less than 8
        top_by_clicks = queries_with_clicks.head(8)
        
        # Calculate how many more queries we need
        remaining_slots = 10 - len(top_by_clicks)
        
        # Get additional queries by impressions, excluding those already selected
        if remaining_slots > 0:
            remaining_queries = group[~group['Query'].isin(top_by_clicks['Query'])]
            top_by_impressions = remaining_queries.sort_values('Impressions', ascending=False).head(remaining_slots)
            return pd.concat([top_by_clicks, top_by_impressions])
        
        return top_by_clicks

    def fetch_html_content(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch HTML content from URL with error handling and rate limiting."""
        try:
            sleep(self.request_delay)  # Rate limiting
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch content for URL {url}: {e}")
            return None

    def check_presence(self, soup: BeautifulSoup, query: str) -> Dict[str, bool]:
        """Check presence of query in various HTML elements."""
        if not soup:
            return {tag: False for tag in ['Title', 'Meta', 'H1', 'H2-1', 'H2-2', 'H3-1', 'H3-2', 'Body']}

        query = query.lower()
        presence = {}

        # Check title
        title = soup.find('title')
        presence['Title'] = bool(title and query in title.get_text(separator=" ").lower())

        # Check meta description
        meta = soup.find('meta', attrs={'name': 'description'})
        presence['Meta'] = bool(meta and meta.get('content', '').lower().find(query) != -1)

        # Check H1
        h1 = soup.find('h1')
        presence['H1'] = bool(h1 and query in h1.get_text(separator=" ").lower())

        # Check H2s
        h2s = soup.find_all('h2')
        presence['H2-1'] = bool(len(h2s) > 0 and query in h2s[0].get_text(separator=" ").lower())
        presence['H2-2'] = bool(len(h2s) > 1 and query in h2s[1].get_text(separator=" ").lower())

        # Check H3s
        h3s = soup.find_all('h3')
        presence['H3-1'] = bool(len(h3s) > 0 and query in h3s[0].get_text(separator=" ").lower())
        presence['H3-2'] = bool(len(h3s) > 1 and query in h3s[1].get_text(separator=" ").lower())

        # Check body content
        body = soup.find('body')
        presence['Body'] = bool(body and query in body.get_text(separator=" ").lower())

        return presence

    def analyze(self) -> pd.DataFrame:
        """Perform the SEO analysis."""
        df = self.load_and_filter_data()
        final_data = []
        total_urls = len(df['Landing Page'].unique())

        for idx, (landing_page, group) in enumerate(df.groupby('Landing Page'), 1):
            logging.info(f"Processing URL {idx}/{total_urls}: {landing_page}")
            
            # Select top performing queries
            top_queries = self.select_top_queries(group)
            
            # Fetch HTML content
            soup = self.fetch_html_content(landing_page)
            
            if not soup:
                logging.warning(f"Skipping URL due to fetch failure: {landing_page}")
                continue

            # Analyze each query
            for _, query_row in top_queries.iterrows():
                query = query_row['Query']
                presence = self.check_presence(soup, query)
                
                final_data.append({
                    'URL': landing_page,
                    'Query': query,
                    'Clicks': query_row['Clicks'],
                    'Impressions': query_row['Impressions'],
                    **presence
                })

        return pd.DataFrame(final_data)

def main():
    # Get input from user
    csv_path = input("Enter the path to your Google Search Console CSV file: ")
    branded_terms_input = input("Enter branded terms to exclude (comma-separated): ")
    branded_terms = [term.strip() for term in branded_terms_input.split(",")]

    try:
        # Initialize and run analysis
        analyzer = SEOAnalyzer(csv_path, branded_terms)
        results_df = analyzer.analyze()

        # Save results
        output_file = 'seo_analysis_results.csv'
        results_df.to_csv(output_file, index=False)
        logging.info(f"Analysis complete. Results saved to {output_file}")

    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        raise

if __name__ == "__main__":
    main()
