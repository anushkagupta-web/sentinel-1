"""
Groq API based timestamp verification utility.
Uses LLM to verify if the extracted timestamp is actually the last modified date.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class GroqVerifier:
    """Verifies extracted timestamps using Groq LLM API."""

    def __init__(self, api_key: str = None):
        """
        Initialize Groq verifier.

        Args:
            api_key: Groq API key. If not provided, reads from GROQ_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        self.logger = logging.getLogger('GroqVerifier')
        self.client = None

        if not self.api_key:
            self.logger.warning("GROQ_API_KEY not found. Verification will be skipped.")
        else:
            self._init_client()

    def _init_client(self):
        """Initialize the Groq client."""
        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
            self.logger.info("Groq client initialized successfully")
        except ImportError:
            self.logger.error("groq package not installed. Run: pip install groq")
            self.client = None
        except Exception as e:
            self.logger.error(f"Failed to initialize Groq client: {e}")
            self.client = None

    def verify_timestamp(
        self,
        extracted_timestamp: str,
        page_content: str,
        source_name: str,
        data_url: str
    ) -> Dict[str, Any]:
        """
        Verify if the extracted timestamp is the actual last modified date.

        Args:
            extracted_timestamp: The timestamp that was extracted
            page_content: The raw HTML/text content from the page
            source_name: Name of the data source
            data_url: URL of the data source

        Returns:
            Dict with verification result:
            {
                'is_verified': bool,
                'confidence': float (0-1),
                'reasoning': str,
                'suggested_timestamp': str or None,
                'error': str or None
            }
        """
        if not self.client:
            return {
                'is_verified': None,
                'confidence': 0,
                'reasoning': 'Groq client not available',
                'suggested_timestamp': None,
                'error': 'GROQ_API_KEY not configured or groq package not installed'
            }

        # Truncate content if too long (Groq has token limits)
        max_content_length = 4000
        truncated_content = page_content[:max_content_length]
        if len(page_content) > max_content_length:
            truncated_content += "\n... [content truncated]"

        prompt = self._build_verification_prompt(
            extracted_timestamp,
            truncated_content,
            source_name,
            data_url
        )

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a data verification assistant. Your job is to verify if an extracted timestamp is actually the "last modified" or "last updated" date of a data source.

Analyze the provided content carefully and determine:
1. Is the extracted timestamp actually the last modified/updated date?
2. How confident are you? (0.0 to 1.0)
3. If the extracted timestamp is wrong, what is the correct one?

Respond in this exact JSON format:
{
    "is_verified": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation",
    "correct_timestamp": "YYYY-MM-DD HH:MM:SS or null if extracted is correct"
}"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=500
            )

            return self._parse_response(response.choices[0].message.content)

        except Exception as e:
            self.logger.error(f"Groq API call failed: {e}")
            return {
                'is_verified': None,
                'confidence': 0,
                'reasoning': f'API call failed: {str(e)}',
                'suggested_timestamp': None,
                'error': str(e)
            }

    def _build_verification_prompt(
        self,
        extracted_timestamp: str,
        content: str,
        source_name: str,
        data_url: str
    ) -> str:
        """Build the prompt for verification."""
        return f"""Please verify if the following extracted timestamp is correct.

**Data Source:** {source_name}
**URL:** {data_url}
**Extracted Timestamp:** {extracted_timestamp}

**Page Content:**
```
{content}
```

Is "{extracted_timestamp}" the actual last modified/updated date for this data source? Look for phrases like:
- "Last Updated:", "Last Modified:", "Updated on:", "Modified:"
- "Data as of:", "Release Date:", "Published:"
- Meta tags with dates
- Any timestamp indicating when the data was last changed

Provide your verification result in the JSON format specified."""

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the LLM response."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'is_verified': result.get('is_verified', False),
                    'confidence': float(result.get('confidence', 0)),
                    'reasoning': result.get('reasoning', ''),
                    'suggested_timestamp': result.get('correct_timestamp'),
                    'error': None
                }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse JSON response: {e}")

        # Fallback: try to extract info from text
        return {
            'is_verified': None,
            'confidence': 0,
            'reasoning': response_text[:500],
            'suggested_timestamp': None,
            'error': 'Could not parse structured response'
        }

    def verify_with_headers(
        self,
        extracted_timestamp: str,
        http_headers: Dict[str, str],
        source_name: str
    ) -> Dict[str, Any]:
        """
        Verify timestamp using HTTP headers (simpler verification).

        Args:
            extracted_timestamp: The timestamp that was extracted
            http_headers: HTTP response headers
            source_name: Name of the data source

        Returns:
            Verification result dict
        """
        if not self.client:
            return {
                'is_verified': None,
                'confidence': 0,
                'reasoning': 'Groq client not available',
                'suggested_timestamp': None,
                'error': 'GROQ_API_KEY not configured'
            }

        headers_str = "\n".join([f"{k}: {v}" for k, v in http_headers.items()])

        prompt = f"""Verify if this extracted timestamp matches the HTTP headers.

**Source:** {source_name}
**Extracted Timestamp:** {extracted_timestamp}

**HTTP Headers:**
```
{headers_str}
```

Check if the extracted timestamp matches the "Last-Modified" header or other date-related headers.
Respond in JSON format: {{"is_verified": bool, "confidence": float, "reasoning": str, "correct_timestamp": str or null}}"""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a timestamp verification assistant. Respond only in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            return self._parse_response(response.choices[0].message.content)

        except Exception as e:
            self.logger.error(f"Groq API call failed: {e}")
            return {
                'is_verified': None,
                'confidence': 0,
                'reasoning': str(e),
                'suggested_timestamp': None,
                'error': str(e)
            }


def verify_timestamp(
    extracted_timestamp: str,
    page_content: str,
    source_name: str,
    data_url: str,
    api_key: str = None
) -> Dict[str, Any]:
    """
    Convenience function to verify a timestamp.

    Args:
        extracted_timestamp: The timestamp that was extracted
        page_content: The raw content from the page
        source_name: Name of the data source
        data_url: URL of the data source
        api_key: Optional Groq API key

    Returns:
        Verification result dict
    """
    verifier = GroqVerifier(api_key)
    return verifier.verify_timestamp(
        extracted_timestamp,
        page_content,
        source_name,
        data_url
    )
