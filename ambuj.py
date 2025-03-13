from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json  # For storing metadata in JSON format
import time

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# Configure Selenium
# chrome_options = Options()
# chrome_options.add_argument("--headless")  # Run Chrome in headless mode
# Make driver global so it can be used in the TechincalSEOAgent
driver = webdriver.Chrome()

def extract_file_metadata(file_path):
    """Extracts basic metadata from a file."""
    try:
        metadata = {
            "name": os.path.basename(file_path),
            "path": file_path,
            "size_bytes": os.path.getsize(file_path),
            "created_time": os.path.getctime(file_path), # Creation time (platform-dependent)
            "modified_time": os.path.getmtime(file_path),  # Last modified time
            "accessed_time": os.path.getatime(file_path),   # Last accessed time
        }
        return metadata
    except OSError as e:
        print(f"Error getting metadata for {file_path}: {e}")
        return None


def analyze_web_page(url): #removed chromedriver_path to use global driver
    """
    Analyzes a web page, extracts key elements, and returns metadata.

    Args:
        url (str): The URL of the web page to analyze.

    Returns:
        dict: A dictionary containing:
            - "url": The URL of the page.
            - "title": The page title.
            - "meta_tags": A list of dictionaries, each containing name/content attributes of meta tags.
            - "headings": A list of all heading text (h1, h2, ..., h6).
            - "links": A list of all links (href attributes).
            - "metadata": The web page metadata
    """
    #driver = None  # Initialize driver outside the try block # Removed local driver to use global driver

    try:
        # --- WebDriver Setup ---
        # if chromedriver_path: #Removed Chromedriver Path condition
        #     service = ChromeService(executable_path=chromedriver_path)
        #     driver = webdriver.Chrome(service=service)
        # else:
        #     # Try to use webdriver_manager (if installed) or assume ChromeDriver is in PATH
        #     try:
        #         from webdriver_manager.chrome import ChromeDriverManager
        #         driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
        #     except ImportError:
        #         driver = webdriver.Chrome()  # Assumes ChromeDriver is in PATH # Removed Chrome driver setup


        driver.get(url)

        # --- Extract Metadata ---
        page_metadata = {
            "url": url,
            "title": driver.title,
            "meta_tags": [],
            "headings": [],
            "links": [],
        }

        # --- Extract Meta Tags ---
        meta_elements = driver.find_elements(By.TAG_NAME, "meta")
        for meta in meta_elements:
            meta_data = {}
            if meta.get_attribute("name"):
                meta_data["name"] = meta.get_attribute("name")
            if meta.get_attribute("content"):
                meta_data["content"] = meta.get_attribute("content")
            page_metadata["meta_tags"].append(meta_data)  # Append the dict

        # --- Extract Headings (h1-h6) ---
        for i in range(1, 7):
            heading_elements = driver.find_elements(By.TAG_NAME, f"h{i}")  # f-string for dynamic tag names
            for heading in heading_elements:
                page_metadata["headings"].append(heading.text)

        # --- Extract Links ---
        link_elements = driver.find_elements(By.TAG_NAME, "a")
        for link in link_elements:
            href = link.get_attribute("href")
            if href:  # Only add links with valid hrefs
                page_metadata["links"].append(href)
        page_metadata["metadata"] = extract_file_metadata(url) # Add Metadata of the web page

        return page_metadata


    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    # finally: #removed finally block to avoid closing browser for other agents
    #     if driver:
    #         driver.quit()  # Ensure the browser closes even if errors occur


class Agent:
    def __init__(self, name, description):
        self.name = name
        self.description = description

    def analyze(self, url):
        raise NotImplementedError


class KeywordResearchAgent(Agent):
    def analyze(self, url):
        prompt = f"Find relevant keywords for the following URL: {url}"
        response = model.generate_content(prompt)
        return response.text


class OnPageOptimizationAgent(Agent):
    def analyze(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            title = soup.find('title').text if soup.find('title') else 'No title found'
            description = soup.find('meta', attrs={'name': 'description'})['content'] if soup.find('meta', attrs={
                'name': 'description'}) else 'No description found'
            prompt = f"Analyze the following title: {title} and description: {description} for SEO."
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error analyzing on-page elements: {e}"


class ContentAnalysisAgent(Agent):
    def analyze(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            # Extract all text from <p> tags
            content = ' '.join([p.get_text(strip=True) for p in soup.find_all('p')])
            prompt = f"Analyze the following website content for SEO and provide recommendations:\n\n{content}"
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error analyzing content: {e}"


class TechnicalSEOAgent(Agent):  # Modified this class to integrate the analyze_web_page function
    def analyze(self, url):
        try:
            # Use Selenium and the analyze_web_page function to get comprehensive data
            page_data = analyze_web_page(url)  # Call the analyze_web_page function

            if not page_data:
                return "Failed to retrieve page data for technical SEO analysis."

            # Extract relevant data from page_data
            ssl_certificate = "Present" if url.startswith("https://") else "Not present"
            mobile_friendly = "Yes" if any(
                meta.get("name") == "viewport" for meta in page_data["meta_tags"]
            ) else "No"
            sitemap_url = f"{url.rstrip('/')}/sitemap.xml"
            sitemap_response = requests.get(sitemap_url)
            sitemap_present = "Present" if sitemap_response.status_code == 200 else "Not present"

            # --- Broken Links Check (Simplified) ---
            broken_links = []
            for link in page_data["links"]:
                if link and link.startswith('http'):
                    try:
                        response = requests.get(link)
                        if response.status_code != 200:
                            broken_links.append(link)
                    except requests.exceptions.RequestException:
                        broken_links.append(link)

            # Page Speed Check (Simplified, can be enhanced with more sophisticated metrics)
            navigation_start = driver.execute_script("return window.performance.timing.navigationStart")
            dom_complete = driver.execute_script("return window.performance.timing.domComplete")
            load_time = dom_complete - navigation_start
            page_speed_score = "Good" if load_time < 3000 else "Needs improvement"
            # -- Metadata check
            metadata = page_data["metadata"]

            # Construct the prompt for Gemini, including comprehensive data
            prompt = f"""
            Analyze the following technical SEO aspects of a website based on extracted data:

            * URL: {page_data["url"]}
            * Title: {page_data["title"]}
            * Meta Tags: {page_data["meta_tags"]}
            * Headings: {page_data["headings"]}
            * Links: {page_data["links"]}
            * SSL Certificate: {ssl_certificate}
            * Mobile-friendly: {mobile_friendly}
            * Sitemap: {sitemap_present}
            * Broken Links: {broken_links}
            * Page Speed Score: {page_speed_score} (Load time: {load_time} ms)
            *Metadata:{metadata}
            Provide recommendations for improvement, focusing on the extracted metadata and technical aspects.
            """
            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            return f"Error analyzing technical SEO: {e}"


class LinkBuildingAgent(Agent):
    def analyze(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract relevant content for analysis (e.g., title, headings, keywords)
            title = soup.find('title').text if soup.find('title') else ""
            headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])]
            # You might need to use the KeywordResearchAgent here to get relevant keywords

            # Construct the prompt for Gemini
            prompt = f"""
                    Suggest link building strategies for a website with the following characteristics:

                    * Title: {title}
                    * Headings: {headings}
                    * URL: {url}
                    """
            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            return f"Error analyzing link building opportunities: {e}"


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze_seo")
async def analyze_seo(request: Request, url: str = Form(...)):
    keyword_agent = KeywordResearchAgent("Keyword Agent", "Finds keywords")
    onpage_agent = OnPageOptimizationAgent("On-Page Agent", "Analyzes on-page elements")
    content_agent = ContentAnalysisAgent("Content Agent", "Analyzes content")
    technical_agent = TechnicalSEOAgent("Technical Agent", "Checks technical aspects")
    link_building_agent = LinkBuildingAgent("Link Building Agent", "Suggests link building strategies")

    keyword_results = keyword_agent.analyze(url)
    onpage_results = onpage_agent.analyze(url)
    content_results = content_agent.analyze(url)
    technical_results = technical_agent.analyze(url)
    link_building_results = link_building_agent.analyze(url)

    report = f"""
    Keyword Analysis:
    {keyword_results}

    On-Page Analysis:
    {onpage_results}

    Content Analysis:
    {content_results}

    Technical SEO Analysis:
    {technical_results}

    Link Building Analysis:
    {link_building_results}
    """

    return templates.TemplateResponse("index.html", {"request": request, "report": report, "url": url})

# after all the agents performed their task quit the driver
@app.on_event("shutdown")
async def shutdown_event():
    driver.quit()