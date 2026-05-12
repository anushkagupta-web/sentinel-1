import csv
from datetime import datetime

# Read the DC-Auto Refresh Failure List (Simplified v2)
failure_list = []
with open('Input/DC-Auto_Refresh_Failure_List_Simplified_v2.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        failure_list.append({
            'id': row['id'],
            'prov_id': row['prov_id'],
            'provenance_url': row['provenance_url']
        })

# Create a mapping of URL -> last_modified_timestamp from output files
url_timestamp_map = {}

# Read output_30_March_2026_2.csv
try:
    with open('Output/output_30_March_2026_2.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row['provenance_url'].strip()
            timestamp = row['last_modified_timestamp'].strip()
            if url and timestamp:
                url_timestamp_map[url] = timestamp
    print(f"Loaded {len(url_timestamp_map)} URLs from output_30_March_2026_2.csv")
except Exception as e:
    print(f"Error reading output_30_March_2026_2.csv: {e}")

# Read output_30_March_2026_3.csv
try:
    with open('Output/output_30_March_2026_3.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count_before = len(url_timestamp_map)
        for row in reader:
            url = row['provenance_url'].strip()
            timestamp = row['last_modified_timestamp'].strip()
            if url and timestamp:
                # If URL already exists, keep the existing one (from file 2)
                # or update if you want the latest
                if url not in url_timestamp_map:
                    url_timestamp_map[url] = timestamp
        print(f"Added {len(url_timestamp_map) - count_before} new URLs from output_30_March_2026_3.csv")
except Exception as e:
    print(f"Error reading output_30_March_2026_3.csv: {e}")

print(f"\nTotal unique URLs in mapping: {len(url_timestamp_map)}")

# Match and create final output
results = []
matched_count = 0
not_matched_count = 0

for item in failure_list:
    url = item['provenance_url'].strip() if item['provenance_url'] else ''

    # Try to find matching timestamp
    timestamp = None
    if url and url != '#N/A':
        # Direct match
        if url in url_timestamp_map:
            timestamp = url_timestamp_map[url]
            matched_count += 1
        else:
            # Try case-insensitive match
            for map_url, map_timestamp in url_timestamp_map.items():
                if map_url.lower() == url.lower():
                    timestamp = map_timestamp
                    matched_count += 1
                    break

    if timestamp is None:
        not_matched_count += 1

    results.append({
        'id': item['id'],
        'prov_id': item['prov_id'],
        'provenance_url': url,
        'last_modified_timestamp': timestamp if timestamp else 'NOT_FOUND'
    })

# Write the final output
output_filename = f'Output/matched_urls_with_timestamps_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
with open(output_filename, 'w', encoding='utf-8', newline='') as f:
    fieldnames = ['id', 'prov_id', 'provenance_url', 'last_modified_timestamp']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

print(f"\n=== SUMMARY ===")
print(f"Total records in DC-Auto Refresh Failure List: {len(failure_list)}")
print(f"Matched URLs: {matched_count}")
print(f"Not matched URLs: {not_matched_count}")
print(f"\nOutput file created: {output_filename}")

# Show some examples of matched and not matched
print("\n=== EXAMPLES OF MATCHED URLS ===")
matched_examples = [r for r in results if r['last_modified_timestamp'] != 'NOT_FOUND'][:5]
for ex in matched_examples:
    print(f"  {ex['id']}: {ex['provenance_url'][:60]}... -> {ex['last_modified_timestamp']}")

print("\n=== EXAMPLES OF NOT MATCHED URLS ===")
not_matched_examples = [r for r in results if r['last_modified_timestamp'] == 'NOT_FOUND'][:5]
for ex in not_matched_examples:
    print(f"  {ex['id']}: {ex['provenance_url'][:60]}...")
