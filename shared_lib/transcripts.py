# shared_lib/transcripts.py
import csv
import io

def generate_csv_transcript(messages: list) -> str:
    """
    Generates a CSV transcript from a list of messages.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["author", "content", "timestamp"])
    for message in messages:
        writer.writerow([message["author"], message["content"], message["timestamp"]])
    return output.getvalue()
