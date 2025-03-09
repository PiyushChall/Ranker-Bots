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
from selenium.webdriver.chrome.options import Options

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# Configure Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run Chrome in headless mode
driver = webdriver.Chrome(options=chrome_options)



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


class TechnicalSEOAgent(Agent):
    def analyze(self, url):
        try:
            # Use Selenium to get the page source (for JavaScript rendering)
            driver.get(url)
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, "html.parser")

            # Check for SSL certificate
            ssl_certificate = "Present" if url.startswith("https://") else "Not present"

            # Check for mobile-friendliness (basic check using viewport meta tag)
            viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
            mobile_friendly = "Yes" if viewport_meta else "No"

            # Check for sitemap.xml
            sitemap_url = f"{url.rstrip('/')}/sitemap.xml"
            sitemap_response = requests.get(sitemap_url)
            sitemap_present = "Present" if sitemap_response.status_code == 200 else "Not present"

            # Check for broken links
            broken_links = []
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and href.startswith('http'):
                    try:
                        response = requests.get(href)
                        if response.status_code != 200:
                            broken_links.append(href)
                    except requests.exceptions.RequestException:
                        broken_links.append(href)

            # Check for page speed (using Selenium to get performance timings)
            navigation_start = driver.execute_script("return window.performance.timing.navigationStart")
            dom_complete = driver.execute_script("return window.performance.timing.domComplete")
            load_time = dom_complete - navigation_start
            page_speed_score = "Good" if load_time < 3000 else "Needs improvement"

            # Construct the prompt for Gemini
            prompt = f"""
                        Analyze the following technical SEO aspects of a website:

                        * SSL Certificate: {ssl_certificate}
                        * Mobile-friendly: {mobile_friendly}
                        * Sitemap: {sitemap_present}
                        * Broken Links: {broken_links}
                        * Page Speed Score: {page_speed_score} (Load time: {load_time} ms)

                        Provide recommendations for improvement.
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


# templates/index.html (basic form and report display)
"""
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Agent SEO Agency</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <h1>Multi-Agent SEO Agency</h1>
        <form method="post" action="/analyze_seo">
            <input type="url" name="url" placeholder="Enter URL to analyze" required><br><br>
            <button type="submit">Analyze</button>
        </form>

        {% if report %}
            <div class="result-box">
                <h2>SEO Report:</h2>
                <p>{{ report|replace('\n', '<br>')|safe }}</p>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""
