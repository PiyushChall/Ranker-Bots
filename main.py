from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

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
            description = soup.find('meta', attrs={'name':'description'})['content'] if soup.find('meta', attrs={'name':'description'}) else 'No description found'
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
        # Placeholder for technical SEO analysis
        # (e.g., check site speed, mobile-friendliness, SSL certificate)
        # This would require more complex checks using external libraries or APIs
        return "Technical SEO analysis is not yet implemented."

class LinkBuildingAgent(Agent):
    def analyze(self, url):
        # Placeholder for link building analysis
        # (e.g., suggest link building strategies based on website content)
        # This would require more advanced analysis and potentially external data sources
        return "Link building analysis is not yet implemented."

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