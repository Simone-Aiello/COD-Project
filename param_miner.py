import requests
import os
import difflib
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich.prompt import Prompt
import random
console = Console()

def create_template_table(header,value):
    table = Table(title=f"Header: {header}, Value: {value}",show_lines=True)
    table.add_column("Original request", style="red", no_wrap=True)
    table.add_column("Modified request", style="green")
    return table

def headers_differs(original,modified):
    if len(original) != len(modified):
        return True
    original_keys = original.keys()
    for k in original_keys:
        if k not in modified.keys():
            return True

    modified_keys = modified.keys()
    for k in modified_keys:
        if k not in original.keys():
            return True
    for key in original_keys:
        if original[key] != modified[key]:
            return True
    return False

def compute_headers_differences(original,modified):
    differences = []
    original_keys = original.keys()
    modified_keys = modified.keys()
    # Keys in original not in modified
    for k in original_keys:
        if k not in modified_keys:
            differences.append((f"{k}:{original[k]}",""))
    # Keys in modified not in original
    for k in modified_keys:
        if k not in original_keys:
            differences.append(("",f"{k}:{modified[k]}"))
    # Keys in both but different values
    for k in original_keys:
        if k in modified_keys and original[k] != modified[k]:
            differences.append((f"{k}:{original[k]}",f"{k}:{modified[k]}"))
    return differences
def compute_body_difference(original,modified):
    differ = difflib.Differ()
    diff = differ.compare(original, modified)
    filtered = [line for line in diff if line.startswith('+') or line.startswith('-')]
    removed_lines = [line for line in filtered if line.startswith('-')]
    added_lines = [line for line in filtered if line.startswith('+')]
    return (removed_lines,added_lines)

def fuzz_headers(url,previous_headers,headers,params):
    cb = random.randint(0,100000)
    original_request = requests.get(f"{url}?cache_buster={cb}",headers=previous_headers,allow_redirects=False)
    cb+=1
    original_content_length = int(original_request.headers.get("Content-Length"))
    original_status_code = original_request.status_code
    original_headers = original_request.headers
    found_headers = []
    for header in track(headers,description='Fuzzing headers...',console=console):
        for param in params:
            table = create_template_table(header.strip(),param.strip())
            at_least_a_difference = False
            previous_headers[header.strip()] = param.strip()
            modified_request = requests.get(f"{url}?cache={cb}",headers=previous_headers,allow_redirects=False)
            modified_content_length = int(modified_request.headers.get("Content-Length"))
            modified_status_code = modified_request.status_code
            modified_headers = modified_request.headers
            cb += 1
            previous_headers.pop(header.strip())
            if original_status_code != modified_request.status_code:
                table.add_row(f"Original status code: {original_status_code}",f"New status code: {modified_status_code}")
            if original_content_length != modified_content_length:
                at_least_a_difference = True
                removed_lines, added_lines = compute_body_difference(original_request.text.split(),modified_request.text.split())
                for row in zip(removed_lines,added_lines):
                    table.add_row(row[0], row[1])
            if headers_differs(original_headers,modified_headers):
                at_least_a_difference = True
                differences = compute_headers_differences(original_headers,modified_headers)
                for d in differences:
                    table.add_row(d[0],d[1])
            if at_least_a_difference:
                console.print(table)
                found_headers.append(header.strip())
                break
    return found_headers

def main(url: str, header_wordlist:str, param_wordlist:str):
    with open(header_wordlist) as f:
        headers = f.readlines()
    with open(param_wordlist) as f:
        params = f.readlines()
    headers = [value.strip() for value in headers]
    params = [value.strip() for value in params]
    found_headers = fuzz_headers(url,{},headers,params)
    console.log(f"Found {found_headers}")
    requested_headers = Prompt.ask("Insert headers to keep (key:value) comma separeted, leave empty to quit: ")
    while requested_headers != "":
        requested_headers = requested_headers.split(',')
        requested_headers = [key.split(':') for key in requested_headers]
        requested_headers = {key[0]: key[1] for key in requested_headers}
        new_header = []
        for h in headers:
            if h not in requested_headers:
                new_header.append(h)
        headers = new_header
        if len(headers) > 0:
            found_headers = fuzz_headers(url,requested_headers,headers,params)
            console.log(f"Found {found_headers}")
            requested_headers = Prompt.ask("Insert headers to keep (key:value) comma separeted, leave empty to quit: ")
        else:
            requested_headers = ""
if __name__ == "__main__":
    typer.run(main)
