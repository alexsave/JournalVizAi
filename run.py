import os
import sys
import json
import glob
import re

from ollama import generate 

def user(text, log=True):
    if (log):
        print(f"USER>{text}")

def llm(prompt, log=True):
    output = ""
    if (log):
        print(f"{model}>", end='')
    for part in generate(model, prompt, stream=True):
        output += part['response']
        if (log):
            print(part['response'], end='', flush=True)
    if (log):
        print()
    return output
    

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
        user(prompt, False)
        print(f"{model}>", end='')
        for part in generate(model, prompt, stream=True):
            output += part['response']
            print(part['response'], end='', flush=True)
        print()
        output = output.replace('`','')

        #lol
        output = '2023-05.*'
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
userPrompt = "What is my favorite restaurant"
user(userPrompt)

# Step 1, filter
filterPrompt = "Does this text talk about a restaurant? Do not explain, just answer Y or N"

filteredParagraphs = []

for file_path in matching_files:
    with open(journal_dir + '/' + file_path, 'r') as file:
        content = file.read()
        date = os.path.basename(file_path).replace(".txt", "")
        print(f"reading {os.path.basename(file_path)}")
        
        # Iffy, could be done by sending to LLM 
        paragraphs = content.split("\n\n")

        for paragraph in paragraphs:
            ask = paragraph + filterPrompt
            user(ask, False)
            answer = llm(ask, False)

            while answer[0] != 'Y' and answer[0] != 'N':
                answer = llm(ask, False)
            if answer[0] == 'Y':
                #print(paragraph)
                #print()
                filteredParagraphs.append(paragraph)

# Step 2, group
def getGroupPrompt(options):
    groupPrompt = f"Which restaurant is this text talking about? Existing options are [{", ".join(options)}], but it doesn't have to be one of these. Do not explain, just reply with the name of the restaurant in JSON format {{ name: [RESTAURANT] }} ."
    return groupPrompt

groups = {}

for paragraph in filteredParagraphs:
    ask = paragraph + getGroupPrompt(groups.keys())
    user(ask, True)
    answer = llm(ask, True)
    formattedAnswer = {}
    while True:
        try:
            formattedAnswer = json.loads(answer)
            break
        except json.JSONDecodeError as e:
            print("Invalid JSON syntax:", e)
            answer = llm(ask, True)

    answer = formattedAnswer['name']

    if answer not in groups:
        groups[answer] = []
    groups[answer].append(paragraph)

for k in groups.keys():
    print(f"{len(groups[k])} entries for {k}")

# Step 3, summarize
# Step 4, rank
# Step 5, answer original question