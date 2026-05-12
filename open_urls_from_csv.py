import pandas as pd
import webbrowser
import time

def open_urls_from_csv():
    """
    Opens URLs from a CSV file based on user-specified ID range.
    """
    print("=" * 60)
    print("URL Opener Tool - Open URLs from CSV File")
    print("=" * 60)

    # Get CSV file path from user
    csv_file_path = input("\nEnter CSV file path (e.g., Input/DC_Imports_URLs.csv): ").strip()

    try:
        # Read the CSV file
        df = pd.read_csv(csv_file_path)

        # Display CSV info
        print(f"\n[SUCCESS] CSV file loaded successfully!")
        print(f"Total rows: {len(df)}")
        print(f"\nColumns found: {', '.join(df.columns.tolist())}")

        # Check if required columns exist
        if 'id' not in df.columns or 'provenance_url' not in df.columns:
            print("\n[ERROR] CSV must have 'id' and 'provenance_url' columns")
            return

        # Display first few rows
        print(f"\nFirst 5 rows:")
        print(df.head().to_string())

        # Get ID range from user
        print("\n" + "=" * 60)
        print("Specify which URLs to open:")
        start_id = int(input("Enter starting ID: "))
        end_id = int(input("Enter ending ID: "))

        # Validate range
        if start_id > end_id:
            print("\n[ERROR] Error: Starting ID cannot be greater than ending ID")
            return

        # Filter the dataframe based on ID range
        filtered_df = df[(df['id'] >= start_id) & (df['id'] <= end_id)]

        if filtered_df.empty:
            print(f"\n[ERROR] No URLs found for IDs {start_id} to {end_id}")
            return

        # Remove rows with empty/NaN URLs
        filtered_df = filtered_df[filtered_df['provenance_url'].notna()]
        filtered_df = filtered_df[filtered_df['provenance_url'].astype(str).str.strip() != '']

        urls_to_open = len(filtered_df)

        if urls_to_open == 0:
            print(f"\n[ERROR] No valid URLs found for IDs {start_id} to {end_id}")
            return

        print(f"\n[SUCCESS] Found {urls_to_open} valid URLs to open")
        print("\nURLs that will be opened:")
        for idx, row in filtered_df.iterrows():
            print(f"  ID {row['id']}: {row['provenance_url']}")

        # Confirm before opening
        confirm = input(f"\nDo you want to open these {urls_to_open} URLs in your browser? (yes/no): ").strip().lower()

        if confirm not in ['yes', 'y']:
            print("\n[ERROR] Operation cancelled by user")
            return

        # Open URLs in browser
        print("\n" + "=" * 60)
        print("Opening URLs in browser...")
        print("=" * 60)

        for idx, row in filtered_df.iterrows():
            url = row['provenance_url']
            url_id = row['id']

            try:
                print(f"Opening ID {url_id}: {url}")
                webbrowser.open(url)

                # Add small delay to avoid overwhelming the browser
                time.sleep(0.5)

            except Exception as e:
                print(f"[ERROR] Error opening URL for ID {url_id}: {e}")

        print(f"\n[SUCCESS] Successfully opened {urls_to_open} URLs in your browser!")

    except FileNotFoundError:
        print(f"\n[ERROR] Error: File '{csv_file_path}' not found")
        print("Please check the file path and try again")
    except pd.errors.EmptyDataError:
        print(f"\n[ERROR] Error: The CSV file is empty")
    except ValueError as e:
        print(f"\n[ERROR] Error: Invalid input - {e}")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    open_urls_from_csv()
