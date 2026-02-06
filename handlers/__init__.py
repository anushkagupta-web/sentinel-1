"""
Handlers package - Contains all retrieval method implementations.
"""

from handlers.base_handler import BaseHandler
from handlers.http_handler import HTTPHandler
from handlers.api_handler import APIHandler
from handlers.selenium_handler import SeleniumHandler
from handlers.bs4_handler import BS4Handler
from handlers.cli_handler import CLIHandler

__all__ = [
    'BaseHandler',
    'HTTPHandler',
    'APIHandler',
    'SeleniumHandler',
    'BS4Handler',
    'CLIHandler'
]
