import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
import random
# Download required NLTK data
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('stopwords')
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper import setup_script_logging
logger = setup_script_logging(__name__)
# Read styles from the default_styles.txt file
styles = []
try:
    with open('Styles/default_styles.txt', 'r', encoding='utf-8') as styles_file:
        in_used_styles_section = False
        for line in styles_file:
            line = line.strip()
            if line == "# Used Styles":
                in_used_styles_section = True
                continue
            elif in_used_styles_section:
                if not line:  # Stop at the first blank line
                    break
                styles.append(line)
    logger.info(f"Styles: {styles}")
except FileNotFoundError:
    # Fallback to default styles if file not found
    styles = [
        "Realistic/Photorealistic",
        "Cinematic",
        "Illustrative/Cartoon",
        "Anime/Manga",
        "Comic Book"
    ]
    logger.info("Styles file not found, using default styles instead.")



def extract_key_info(text):
    # Tokenize the text into sentences
    sentences = sent_tokenize(text)
    
    # Use the first sentence as it often contains the most important information
    if not sentences:
        return ""
    first_sentence = sentences[0]
    
    # Tokenize words and remove stopwords
    stop_words = set(stopwords.words('english'))
    words = word_tokenize(first_sentence)
    filtered_words = [word.lower() for word in words if word.isalnum() and word.lower() not in stop_words]
    
    # Get part-of-speech tags
    pos_tags = pos_tag(filtered_words)
    
    # Extract nouns and verbs
    key_words = [word for word, pos in pos_tags if pos.startswith('NN') or pos.startswith('VB')]
    
    return ' '.join(key_words)

  
def create_image_prompt(text, style):
    key_info = extract_key_info(text)
    prompt = f"{key_info}, {style} style"
    return prompt





def main():
    prompts = []
    with open('processed.txt', 'r', encoding='utf-8') as news_file:
        news_text = news_file.read()

    with open('promptCheck.txt', 'w', encoding='utf-8') as file:
        paragraphs = [p for p in news_text.split('\n\n') if p.strip()]
        for paragraph in paragraphs:
            if paragraph.startswith(' ') or paragraph.startswith(',') or (paragraph is None):
                continue
            image_prompt = create_image_prompt(paragraph, style=random.choice(styles))
            if image_prompt[0]!=',' or image_prompt[0]!=' ':
                file.write(image_prompt + '\n')
                prompts.append(image_prompt)
            else:
                print("Prompt starts with a comma, skipping this prompt.")
                continue
            logger.info(image_prompt)

    return prompts if prompts else None

if __name__ == "__main__":
    main()