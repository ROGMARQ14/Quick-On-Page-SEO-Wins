# SEO Analyzer

This script analyzes SEO performance by cross-referencing Google Search Console data with HTML content from your web pages.

## Features

- Analyzes top 10 performing queries (8 by clicks, 2 by impressions)
- Checks query presence in:
  - Title tags
  - Meta descriptions
  - H1 headings
  - H2 headings (first two)
  - H3 headings (first two)
  - Body content
- Excludes branded terms from analysis
- Rate limiting to prevent server blocking
- Comprehensive error handling and logging

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Export your Google Search Console data to a CSV file
2. Run the script:
```bash
python seo_analyzer.py
```
3. When prompted:
   - Enter the path to your Google Search Console CSV file
   - Enter any branded terms you want to exclude (comma-separated)

The script will create:
- `seo_analysis_results.csv`: Contains the analysis results
- `seo_analysis.log`: Contains the execution log

## Output Format

The output CSV will contain the following columns:
- URL: The webpage URL
- Query: The search query
- Clicks: Number of clicks
- Impressions: Number of impressions
- Title: Whether the query appears in the title tag
- Meta: Whether the query appears in the meta description
- H1: Whether the query appears in the H1 heading
- H2-1: Whether the query appears in the first H2 heading
- H2-2: Whether the query appears in the second H2 heading
- H3-1: Whether the query appears in the first H3 heading
- H3-2: Whether the query appears in the second H3 heading
- Body: Whether the query appears in the body content
