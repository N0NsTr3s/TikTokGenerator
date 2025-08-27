import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from googlesearch import search
from openai import OpenAI
import sys
from googletrans import Translator
import asyncio
import subprocess
client = OpenAI(base_url='http://localhost:1234/v1', api_key="Nothing here")

subprocess.run("lms server start")
subprocess.run("lms load cognitivecomputations/Dolphin3.0-Llama3.1-8B-GGUF/Dolphin3.0-Llama3.1-8B-Q3_K_S.gguf --context-length 8096 --gpu max")
def analyze_text_content(text, url):
    print(f"Analyzing text from: {url}")
    # Extract the source: the substring after "https://" until the first "."
    match = re.search(r'https://www.([^\.\/]+)', url)
    if match:
        source = match.group(1)
    else:
        match = re.search(r'https://([^\.\/]+)', url)
        source = match.group(1) if match else "Unknown"
    completions = client.chat.completions.create(
        model="dolphin3.0-llama3.1-8b@q3_k_s",
        messages=[
            {"role": "system", "content": f"Analyze this text from the source {source} and provide the entire article correctly formatted excluding other text that is not article related: {text}, \n Your Output must be in english!"}
        ],
        stream=False
    )
    return source, completions.choices[0].message.content

def extract_all_text(url):
    if not url.startswith("https://"):
        url = "https://" + url
    response = requests.get(url)
    response.raise_for_status()  # Raises an HTTPError for bad responses
    soup = BeautifulSoup(response.text, "html.parser")

    text = " ".join([p.get_text() for p in soup.find_all('p')])
    # Extract sentences that start with a capital letter and end with ., !, or ?
    sentences = re.findall(r'([A-Z][^\.!?]*[\.!?])', text)
    # Remove lines that have less than 5 words
    filtered_sentences = [sentence for sentence in sentences if len(sentence.split()) >= 5]
    print(f"Extracted sentences from {url}: {filtered_sentences}")
    return "\n".join(filtered_sentences)

def is_relevant(text, query):
    # Check if there are at least 3 similar words with at least 3 letters between the text and the query
    query_keywords = set(word for word in query.lower().split() if len(word) >= 3)
    text_words = set(word for word in text.lower().split() if len(word) >= 3)
    common_words = query_keywords.intersection(text_words)
    print(f"Common words: {common_words}")
    return len(common_words) >= 3

def google_search_extract(query, num_results=20):
    # Use google search to get a list of links for the query, excluding YouTube links
    print(f"Searching for: {query}")
    links = [link for link in search(term=query, num_results=num_results, sleep_interval=2) if "youtube.com" not in link and any(len(word) >= 3 and word in link for word in query.split())] # pyright: ignore[reportOperatorIssue]
    print(f"Found {len(links)} links")
    results = {}
    successful_extractions = 0
    with ThreadPoolExecutor(max_workers=len(links)) as executor:
        future_to_url = {executor.submit(extract_all_text, url): url for url in links}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                text = future.result()
                if is_relevant(text, query):
                    results[url] = text
                    successful_extractions += 1
                    print(f"Successfully extracted relevant text from: {url}")
                    with open("sources.txt", "a") as file:
                        file.write(f"{url}\n")
                else:
                    print(f"Irrelevant text from: {url}")
                if successful_extractions >= num_results:
                    break
            except Exception as e:
                results[url] = f"Error: {e}"
                print(f"Failed to extract text from: {url} with error: {e}")
    return {k: v for k, v in results.items() if not v.startswith("Error:")}

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python NewsCheck.py <query>")
        sys.exit(1)

    query = sys.argv[1].strip()

    # Clear the content of sources.txt
    with open("sources.txt", "w") as file:
        file.write(" ")

    with open("processed.txt", "w") as file:
        file.write(" ")
    analysis_results = {}
    try:
        results = google_search_extract(query, num_results=20)
        print("Text extraction complete. Starting text analysis...")

        with ThreadPoolExecutor(max_workers=len(results)) as analysis_executor:
            future_to_url = {
                analysis_executor.submit(analyze_text_content, text, url): url 
                for url, text in results.items()
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    source, analysis = future.result()
                    analysis_results[url] = analysis
                    print(f"\nURL: {url}")
                    print(f"Source: {source}")
                    print("Analysis Result:")
                    print(analysis)
                    print("-" * 80)
                except Exception as e:
                    print(f"An error occurred analyzing {url}: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Initialize conversation history with a system message.
    conversation = [
        {"role": "system", "content": f"You are a helpful objective, assistant that aggregates and analyzes news articles, you also have to ignore or filter the data that has nothing to do with the following sentence, everything that it looks to be subjective to you MAY BE FAKE NEWS: {query}."}
    ]

    # ... After completing analysis for each article, add them as user messages.
    try:
        for url, analysis in analysis_results.items():
            if is_relevant(analysis, query):
                conversation.append({
                    "role": "user",
                    "content": f"Analysis for {url}:\n{analysis}"
                })
            else:
                print(f"Excluding irrelevant analysis for {url}")
    except Exception as e:
        print(f"An error occurred: {e}")
        for url, analysis in analysis_results.items():
            if is_relevant(analysis, query):
                conversation.append({
                    "role": "user",
                    "content": f"Analysis for {url}:\n{analysis}"
                })
            else:
                print(f"Excluding irrelevant analysis for {url}")
    # Ask the model if additional data is needed to verify the correctness of the articles.
    conversation.append({
        "role": "user",
        "content": "Do you need additional data to verify the correctness of the articles? If yes, please say yes on the first line of the response and specify what data is needed as a google search string, if multiples are needed write them one per line without additional text or justification, if no just write no."
    })

    try:
        additional_data_request = client.chat.completions.create(
            model="dolphin3.0-llama3.1-8b@q3_k_s",
            messages=conversation, # type: ignore
            stream=False
        ) # type: ignore
        additional_data_needed = additional_data_request.choices[0].message.content.strip().split('\n')
        print(f"Additional data needed: {additional_data_needed}")

        # If additional data is needed, perform another round of Google searches and analyses.
        if any("yes" in data.lower() for data in additional_data_needed):
            additional_results = {}
            additional_data_needed = [data.strip('"') for data in additional_data_needed[1:] if re.match(r'^\d+\.', data) or data.startswith('-') or '"' in data]
            with ThreadPoolExecutor(max_workers=len(additional_data_needed)) as search_executor:
                future_to_query = {
                    search_executor.submit(google_search_extract, data, num_results=5): data 
                    for data in additional_data_needed
                }
            for future in as_completed(future_to_query):
                additional_query = future_to_query[future]
                try:
                    result = future.result()
                    additional_results.update(result)
                    print(f"Successfully extracted additional data for query: {additional_query}")
                except Exception as e:
                    print(f"Failed to extract additional data for query: {additional_query} with error: {e}")

            print("Additional text extraction complete. Starting additional text analysis...")

            max_workers = max(1, len(additional_results))
            with ThreadPoolExecutor(max_workers=max_workers) as additional_analysis_executor:
                future_to_url = {
                    additional_analysis_executor.submit(analyze_text_content, text, url): url 
                    for url, text in additional_results.items()
                }
                additional_analysis_results = {}
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        source, analysis = future.result()
                        additional_analysis_results[url] = analysis
                        print(f"\nURL: {url}")
                        print(f"Source: {source}")
                        print("Additional Analysis Result:")
                        print(analysis)
                        print("-" * 80)
                    except Exception as e:
                        print(f"An error occurred analyzing {url}: {e}")

            # Append the additional data to the original conversation.
            for url, analysis in additional_analysis_results.items():
                if is_relevant(analysis, additional_query):
                    conversation.append({
                        "role": "user",
                        "content": f"Analysis for {url}:\n{analysis}"
                    })
                else:
                    print(f"Excluding irrelevant additional analysis for {url}")

    except Exception as e:
        print(f"An error occurred: {e}")

    # Finally, add the final request, which now has the context of all previous messages.
    conversation.append({
        "role": "user",
        "content": f"Analyze your previous responses, create a 200-300 words summary and let me know if the content is reliable, fake news, or misinformation for the following title: {query}. Also, provide the main points following this format: Summary:... Overall Assessment:... Fake News Analysis:..., also provide a more accurate point of view of the story."
    })

    try:
        final_response = client.chat.completions.create(
            model="dolphin3.0-llama3.1-8b@q3_k_s",
            messages=conversation, # type: ignore
            stream=False
        ) # type: ignore
        final_output = final_response.choices[0].message.content
        summary_index = final_output.find("Summary:")
        if summary_index != -1:
            final_output = final_output[summary_index:]
        print(final_output)
       
    except Exception as e:
        print(f"An error occurred: {e}")

    translator = Translator()
    async def translate_query():
        translation = await translator.translate(query, dest='en')
        return translation.text

    translated_query = asyncio.run(translate_query())
    # Edit the processed.txt file to erase everything before "Summary:"
    try:
        with open("processed.txt", "r", encoding="utf-8") as file:
            content = file.read()
        
        summary_index = content.find("Summary:")
        if summary_index != -1:
            content = content[summary_index:]
        
        with open("processed.txt", "w", encoding="utf-8") as file:
            file.write(f"{translated_query} ?\n\n{final_output}")
    except Exception as e:
        print(f"An error occurred while editing processed.txt: {e}")
    subprocess.run("lms unload --all")
    subprocess.run("lms server stop")