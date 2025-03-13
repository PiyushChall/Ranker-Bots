from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re  # Import the regular expression module
from docx import Document  # Import python-docx

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

def clean_text(text):
    """Removes asterisks from the given text."""
    return text.replace("*", "")

class Agent:
    def __init__(self, name, description):
        self.name = name
        self.description = description

    def analyze(self, url):
        raise NotImplementedError

class KeywordResearchAgent(Agent):
    def analyze(self, url):
        prompt = f"Find relevant keywords for the following URL: {url}. Describe the different types of keywords that are relevant (e.g., general keywords, long-tail keywords, etc.) and explain their importance for SEO."
        response = model.generate_content(prompt)
        return clean_text(response.text)

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
            return clean_text(response.text)
        except Exception as e:
            return f"Error analyzing on-page elements: {e}"

class ContentAnalysisAgent(Agent):
    def analyze(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            content = ' '.join([p.get_text(strip=True) for p in soup.find_all('p')])
            prompt = f"Analyze the following website content for SEO and provide recommendations:\n\n{content}"
            response = model.generate_content(prompt)
            return clean_text(response.text)
        except Exception as e:
            return f"Error analyzing content: {e}"

class TechnicalSEOAgent(Agent):
    def analyze(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")

            ssl_certificate = "Present" if url.startswith("https://") else "Not present"
            viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
            mobile_friendly = "Yes" if viewport_meta else "No"

            sitemap_url = f"{url.rstrip('/')}/sitemap.xml"
            sitemap_response = requests.get(sitemap_url)
            sitemap_present = "Present" if sitemap_response.status_code == 200 else "Not present"

            broken_links = []
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    absolute_href = urljoin(url, href)
                    parsed_href = urlparse(absolute_href)
                    if parsed_href.scheme.startswith('http'):
                        try:
                            link_response = requests.head(absolute_href, allow_redirects=True)
                            if link_response.status_code >= 400:
                                broken_links.append(absolute_href)
                        except requests.exceptions.RequestException:
                            broken_links.append(absolute_href)

            content_length = len(response.content)
            page_speed_score = "Good" if content_length < 500000 else "Needs improvement"

            prompt = f"""
                        Analyze the following technical SEO aspects of a website:

                        * SSL Certificate: {ssl_certificate}
                        * Mobile-friendly: {mobile_friendly}
                        * Sitemap: {sitemap_present}
                        * Broken Links: {broken_links}
                        * Page Speed Score: {page_speed_score} (Content length proxy)

                        Provide recommendations for improvement.
                        """
            response = model.generate_content(prompt)
            return clean_text(response.text)

        except Exception as e:
            return f"Error analyzing technical SEO: {e}"

class LinkBuildingAgent(Agent):
    def analyze(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            title = soup.find('title').text if soup.find('title') else ""
            headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])]
            prompt = f"""
                    Suggest link building strategies for a website with the following characteristics:

                    * Title: {title}
                    * Headings: {headings}
                    * URL: {url}
                    """
            response = model.generate_content(prompt)
            return clean_text(response.text)
        except Exception as e:
            return f"Error analyzing link building opportunities: {e}"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def generate_report_content(agent_results, url):
    """Generates the report content as a string."""
    report = f"SEO Analysis Report for {url}\n\n"
    for agent_name, result in agent_results.items():
        report += f"--- {agent_name} ---\n{result}\n\n"
    return report

@app.post("/analyze_seo")
async def analyze_seo(request: Request, url: str = Form(...)):
    keyword_agent = KeywordResearchAgent("Keyword Agent", "Finds keywords")
    onpage_agent = OnPageOptimizationAgent("On-Page Agent", "Analyzes on-page elements")
    content_agent = ContentAnalysisAgent("Content Agent", "Analyzes content")
    technical_agent = TechnicalSEOAgent("Technical Agent", "Checks technical aspects")
    link_building_agent = LinkBuildingAgent("Link Building Agent", "Suggests link building strategies")

    agent_results = {
        "Keyword Agent": keyword_agent.analyze(url),
        "On-Page Agent": onpage_agent.analyze(url),
        "Content Agent": content_agent.analyze(url),
        "Technical Agent": technical_agent.analyze(url),
        "Link Building Agent": link_building_agent.analyze(url),
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "url": url,
        "keyword_results": agent_results["Keyword Agent"],
        "onpage_results": agent_results["On-Page Agent"],
        "content_results": agent_results["Content Agent"],
        "technical_results": agent_results["Technical Agent"],
        "link_building_results": agent_results["Link Building Agent"],
    })

@app.get("/download_report")
async def download_report(url: str, download_format: str):
    """Handles the download request for the SEO report."""
    keyword_agent = KeywordResearchAgent("Keyword Agent", "Finds keywords")
    onpage_agent = OnPageOptimizationAgent("On-Page Agent", "Analyzes on-page elements")
    content_agent = ContentAnalysisAgent("Content Agent", "Analyzes content")
    technical_agent = TechnicalSEOAgent("Technical Agent", "Checks technical aspects")
    link_building_agent = LinkBuildingAgent("Link Building Agent", "Suggests link building strategies")

    agent_results = {
        "Keyword Agent": keyword_agent.analyze(url),
        "On-Page Agent": onpage_agent.analyze(url),
        "Content Agent": content_agent.analyze(url),
        "Technical Agent": technical_agent.analyze(url),
        "Link Building Agent": link_building_agent.analyze(url),
    }

    report_content = generate_report_content(agent_results, url)

    if download_format == "txt":
        # Create a temporary file
        with open("report.txt", "w") as f:
            f.write(report_content)
        return FileResponse("report.txt", filename="report.txt", media_type="text/plain")
    elif download_format == "docx":
        # Create a Word document
        document = Document()
        document.add_paragraph(report_content)
        document.save("report.docx")
        return FileResponse("report.docx", filename="report.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")