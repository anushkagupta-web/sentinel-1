import pandas as pd
from datetime import datetime
import os

def clean_timestamp(timestamp):
    """Clean and standardize timestamp format"""
    if pd.isna(timestamp) or timestamp == '' or timestamp == 'N/A':
        return None

    timestamp_str = str(timestamp).strip()

    # Common formats to try
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%d-%m-%Y %H:%M:%S',
        '%Y/%m/%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%Y-%m-%d',
        '%d-%m-%Y',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    return timestamp_str

def show_columns(columns):
    """Display columns as a comma-separated list"""
    print("  ", ", ".join(columns))

def parse_column_names(input_str):
    """Parse comma-separated column names"""
    columns = [col.strip() for col in input_str.split(',')]
    return [col for col in columns if col]  # Remove empty strings

def get_columns_by_names(df, prompt, file_name, expected_count):
    """Ask user to enter comma-separated column names and validate"""
    while True:
        print(f"\n  Example: column1, column2")
        column_input = input(prompt).strip()

        if not column_input:
            print(f"\n  ❌ Please enter column names.")
            continue

        columns = parse_column_names(column_input)

        if len(columns) != expected_count:
            print(f"\n  ❌ Please enter exactly {expected_count} column name(s).")
            print(f"  Available columns in {file_name}:")
            show_columns(df.columns.tolist())
            continue

        # Validate all columns exist
        invalid_columns = []
        for col in columns:
            if col not in df.columns:
                invalid_columns.append(col)

        if invalid_columns:
            print(f"\n  ❌ You have given wrong column name(s): {', '.join(invalid_columns)}")
            print(f"  Please check it again and tell me.")
            print(f"\n  Available columns in {file_name}:")
            show_columns(df.columns.tolist())
        else:
            print(f"  ✓ Columns found: {', '.join(columns)}")
            return columns

def compare_csv_files():
    print("=" * 75)
    print("CSV Timestamp Comparison Tool")
    print("=" * 75)
    print()

    # ========== STEP 1: Input File (O1) ==========
    print("STEP 1: Input file path dein (O1 - jisko verify karna hai)")
    print("-" * 75)
    o1_path = input("Input file O1 path: ").strip().strip('"')

    if not os.path.exists(o1_path):
        print(f"\n❌ Error: File nahi mili - {o1_path}")
        return

    # Read O1 file
    try:
        df_o1 = pd.read_csv(o1_path)
        print(f"✓ File loaded: {len(df_o1)} rows, {len(df_o1.columns)} columns")
    except Exception as e:
        print(f"\n❌ Error reading file: {e}")
        return

    # ========== STEP 2: Select O1 Columns ==========
    print("\n" + "=" * 75)
    print("STEP 2: O1 file ke columns select karein (comma separated)")
    print("-" * 75)
    print(f"Available columns in O1 file:")
    show_columns(df_o1.columns.tolist())

    o1_columns = get_columns_by_names(
        df_o1,
        "Compare to column names (URL_column, Timestamp_column): ",
        "O1",
        2
    )
    url_col_o1 = o1_columns[0]
    timestamp_col_o1 = o1_columns[1]

    # ========== STEP 3: Compare File (C1) ==========
    print("\n" + "=" * 75)
    print("STEP 3: Comparison file path dein (C1 - jisse compare karna hai)")
    print("-" * 75)
    c1_path = input("Compare file C1 path: ").strip().strip('"')

    if not os.path.exists(c1_path):
        print(f"\n❌ Error: File nahi mili - {c1_path}")
        return

    # Read C1 file
    try:
        df_c1 = pd.read_csv(c1_path)
        print(f"✓ File loaded: {len(df_c1)} rows, {len(df_c1.columns)} columns")
    except Exception as e:
        print(f"\n❌ Error reading file: {e}")
        return

    # ========== STEP 4: Select C1 Columns ==========
    print("\n" + "=" * 75)
    print("STEP 4: C1 file ke columns select karein (comma separated)")
    print("-" * 75)
    print(f"Available columns in C1 file:")
    show_columns(df_c1.columns.tolist())

    c1_columns = get_columns_by_names(
        df_c1,
        "Compare with column names (URL_column, Timestamp_column): ",
        "C1",
        2
    )
    url_col_c1 = c1_columns[0]
    timestamp_col_c1 = c1_columns[1]

    # ========== STEP 5: Comparison ==========
    print("\n" + "=" * 75)
    print("COMPARISON STARTING...")
    print("=" * 75)
    print(f"\n📌 Comparison Setup:")
    print(f"   O1 URL column:       {url_col_o1}")
    print(f"   O1 Timestamp column: {timestamp_col_o1}")
    print(f"   C1 URL column:       {url_col_c1}")
    print(f"   C1 Timestamp column: {timestamp_col_c1}")
    print()

    # Create URL to timestamp mapping for C1
    c1_mapping = {}
    for _, row in df_c1.iterrows():
        url = str(row[url_col_c1]).strip()
        timestamp = clean_timestamp(row[timestamp_col_c1])
        c1_mapping[url] = timestamp

    # Compare
    total_urls_o1 = len(df_o1)
    matched_urls = 0
    correct_timestamps = 0
    incorrect_timestamps = 0
    missing_in_c1 = 0

    results = {
        'correct': [],
        'incorrect': [],
        'missing': []
    }

    print("🔍 Step 1: Matching URLs...")
    for idx, row in df_o1.iterrows():
        url = str(row[url_col_o1]).strip()
        o1_timestamp = clean_timestamp(row[timestamp_col_o1])

        if url in c1_mapping:
            matched_urls += 1
            c1_timestamp = c1_mapping[url]

            # Compare timestamps
            if o1_timestamp == c1_timestamp:
                correct_timestamps += 1
                results['correct'].append({
                    'url': url,
                    'o1_timestamp': o1_timestamp,
                    'c1_timestamp': c1_timestamp
                })
            else:
                incorrect_timestamps += 1
                results['incorrect'].append({
                    'url': url,
                    'o1_timestamp': o1_timestamp,
                    'c1_timestamp': c1_timestamp
                })
        else:
            missing_in_c1 += 1
            results['missing'].append({
                'url': url,
                'o1_timestamp': o1_timestamp
            })

    # Calculate percentages
    url_match_percentage = (matched_urls / total_urls_o1 * 100) if total_urls_o1 > 0 else 0
    timestamp_accuracy = (correct_timestamps / matched_urls * 100) if matched_urls > 0 else 0

    # ========== STEP 6: Results ==========
    print("\n" + "=" * 75)
    print("RESULTS")
    print("=" * 75)

    # URL Matching Results
    print("\n📊 STEP 1: URL MATCHING")
    print("-" * 75)
    print(f"Total URLs in O1 file:         {total_urls_o1}")
    print(f"URLs matched with C1:          {matched_urls}/{total_urls_o1}")
    print(f"URLs not found in C1:          {missing_in_c1}/{total_urls_o1}")
    print()
    print(f"✓ URL Match Ratio:             {matched_urls}/{total_urls_o1}")
    print(f"✓ URL Match Percentage:        {url_match_percentage:.2f}%")

    # Timestamp Comparison Results
    print("\n📊 STEP 2: TIMESTAMP COMPARISON (for matched URLs only)")
    print("-" * 75)
    print(f"Total matched URLs:            {matched_urls}")
    print(f"✓ Correct timestamps:          {correct_timestamps}/{matched_urls}")
    print(f"✗ Incorrect timestamps:        {incorrect_timestamps}/{matched_urls}")
    print()
    print(f"✓ Timestamp Match Ratio:       {correct_timestamps}/{matched_urls}")
    print(f"✓ Timestamp Accuracy:          {timestamp_accuracy:.2f}%")

    # Overall Summary
    print("\n" + "=" * 75)
    print("📈 OVERALL SUMMARY")
    print("=" * 75)
    print(f"URL Matching:                  {matched_urls}/{total_urls_o1} ({url_match_percentage:.2f}%)")
    print(f"Timestamp Accuracy:            {correct_timestamps}/{matched_urls} ({timestamp_accuracy:.2f}%)")
    print("=" * 75)

    # Show incorrect timestamps details
    if incorrect_timestamps > 0:
        print("\n" + "=" * 75)
        print("❌ INCORRECT TIMESTAMPS DETAILS")
        print("=" * 75)
        for i, item in enumerate(results['incorrect'][:10], 1):  # Show first 10
            print(f"\n{i}. URL: {item['url'][:65]}...")
            print(f"   O1 timestamp: {item['o1_timestamp']}")
            print(f"   C1 timestamp: {item['c1_timestamp']}")

        if len(results['incorrect']) > 10:
            print(f"\n... aur {len(results['incorrect']) - 10} incorrect timestamps hain")

    # Show missing URLs
    if missing_in_c1 > 0:
        print("\n" + "=" * 75)
        print("⚠️  MISSING URLS (Not found in C1)")
        print("=" * 75)
        for i, item in enumerate(results['missing'][:5], 1):  # Show first 5
            print(f"{i}. {item['url'][:70]}...")

        if len(results['missing']) > 5:
            print(f"\n... aur {len(results['missing']) - 5} missing URLs hain")

    print("\n" + "=" * 75)
    print("✓ Comparison complete!")
    print("=" * 75)

if __name__ == "__main__":
    try:
        compare_csv_files()
    except KeyboardInterrupt:
        print("\n\n⚠️  Program cancelled by user.")
    except Exception as e:
        print(f"\n\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
