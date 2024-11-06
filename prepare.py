import os
import requests
import sys
import json
from dotenv import load_dotenv
import re
import hashlib
from ollama import generate
from openai import OpenAI

load_dotenv()
client = OpenAI()

def llm(prompt, log=False, user_log=False):
    output = ""
    if user_log:
        print(f"USER>{prompt}")
    if log:
        print(f"{model}>", end='')
    for part in generate(model, prompt, stream=True):
        output += part['response']
        if log:
            print(part['response'], end='', flush=True)
    if log:
        print()
    return output

model = "llama3.2"
context_size = 7500

journal_dir = sys.argv[1]
output_dir = os.path.join('.', "prepared")
aipics_dir = os.path.join('.', "aipics")
mapping_file_path = os.path.join('.', "prepared", "name_address_mapping.json")

# Create output directories if they don't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
if not os.path.exists(aipics_dir):
    os.makedirs(aipics_dir)

print(f"looking for journal entries in {journal_dir}")

matching_files = []

# Create a hash of the prompt + matching_files to use for saving/restoring progress
def get_hash_key(prompt, matching_files):
    combined = prompt + "".join(matching_files)
    return hashlib.md5(combined.encode()).hexdigest()

# Load saved name/address mapping if available
name_address_mapping = {}
if os.path.exists(mapping_file_path):
    with open(mapping_file_path, 'r') as f:
        name_address_mapping = json.load(f)

try:
    files_and_dirs = sorted(
        os.listdir(journal_dir),
        key=lambda x: os.path.getmtime(os.path.join(journal_dir, x))
    )
    formatted = " ".join(files_and_dirs)

    while True:
        output = ""

        prompt = f'{formatted}. Looking at the output of this ls command, come up with a regex that will match journal entries. Keep it simple. Do not explain, just give the regex.'
        llm(prompt)
        output = output.replace('`', '')

        # Use hardcoded regex pattern
        output = '[12].*'
        pattern = re.compile(output)

        # Filter files and directories that match the regex pattern
        matching_files = [f for f in files_and_dirs if re.match(pattern, f)]
        print(f"{len(matching_files)} matched out of {len(files_and_dirs)} total ")
        if len(matching_files) == 0:
            print('Trying again')
        else:
            break
except FileNotFoundError:
    print("Directory not found. Please check the path and try again.")

print(f"Analyzing {len(matching_files)} journal files")

# Generate a unique key for this session
session_key = get_hash_key("SensitiveContentFilter", matching_files)

# Load saved progress if available
modified_files = {}

# Function to replace names and addresses consistently using LLM
def replace_sensitive_info(text, mapping):
    # Ask the LLM to identify names and addresses in the text and suggest replacements
    prompt = f'"{text}"\n Identify names of people and addresses in the text and suggest replacements. Do not suggest replacements for anything other than names of people or addresses. Do not explain or discuss, just reply with the suggestions in JSON format, e.g., {{"Alex": "Robert", "Thomas": "Johnny", "original": "replacement" ...}}. '
    response = llm(prompt)



    
    # Try to parse the JSON response, retry if necessary
    suggested_mappings = {}
    tries = 0
    while tries < 5:
        try:
            suggested_mappings = json.loads(response)
            if isinstance(suggested_mappings, dict):
                # just ask it again to make sure?
                keys = '","'.join(suggested_mappings.keys())
                #filtered_keys = llm(f"Filter out words that are not people names or addresses from [\"{keys}\"]. Do not explain or discuss anything, only respond with a JSON array of names or addresses, e.g., [\"John\", \"Bryan\",...]", True, True)
                filtered_keys = llm(f"Return only a JSON array of people names or addresses from the input list: [\"{keys}\"]. No explanations or additional text, only respond with the JSON array.", True, True)

                filtered_keys = json.loads(filtered_keys)
                actual = {}
                for k in filtered_keys:
                    if k in suggested_mappings:
                        actual[k] = suggested_mappings[k]
                suggested_mappings = actual

                break
        except Exception as e:
            print(e)
            response = llm(prompt)
            tries += 1

    if not isinstance(suggested_mappings, dict):
        print(f"Skipping paragraph due to JSON parsing issues: {text[:50]}...")
        return text

    # this is iffy
    # Start with first mapping to stay consistent
    for original, suggested in mapping.items():
        text = text.replace(original, suggested)

    # Update the name/address mapping and replace in the text
    for original, suggested in suggested_mappings.items():
        if isinstance(suggested, str) and original in text:
            if original not in mapping:
                mapping[original] = suggested
            text = text.replace(original, mapping[original])

    return text

def check_for_unsafe(text):
    prompt = f'Is the following text something that deals with extremely harmful content:"{text}"? If it\'s safe, reply with {{"safe": "Y", "replacement_text": ""}}. If it\'s unsafe, rewrite it so that it\'s safe and reply with {{"safe": "N", "replacement_text": "detailed replacement text"}}. Do not discuss, just reply with a JSON object.`'
    response = llm(prompt)
    tries = 0
    while tries < 5:
        tries += 1
        try:
            response_json = json.loads(response)
            if 'safe' in response_json and ('replacement_text' in response_json):
                return text if response_json['safe'] == 'Y' else response_json['replacement_text']
            else:
                print('one was missing')
        except json.JSONDecodeError as e:
            print(e)
            response = llm(prompt)
    return ""
    
for file_path in matching_files:
    with open(journal_dir + '/' + file_path, 'r') as file:
        content = file.read()
        date = os.path.basename(file_path).replace(".txt", "")
        print(f"reading {os.path.basename(file_path)}")

        # Split content into paragraphs
        paragraphs = content.split("\n\n")
        modified_paragraphs = []

        for paragraph in paragraphs:
            # Replace sensitive information using LLM
            print('original', paragraph)
            modified_paragraph = replace_sensitive_info(paragraph, name_address_mapping)
            # try commenting this out
            modified_paragraph = check_for_unsafe(modified_paragraph)
            print('modified', modified_paragraph)
            modified_paragraphs.append(modified_paragraph)

        # Save modified paragraphs as a text file
        modified_content = "\n\n".join(modified_paragraphs)
        output_file_path = os.path.join(output_dir, f"{date}-modified.txt")
        with open(output_file_path, 'w') as output_file:
            output_file.write(modified_content)

        # Keep track of modified files
        modified_files[date] = output_file_path

    # Save name/address mapping to file
    with open(mapping_file_path, 'w') as f:
        json.dump(name_address_mapping, f, indent=4)

print(f"Modified files saved in '{output_dir}'")
