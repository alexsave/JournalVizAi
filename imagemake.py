import os
import time
import re
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

output_dir = os.path.join('.', "prepared")
aipics_dir = os.path.join('.', "aipics")

if not os.path.exists(aipics_dir):
    os.makedirs(aipics_dir)

modified_files = sorted(
    os.listdir(output_dir),
    key=lambda x: os.path.getmtime(os.path.join(output_dir, x))
)

output = '.*-modified.txt'
pattern = re.compile(output)

# Filter files and directories that match the regex pattern
modified_files = [f for f in modified_files if re.match(pattern, f)]

print(modified_files)

for file_path in modified_files:
    with open(output_dir + '/' + file_path, 'r') as modified_file:
        modified_entry = modified_file.read()
        # Create a prompt to generate an image based on the content
        #image_prompt = "Generate a photo based on the following content. Choose a style that you think best suits the text: "
        image_prompt = ""

        max_prompt_length = 4000
        remaining = max_prompt_length - len(image_prompt)

        prompts = []

        pars = modified_entry.split("\n\n")
        current_prompt = ''
        for paragraph in pars:
            if len(paragraph) + len(current_prompt) < remaining:
                current_prompt += paragraph
            else: 
                prompts.append(image_prompt + current_prompt)
                current_prompt = paragraph

        if current_prompt != '':
            prompts.append(current_prompt)
            

        for i, prompt in enumerate(prompts):
            try:
                # reate limit
                time.sleep(12)
                # try commenting this out
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="hd",
                    style="vivid",
                    n=1,
                )
                print(f"created image for {file_path}")
                image_url = response.data[0].url
                image_path = os.path.join(aipics_dir, f"{file_path}{i}.png")
                # Download and save the image to the aipics directory
                # Download and save the image to the aipics directory
                image_data = requests.get(image_url).content
                with open(image_path, 'wb') as image_file:
                    image_file.write(image_data)
            except Exception as e:
                print(e)
                    
    
print(f"Images saved in '{aipics_dir}'")


