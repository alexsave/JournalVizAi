import os
import sys
import json
import glob
import re

from ollama import generate 

model = "llama3.2"

#for part in generate('llama3.2', 'Why is the sky blue?', stream=True):
#  print(part['response'], end='', flush=True)

journal_dir = sys.argv[1]

print(f"looking for journal entries in {journal_dir}")

matching_files = []

try:
    files_and_dirs = sorted(
        os.listdir(journal_dir),
        key=lambda x: os.path.getmtime(os.path.join(journal_dir, x))
    )
    formatted = " ".join(files_and_dirs)

    while True:
        output = ""

        prompt = f'{formatted}. Looking at the output of this ls command, come up with a regex that will match journal entries. Keep it simple. Do not explain, just give the regex.'
        print(f"USER>{prompt}")
        print(f"{model}>", end='')
        for part in generate(model, prompt, stream=True):
            output += part['response']
            print(part['response'], end='', flush=True)
        print()
        output = output.replace('`','')

        output = '[12].*'
        pattern = re.compile(output)
    
    
        # Filter files and directories that match the regex pattern
        matching_files = [f for f in files_and_dirs if re.match(pattern, f)]
        print(f"{len(matching_files)} matched out of {len(files_and_dirs)} total ")
        if (len(matching_files) == 0):
            print('Trying again')
        else: 
            break
except FileNotFoundError:
    "Directory not found. Please check the path and try again."


print(f"Analyzing {len(matching_files)} journal files")

# Ok here we could do some visualization, but that's a whole separate thing. We'll hard code the prompt for now
# Step 1, filter
# Step 2, group
# Step 3, summarize
# Step 4, rank
# Step 5, answer original question