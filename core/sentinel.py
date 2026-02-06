"""
Sentinel - Main entry point for the monitoring agent.
"""

import csv
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

from core.registry import SourceRegistry
from core.state_manager import StateManager
from models.check_result import CheckResult
from utils.groq_verifier import GroqVerifier


class Sentinel:
    """Main monitoring agent that orchestrates update checks."""

    def __init__(
        self,
        config_path: str = None,
        settings_path: str = None,
        state_file: str = None,
        enable_verification: bool = True
    ):
        """
        Initialize the Sentinel monitoring agent.

        Args:
            config_path: Path to sources.yaml
            settings_path: Path to settings.yaml
            state_file: Path to state JSON file
            enable_verification: Enable Groq LLM verification of timestamps
        """
        self.registry = SourceRegistry(config_path, settings_path)
        self.state_manager = StateManager(state_file)
        self.logger = logging.getLogger('Sentinel')
        self.enable_verification = enable_verification

        # Initialize Groq verifier if enabled
        self.verifier = None
        if enable_verification:
            self.verifier = GroqVerifier()
            if not self.verifier.client:
                self.logger.warning("Groq verification disabled - API key not found")

        # Configure logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging based on settings."""
        log_settings = self.registry.get_settings().get('logging', {})
        level = getattr(logging, log_settings.get('level', 'INFO'))
        format_str = log_settings.get(
            'format',
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        logging.basicConfig(level=level, format=format_str)

    def check_for_updates(self, dcid: str) -> CheckResult:
        """
        Check if a data source has been updated.

        Args:
            dcid: Data Commons ID of the source to check

        Returns:
            CheckResult with update status and timestamps
        """
        self.logger.info(f"Checking for updates: {dcid}")

        # Get source configuration
        source_config = self.registry.get_source(dcid)
        if not source_config:
            return CheckResult(
                dcid=dcid,
                import_name=None,
                changed=False,
                error=f"Source not found: {dcid}"
            )

        import_name = source_config.get('import_name', dcid)
        data_url = source_config.get('data_url', '')
        script_url = source_config.get('script_url', '')
        method = source_config.get('method', '')

        # Get handler for this source
        handler = self.registry.get_handler(dcid)
        if not handler:
            return CheckResult(
                dcid=dcid,
                import_name=import_name,
                data_url=data_url,
                script_url=script_url,
                method=method,
                changed=False,
                error=f"No handler available for: {dcid}"
            )

        # Fetch current timestamp
        try:
            current_timestamp = handler.fetch_current_timestamp()
        except Exception as e:
            self.logger.error(f"Error fetching timestamp for {dcid}: {e}")
            return CheckResult(
                dcid=dcid,
                import_name=import_name,
                data_url=data_url,
                script_url=script_url,
                method=method,
                changed=False,
                error=str(e)
            )

        # Get stored timestamp
        stored_timestamp = self.state_manager.get_last_timestamp(dcid)

        # Compare timestamps
        changed = handler.compare_with_stored(current_timestamp, stored_timestamp)

        # Update state if we got a valid timestamp
        if current_timestamp:
            self.state_manager.update_timestamp(
                dcid,
                current_timestamp,
                raw_value=handler.get_raw_timestamp(),
                etag=getattr(handler, 'get_etag', lambda: None)()
            )

        result = CheckResult(
            dcid=dcid,
            import_name=import_name,
            data_url=data_url,
            script_url=script_url,
            method=method,
            changed=changed,
            current_timestamp=current_timestamp,
            previous_timestamp=stored_timestamp,
            raw_timestamp=handler.get_raw_timestamp()
        )

        # Verify timestamp using Groq LLM if enabled and we have a timestamp
        if self.verifier and self.verifier.client and current_timestamp:
            self.logger.info(f"Verifying timestamp for {dcid} using Groq LLM...")
            raw_timestamp = handler.get_raw_timestamp() or str(current_timestamp)

            # Get page content for verification (if available from handler)
            page_content = getattr(handler, '_page_content', '') or raw_timestamp

            verification_result = self.verifier.verify_timestamp(
                extracted_timestamp=raw_timestamp,
                page_content=page_content,
                source_name=import_name,
                data_url=data_url
            )

            result.is_verified = verification_result.get('is_verified')
            result.verification_confidence = verification_result.get('confidence', 0)
            result.verification_reasoning = verification_result.get('reasoning')
            result.suggested_timestamp = verification_result.get('suggested_timestamp')

            self.logger.info(
                f"Verification for {dcid}: verified={result.is_verified}, "
                f"confidence={result.verification_confidence:.0%}"
            )

        self.logger.info(f"Result for {dcid}: changed={changed}, timestamp={current_timestamp}")
        return result

    def check_all_sources(self) -> List[CheckResult]:
        """
        Check all configured sources for updates.

        Returns:
            List of CheckResult objects
        """
        results = []
        sources = self.registry.list_sources()

        self.logger.info(f"Checking {len(sources)} sources...")

        for dcid in sources:
            result = self.check_for_updates(dcid)
            results.append(result)

        return results

    def export_to_csv(
        self,
        results: List[CheckResult],
        output_path: str = None
    ) -> str:
        """
        Export results to CSV file.

        Args:
            results: List of CheckResult objects
            output_path: Output CSV file path

        Returns:
            Path to the created CSV file
        """
        if output_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_path = os.path.join(base_dir, 'output.csv')

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

        fieldnames = [
            'import_name',
            'dcid',
            'data_url',
            'script_url',
            'method',
            'last_modified_timestamp',
            'raw_timestamp',
            'previous_timestamp',
            'changed',
            'check_time',
            'status',
            'error',
            # Verification fields
            'is_verified',
            'verification_confidence',
            'verification_reasoning',
            'suggested_timestamp'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                writer.writerow({
                    'import_name': result.import_name or '',
                    'dcid': result.dcid,
                    'data_url': result.data_url or '',
                    'script_url': result.script_url or '',
                    'method': result.method or '',
                    'last_modified_timestamp': result.current_timestamp.isoformat() if result.current_timestamp else '',
                    'raw_timestamp': result.raw_timestamp or '',
                    'previous_timestamp': result.previous_timestamp.isoformat() if result.previous_timestamp else '',
                    'changed': result.changed,
                    'check_time': result.check_time.isoformat() if result.check_time else '',
                    'status': 'success' if not result.error else 'error',
                    'error': result.error or '',
                    # Verification fields
                    'is_verified': result.is_verified if result.is_verified is not None else '',
                    'verification_confidence': f"{result.verification_confidence:.0%}" if result.verification_confidence else '',
                    'verification_reasoning': result.verification_reasoning or '',
                    'suggested_timestamp': result.suggested_timestamp or ''
                })

        self.logger.info(f"Results exported to: {output_path}")
        return output_path


def check_for_updates(dcid: str) -> CheckResult:
    """
    Convenience function to check a single source for updates.

    Args:
        dcid: Data Commons ID

    Returns:
        CheckResult object
    """
    sentinel = Sentinel()
    return sentinel.check_for_updates(dcid)
