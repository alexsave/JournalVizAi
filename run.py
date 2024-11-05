import os
import sys
import json
import glob
import re
import hashlib

from ollama import generate 


def llm(prompt, log=True, user_log=False):
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

print(f"looking for journal entries in {journal_dir}")

matching_files = []

# Create a hash of the prompt + matching_files to use for saving/restoring progress
def get_hash_key(prompt, matching_files):
    combined = prompt + "".join(matching_files)
    return hashlib.md5(combined.encode()).hexdigest()

# Check if there is a saved progress file
progress_file = "progress.json"
saved_progress = {}
if os.path.exists(progress_file):
    with open(progress_file, 'r') as f:
        saved_progress = json.load(f)

try:
    files_and_dirs = sorted(
        os.listdir(journal_dir),
        key=lambda x: os.path.getmtime(os.path.join(journal_dir, x))
    )
    formatted = " ".join(files_and_dirs)

    while True:
        output = ""

        prompt = f'{formatted}. Looking at the output of this ls command, come up with a regex that will match journal entries. Keep it simple. Do not explain, just give the regex.'
        llm(prompt, False)
        output = output.replace('`', '')

        # Use hardcoded regex pattern
        output = '2023.*'
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
# Ok here we could do some visualization, but that's a whole separate thing. We'll hard code the prompt for now
userPrompt = "What is my favorite restaurant"

print(f"Analyzing {len(matching_files)} journal files")

# Generate a unique key for this session
session_key = get_hash_key(userPrompt, matching_files)

# Load saved progress if available
filteredParagraphs = saved_progress.get(session_key, {}).get("filteredParagraphs", [])

# Step 1, filter
filterPrompt = "Does this text talk about a restaurant? Do not explain, just answer Y or N"

if not filteredParagraphs:
    for file_path in matching_files:
        with open(journal_dir + '/' + file_path, 'r') as file:
            content = file.read()
            date = os.path.basename(file_path).replace(".txt", "")
            print(f"reading {os.path.basename(file_path)}")

            # Split content into paragraphs
            paragraphs = content.split("\n\n")

            for paragraph in paragraphs:
                ask = paragraph + filterPrompt
                answer = llm(ask, False)

                tries = 0
                while answer[0] != 'Y' and answer[0] != 'N':
                    answer = llm(ask, False, False)
                    tries += 1
                    if tries > 5:
                        print(f"Skipping {paragraph}")
                        break

                if answer[0] == 'Y':
                    filteredParagraphs.append(paragraph)

    # Save filtered paragraphs to progress file
    saved_progress[session_key] = {"filteredParagraphs": filteredParagraphs}
    with open(progress_file, 'w') as f:
        json.dump(saved_progress, f)

# Step 2, group
def getGroupPrompt(options):
    # this prompt is iffy, it's too biased towards choosing existing spots
    groupPrompt = f"\n\nWhich restaurant is this text talking about? " + f"It's more likely that the restaurant referred to in this text is not something seen before. Choose carefully if two restaurants are mentioned. Only choose an existing restaurant name option if you're absolutely sure the text is talking about the same restaurant. Do not discuss, just reply with the name of the restaurant in JSON format {{\"name\": \"[name]\", \"explanation\": \"[explanation]\"}}. If you do not format it in JSON, I will have to ask again."
    "Previously seen restaurants: [{', '.join(options)}]. "
    return groupPrompt

groups = saved_progress.get(session_key, {}).get("groups", {})

if not groups:
    for paragraph in filteredParagraphs:
        ask = paragraph + getGroupPrompt(groups.keys())
        answer = llm(ask, True, True)

        tries = 0
        while True:
            tries += 1
            if tries > 5:
                print(f"skipping {paragraph}")
                formattedAnswer = {"name": "None"}
                break
            try:
                formattedAnswer = json.loads(answer)
                if "name" in formattedAnswer:
                    break
            except json.JSONDecodeError as e:
                print("Invalid JSON syntax:", e)
                answer = llm(ask, True)

        restaurant_name = formattedAnswer.get("name")
        if restaurant_name:
            if restaurant_name not in groups:
                # never mind, don't try to spell correct or anything. it just doesn't work
                groups[restaurant_name] = []

            groups[restaurant_name].append(paragraph)

        print("\n\n")

    # Save groups to progress file
    saved_progress[session_key]["groups"] = groups
    with open(progress_file, 'w') as f:
        json.dump(saved_progress, f)

for k in groups.keys():
    print(f"{len(groups[k])} entries for {k}")

# Step 3, summarize

# need to split into context_size/2 because we will then be comparing them in ranking
summary_prompt = f"Summarize the text into {context_size/2} characters. Do not explain, just give the summarized text."

summarized_groups = saved_progress.get(session_key, {}).get("summarized_groups", {})

if not summarized_groups:
    for key in groups.keys():
        all_text = '\n'.join(groups[key])
        answer = all_text
        while len(answer) > context_size/2:
            ask = all_text + summary_prompt
            answer = llm(ask, True)
            
        summarized_groups[key] = answer

    saved_progress[session_key]["summarized_groups"] = summarized_groups
    with open(progress_file, 'w') as f:
        json.dump(saved_progress, f)

# Step 4, rank

def cmp_to_key(mycmp):
    """Convert a cmp= function into a key= function"""
    class K(object):
        __slots__ = ['obj']
        def __init__(self, obj):
            self.obj = obj
        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0
        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
        __hash__ = None
    return K

rank_prompt1 = f"Based on this text, which restaurant do I like more? Your choices are '"
rank_prompt2 = f"'. Do not discuss anything, just reply with the name of the restaurant in JSON format {{\"name\": \"[name]\"}}"

ranked = saved_progress.get(session_key, {}).get("ranked", {})

def compare_text(item1, item2):
    ask = item1[0] + ": " + item1[1] + "\n\n" + item2[0] + ": " + item2[1] + rank_prompt1 + item1[0] + "' or '" + item2[0] + rank_prompt2
    answer = llm(ask, False)
    while answer != item1[0] and answer != item2[0]:
        formattedAnswer = ''
        while True:
            try:
                formattedAnswer = json.loads(answer)
                if "name" in formattedAnswer:
                    break
            except json.JSONDecodeError as e:
                print("Invalid JSON syntax:", e)
                answer = llm(ask, False)
        answer = formattedAnswer['name']

    if answer == item1[0]:
        print(answer + " was chosen over " + item2[0])
        return 1
    if answer == item2[0]:
        print(answer + " was chosen over " + item1[0])
        return -1

if not ranked:
    ranked = sorted(summarized_groups.items(), key=cmp_to_key(compare_text))

    saved_progress[session_key]["ranked"] = ranked
    with open(progress_file, 'w') as f:
        json.dump(saved_progress, f)

for r in ranked:
    print(r[0], len(r[1]))


# Step 5, answer original question

count = len(ranked)

finalPrompt = f"{ranked[count-1][1]}. This is text describing my favorite restaurant, '{ranked[count-1][0]}'. Based on this text, explain why this is my favorite restaurant. Do not argue against it. Be specific and quote the text."
llm(finalPrompt, True, True)

for i in range(count-1):
    j = i+1
    llm(f"{ranked[count-1-j][1]}. This is text describing the restaurant that got ranked number {j+1} out of {count}, '{ranked[count-1-j][0]}'. Based on this text, explain why it got it's ranking. Be specific and quote the text.", True, False)
    print("\n\n\n")



