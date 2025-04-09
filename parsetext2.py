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

styles =[
    "Realistic/Photorealistic",
    "Hyper-Realism",
    "Cinematic",
    "Documentary",
    "Illustrative/Cartoon",
    "Anime/Manga",
    "Comic Book",
    "Disney/Pixar Style",
    "Artistic/Painterly",
    "Impressionism",
    "Surrealism",
    "Abstract",
    "Fantasy/Sci-Fi",
    "Dark Fantasy",
    "Cyberpunk",
    "Medieval Fantasy",
    "Historical/Period",
    "Victorian",
    "Renaissance",
    "Ancient Civilizations",
    "Minimalist/Modern",
    "Flat Design",
    "Geometric",
    "Monochrome",
    "Whimsical/Fantastical",
    "Fairy Tale",
    "Steampunk",
    "Pop Art",
    "Vintage/Retro",
    "1950s Americana",
    "Art Deco",
    "Retro Futurism",
    "Experimental/Conceptual",
    "Glitch Art",
    "Fractal Art",
    "Collage",
    "Mixed Media/Hybrid",
    "Photomontage",
    "3D Render",
    "Pixel Art"
]



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

# Example usage

with open('processed.txt', 'r', encoding='utf-8') as file:
    news_text = file.read()



def main():
    with open('promptCheck.txt', 'w', encoding='utf-8') as file:
        paragraphs = news_text.split('\n\n')
        for paragraph in paragraphs:
            image_prompt = create_image_prompt(paragraph, style=random.choice(styles))
            file.write(image_prompt + '\n')
            print(image_prompt)

    return image_prompt

if __name__ == "__main__":
    main()