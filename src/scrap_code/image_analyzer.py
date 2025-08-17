import os
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

def analyze_image(image_path):
    """
    Analyzes an image to determine if it is related to Ecla Smile and teeth whitening.

    Args:
        image_path (str): The path to the image to be analyzed.
    """
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt = """
    Please analyze the uploaded image and determine if it is related to teeth whitening and the brand "Ecla Smile". 
    You can search the web for more information about "Ecla Smile".
    Compare the uploaded image with the following reference images to help with the analysis.
    Is the uploaded image a real image of one of the products?
    """

    ecla_images_dir = 'ecla_images'
    image_files = [os.path.join(ecla_images_dir, f) for f in os.listdir(ecla_images_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]

    contents = [prompt]

    # Add reference images
    for image_file in image_files:
        img = Image.open(image_file)
        contents.append(img)

    # Add the image to be analyzed
    uploaded_image = Image.open(image_path)
    contents.append(uploaded_image)
    
    response = model.generate_content(contents)
    print(response.text)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Analyze an image to see if it is related to Ecla Smile.')
    parser.add_argument('image_path', type=str, help='The path to the image to analyze.')
    args = parser.parse_args()

    analyze_image(args.image_path) 