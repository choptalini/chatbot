import os
import requests
from pathlib import Path
import tempfile
import shutil
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
from langsmith import traceable

@traceable
def download_infobip_image(media_url: str, temp_dir: Path) -> Path:
    """
    Download image file from Infobip URL to temporary directory.
    """
    load_dotenv()
    api_key = os.getenv("INFOBIP_API_KEY")
    if not api_key:
        raise ValueError("INFOBIP_API_KEY not found in .env file")

    headers = {
        "Authorization": f"App {api_key}",
        "Accept": "image/*" 
    }
    
    response = requests.get(media_url, headers=headers, stream=True, timeout=60)
    response.raise_for_status()

    content_type = response.headers.get('content-type', 'image/jpeg')
    extension = f".{content_type.split('/')[-1]}"
    
    file_path = temp_dir / f"temp_image{extension}"

    with open(file_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    return file_path

@traceable
def analyze_image_from_path(image_path: str) -> str:
    """
    Analyzes an image to determine if it is related to Ecla Smile and teeth whitening.
    """
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    model = genai.GenerativeModel('gemini-2.5-flash')

    prompt = """
    You are an expert AI image analyst for ECLA, a teeth whitening brand.
    Your task is to analyze a single user-uploaded image based on the provided context about ECLA's products.

    --- ECLA PRODUCT KNOWLEDGE BASE ---
    1.  **ECLA® e20 Bionic⁺ Kit**:
        *   **Appearance**: A flagship whitening system. It comes in a box labeled "BIONIC" and "mini clinical grade teeth whitening kit". The key component is a clear, U-shaped LED mouthguard connected by a white cable.
        *   **Purpose**: For professional-level, deep whitening results at home.

    2.  **ECLA® Purple Corrector**:
        *   **Appearance**: A cylindrical, frosted purple bottle with a white pump dispenser. It contains a viscous, dark purple serum. The label clearly says "ECLA® Purple Corrector".
        *   **Purpose**: A color-correcting serum that instantly neutralizes yellow tones on the tooth surface. It's for cosmetic, immediate results, not deep whitening.

    3.  **ECLA® Teeth Whitening Pen**:
        *   **Appearance**: A slim, sleek, silver pen, similar to a mascara tube, with a brush tip applicator. It has the "ECLA" logo on it.
        *   **Purpose**: A portable pen for quick, on-the-go touch-ups of specific spots or for maintaining overall whitening.
    --- END KNOWLEDGE BASE ---

    Now, analyze the user's uploaded image.

    First, determine the primary subject of the image: 'teeth' or 'product'.

    If the image is 'teeth':
    - Provide a detailed analysis of the teeth color, noting any yellow or brown stains.
    - Rate the severity of the staining on a scale of 1 to 10.
    - Output in the following format:
      Image Type: teeth
      Analysis: [Detailed analysis of teeth color and staining.]
      Stain Severity: [Rating from 1 to 10]

    If the image is 'product':
    - Compare the image to the product descriptions in the knowledge base.
    - If it matches one, state the product name.
    - If it doesn't match but seems to be a teeth whitening product, describe it as 'Unknown'.
    - If it's completely unrelated, describe it as 'Unrelated'.
    - Output in the following format:
      Image Type: product
      Product Name: [ECLA® e20 Bionic⁺ Kit/ECLA® Purple Corrector/ECLA® Teeth Whitening Pen/Unknown/Unrelated]
      Description: [A brief description of the product in the image.]

    If the user seems to be asking how to use a product shown in the image:
    - First, identify the product from the image using the knowledge base.
    - Then, provide a concise summary of how a user might use it. (e.g., "The user appears to be asking how to use the Whitening Pen. They should apply the gel directly to their teeth.")
    - Output in the following format:
      Image Type: product_usage
      Product Name: [Identified product name]
      Usage Query: [Brief description of the user's implied question.]

    Analyze the user's image now.
    """

    contents = [prompt]

    uploaded_image = Image.open(image_path)
    contents.append(uploaded_image)
    
    response = model.generate_content(contents)
    return response.text

@traceable
def process_image_from_url(media_url: str) -> str:
    """
    Downloads, analyzes, and then cleans up an image from a URL.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="image_processor_"))
    try:
        image_path = download_infobip_image(media_url, temp_dir)
        analysis_result = analyze_image_from_path(str(image_path))
        return analysis_result
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir) 