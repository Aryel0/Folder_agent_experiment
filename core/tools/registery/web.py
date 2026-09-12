import urllib.request
import re
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool

class FetchUrlArgs(BaseModel):
    url: str = Field(description="The full URL to fetch (must include http:// or https://).")


class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = "Fetch the text content of a webpage. Strips away HTML tags and returns only the readable text."
    args_schema = FetchUrlArgs

    def run(self, **kwargs) -> str:
        url = kwargs["url"]
        if not url.startswith("http"):
            url = "https://" + url
            
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                
                # Strip out script and style blocks
                text = re.sub(r'(?s)<(script|style).*?</\1>', '', html)
                # Strip HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                # Compress multiple spaces
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Limit return size to prevent context overflow
                if len(text) > 10000:
                    text = text[:10000] + "... [TRUNCATED]"
                    
                return text
        except Exception as e:
            return f"Error fetching URL '{url}': {str(e)}"
