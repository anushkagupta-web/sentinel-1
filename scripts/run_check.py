#!/usr/bin/env python3
"""
CLI script to run update checks manually.

Usage:
    python run_check.py                    # Check all sources
    python run_check.py --dcid BIS_CentralBankPolicyRate  # Check specific source
    python run_check.py --list             # List available sources
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sentinel import Sentinel
from utils.logger import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description='Sentinel - Data Source Update Checker'
    )
    parser.add_argument(
        '--dcid',
        type=str,
        help='Specific DCID to check (checks all if not specified)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available sources'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='output.csv',
        help='Output CSV file path (default: output.csv)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        default=True,
        help='Enable Groq LLM verification of timestamps (default: enabled)'
    )
    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Disable Groq LLM verification of timestamps'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logging(level=log_level)

    # Determine if verification should be enabled
    enable_verification = not args.no_verify

    # Initialize Sentinel
    sentinel = Sentinel(enable_verification=enable_verification)

    if enable_verification:
        print("Groq LLM verification: ENABLED")
    else:
        print("Groq LLM verification: DISABLED")

    if args.list:
        print("\nAvailable Data Sources:")
        print("-" * 50)
        for dcid in sentinel.registry.list_sources():
            source = sentinel.registry.get_source(dcid)
            print(f"  {dcid}")
            print(f"    Name:   {source.get('import_name', 'N/A')}")
            print(f"    Method: {source.get('method', 'N/A')}")
            print(f"    URL:    {source.get('data_url', 'N/A')[:60]}...")
            print()
        return

    if args.dcid:
        # Check specific source
        print(f"\nChecking: {args.dcid}")
        print("-" * 50)
        result = sentinel.check_for_updates(args.dcid)
        print(result)

        # Export single result
        sentinel.export_to_csv([result], args.output)

    else:
        # Check all sources
        print("\nChecking all data sources...")
        print("-" * 50)
        results = sentinel.check_all_sources()

        print("\nResults Summary:")
        print("-" * 70)
        for result in results:
            status = "UPDATED" if result.changed else "NO CHANGE"
            if result.error:
                status = "ERROR"

            # Add verification status
            verify_str = ""
            if result.is_verified is not None:
                verify_str = f" [VERIFIED {result.verification_confidence:.0%}]" if result.is_verified else " [NOT VERIFIED]"

            print(f"  [{status:10}] {result.import_name or result.dcid}{verify_str}")

        # Export results
        output_path = sentinel.export_to_csv(results, args.output)
        print(f"\nResults exported to: {output_path}")

        # Summary
        updated = sum(1 for r in results if r.changed)
        errors = sum(1 for r in results if r.error)
        print(f"\nSummary: {updated} updated, {len(results) - updated - errors} unchanged, {errors} errors")


if __name__ == '__main__':
    main()
