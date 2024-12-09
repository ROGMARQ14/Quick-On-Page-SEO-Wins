import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from time import sleep
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse
import concurrent.futures
from functools import lru_cache

# Configure page settings
st.set_page_config(
    page_title="SEO Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = None
if 'processed_urls' not in st.session_state:
    st.session_state.processed_urls = set()

# Cache the HTML content fetching
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_html_content(url: str, timeout: int = 10) -> Optional[str]:
    """Fetch and cache HTML content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        st.warning(f"Failed to fetch {url}: {str(e)}")
        return None

@st.cache_data
def parse_html(_html_content: str) -> Dict:
    """Parse HTML content and extract relevant elements."""
    if not _html_content:
        return {}
    
    soup = BeautifulSoup(_html_content, 'html.parser')
    return {
        'title': soup.find('title').get_text() if soup.find('title') else '',
        'meta': soup.find('meta', attrs={'name': 'description'}).get('content', '') if soup.find('meta', attrs={'name': 'description'}) else '',
        'h1': [h.get_text() for h in soup.find_all('h1')],
        'h2': [h.get_text() for h in soup.find_all('h2')],
        'h3': [h.get_text() for h in soup.find_all('h3')],
        'body': soup.find('body').get_text() if soup.find('body') else ''
    }

def check_query_presence(parsed_html: Dict, query: str) -> Dict[str, bool]:
    """Check if query exists in HTML elements."""
    query = query.lower()
    return {
        'Title': query in parsed_html.get('title', '').lower(),
        'Meta': query in parsed_html.get('meta', '').lower(),
        'H1': any(query in h.lower() for h in parsed_html.get('h1', [])),
        'H2-1': len(parsed_html.get('h2', [])) > 0 and query in parsed_html['h2'][0].lower(),
        'H2-2': len(parsed_html.get('h2', [])) > 1 and query in parsed_html['h2'][1].lower(),
        'H3-1': len(parsed_html.get('h3', [])) > 0 and query in parsed_html['h3'][0].lower(),
        'H3-2': len(parsed_html.get('h3', [])) > 1 and query in parsed_html['h3'][1].lower(),
        'Body': query in parsed_html.get('body', '').lower()
    }

def process_data(df: pd.DataFrame, branded_terms: List[str]) -> pd.DataFrame:
    """Process the GSC data and filter branded terms."""
    if not df.empty:
        # Filter out branded terms
        if branded_terms:
            pattern = '|'.join(map(str.lower, branded_terms))
            df = df[~df['Query'].str.lower().str.contains(pattern, na=False)]
        
        return df
    return pd.DataFrame()

def select_top_queries(group: pd.DataFrame) -> pd.DataFrame:
    """Select top 8 by clicks and 2 by impressions."""
    queries_with_clicks = group[group['Clicks'] > 0].sort_values('Clicks', ascending=False)
    top_by_clicks = queries_with_clicks.head(8)
    remaining_slots = 10 - len(top_by_clicks)
    
    if remaining_slots > 0:
        remaining_queries = group[~group['Query'].isin(top_by_clicks['Query'])]
        top_by_impressions = remaining_queries.sort_values('Impressions', ascending=False).head(remaining_slots)
        return pd.concat([top_by_clicks, top_by_impressions])
    return top_by_clicks

def main():
    st.title("🔍 SEO Performance Analyzer")
    st.write("Analyze your top-performing queries against your page content.")

    # Sidebar for file upload and settings
    with st.sidebar:
        st.header("Settings")
        uploaded_file = st.file_uploader("Upload GSC CSV file", type=['csv'])
        branded_terms = st.text_input(
            "Enter branded terms (comma-separated)",
            help="These terms will be excluded from the analysis"
        ).split(',') if st.text_input("Enter branded terms (comma-separated)") else []
        
        max_concurrent = st.slider(
            "Max concurrent URL fetches",
            min_value=1,
            max_value=10,
            value=5,
            help="Higher values may speed up processing but might get blocked by servers"
        )

    if uploaded_file is not None:
        # Load and process data
        df = pd.read_csv(uploaded_file)
        df = process_data(df, branded_terms)
        
        if df.empty:
            st.error("No data to analyze after filtering branded terms.")
            return

        # Group by Landing Page and process each URL
        results = []
        urls_to_process = set(df['Landing Page'].unique()) - st.session_state.processed_urls
        
        if urls_to_process:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                future_to_url = {
                    executor.submit(fetch_html_content, url): url 
                    for url in urls_to_process
                }
                
                completed = 0
                total = len(urls_to_process)
                
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    html_content = future.result()
                    
                    if html_content:
                        parsed_html = parse_html(html_content)
                        url_group = df[df['Landing Page'] == url]
                        top_queries = select_top_queries(url_group)
                        
                        for _, query_row in top_queries.iterrows():
                            presence = check_query_presence(parsed_html, query_row['Query'])
                            results.append({
                                'URL': url,
                                'Query': query_row['Query'],
                                'Clicks': query_row['Clicks'],
                                'Impressions': query_row['Impressions'],
                                **presence
                            })
                    
                    completed += 1
                    progress = completed / total
                    progress_bar.progress(progress)
                    status_text.text(f"Processed {completed}/{total} URLs")
                    st.session_state.processed_urls.add(url)
            
            if results:
                new_results = pd.DataFrame(results)
                if st.session_state.results is None:
                    st.session_state.results = new_results
                else:
                    st.session_state.results = pd.concat([st.session_state.results, new_results])
        
        # Display results
        if st.session_state.results is not None:
            st.header("Analysis Results")
            
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total URLs Analyzed", len(st.session_state.results['URL'].unique()))
            with col2:
                st.metric("Total Queries Analyzed", len(st.session_state.results))
            with col3:
                st.metric("Avg Queries per URL", round(len(st.session_state.results) / len(st.session_state.results['URL'].unique()), 2))
            
            # Detailed results
            st.dataframe(st.session_state.results)
            
            # Download button
            csv = st.session_state.results.to_csv(index=False)
            st.download_button(
                "Download Results",
                csv,
                "seo_analysis_results.csv",
                "text/csv",
                key='download-csv'
            )

if __name__ == "__main__":
    main()
