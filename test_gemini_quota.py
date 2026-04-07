import os
import vertexai
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv

def test_model_quota():
    load_dotenv()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "vantage-ai-project")
    location = "global"
    model_name = "gemini-3.1-flash-lite-preview"
    
    print(f"--- Testing Model: {model_name} in {project_id} ---")
    
    try:
        vertexai.init(project=project_id, location=location)
        model = GenerativeModel(model_name)
        
        print("Sending test prompt...")
        response = model.generate_content("Hello, this is a quota test. Are you online?")
        
        print("\n--- SUCCESS ---")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print("\n--- FAILURE ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        
        if "429" in str(e):
            print("\n💡 ADVICE: You have hit the Rate Limit (Quota) for this specific model.")
            print("Try switching to 'gemini-1.5-flash' which has higher limits.")

if __name__ == "__main__":
    test_model_quota()
