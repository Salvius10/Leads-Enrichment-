import csv
from datetime import datetime
from typing import Any


def export_contacts_to_csv(
    contacts: list[dict[str, Any]],
    output_path: str,
    dedup_metadata: dict[str, Any] = None,
):
    """Export contacts to CSV with optional deduplication metadata."""
    if not contacts:
        return

    # Get all unique keys from contacts
    fieldnames = set()
    for contact in contacts:
        fieldnames.update(contact.keys())

    # Add deduplication metadata fields if provided
    if dedup_metadata:
        fieldnames.update(dedup_metadata.keys())

    fieldnames = sorted(fieldnames)

    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for contact in contacts:
            row = dict(contact)  # Copy to avoid modifying original
            if dedup_metadata:
                row.update(dedup_metadata)
            writer.writerow(row)


def add_dedup_metadata(
    contacts: list[dict[str, Any]], original_count: int, deduped_count: int
) -> dict[str, Any]:
    """Generate deduplication metadata."""
    return {
        "original_contact_count": original_count,
        "deduplicated_contact_count": deduped_count,
        "duplicates_removed": original_count - deduped_count,
        "export_timestamp": str(datetime.now()),
    }
