import os
from flask import Flask, json, jsonify, render_template, request, redirect, flash
from docx import Document
import pdfplumber
import re
from typing import List, Dict, Tuple, Optional, Any
import ollama
from flask import json


app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def extract_text_from_file(filename: str) -> str:
    if filename.endswith('.docx'):
        return extract_text_from_docx(filename)
    elif filename.endswith('.pdf'):
        return extract_text_from_pdf(filename)
    elif filename.endswith('.txt'):
        return extract_text_from_txt(filename)
    raise ValueError(f"Unsupported file type: {filename}")

def extract_text_from_docx(filename: str) -> str:
    doc = Document(filename)
    full_text = [para.text for para in doc.paragraphs]
    return '\n'.join(full_text)

def extract_text_from_pdf(filename: str) -> str:
    with pdfplumber.open(filename) as pdf:
        return ''.join(page.extract_text() for page in pdf.pages)

def extract_text_from_txt(filename: str) -> str:
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

def extract_interview_data(text: str) -> List[Dict[str, str]]:
    interview_data = []
    speaker_pattern = re.compile(
        r"(\w+ \w+|\w+)\s+(\d+:\d+)\s*(.*?)(?=\n\w+ \w+|\n\w+|\Z)",
        re.DOTALL | re.IGNORECASE
    )
    matches = speaker_pattern.findall(text)
    for speaker, timestamp, line in matches:
        interview_data.append({
            "speaker": speaker.strip(),
            "time": timestamp.strip(),
            "text": line.strip()
        })
    return interview_data

def process_interview_data(interview_data: List[Dict[str, str]]) -> str:
    formatted_transcript = "\n".join(
        [f"{item['speaker']} ({item['time']}): {item['text']}" for item in interview_data]
    )
    return formatted_transcript



def evaluate_with_llm(transcript: str, job_title: str, user_prompt: Optional[str] = None) -> Dict[str, Any]:
    base_prompt = f"""
    You are an expert interviewer evaluating a candidate for the {job_title} position.
    
    Analyze the following interview transcript and generate a **well-structured, professional email** to the hiring manager.
    
    - Identify relevant evaluation topics based on the discussion.
    - Provide a rating (out of 5) for each identified topic 
    - Give an overall performance rating.
    - Clearly summarize the candidate’s strengths, weaknesses, and hiring recommendation.
    
    **Transcript:**
    {transcript}

    

    **Output:** Return only the email in a structured format. **Do not include any additional text or explanations.**
    """

    final_prompt = base_prompt
    if user_prompt:
        final_prompt += f"\n\nAdditional Instructions: {user_prompt}"

    try:
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": final_prompt}],
            options={"temperature": 0.5}
        )
        llm_output = response['message']['content']
        return {"email": llm_output}  # Return only the email content

    except Exception as e:
        return {"error": f"Error during LLM evaluation: {str(e)}"}


import json

import re
import json

def parse_llm_output(llm_output: str) -> Dict[str, Any]:
    try:
        # Extract only JSON using regex
        json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if json_match:
            llm_output = json_match.group(0)
        else:
            return {"error": "No JSON found in LLM response."}
        
        parsed_data = json.loads(llm_output)
        
        # Validate required keys
        required_keys = {"topic_evaluations", "overall_rating", "email"}
        if not required_keys.issubset(parsed_data.keys()):
            return {"error": "LLM response missing required fields."}

        return parsed_data
    
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format received from LLM."}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
def index() -> str:
    email_content: Optional[str] = None
    user_prompt: Optional[str] = None
    topic_evaluations: Optional[dict] = None
    overall_rating: Optional[str] = None

    if request.method == "POST":
        if 'file' not in request.files:
            flash("No file part")
            return redirect(request.url)
        file = request.files['file']
        user_prompt = request.form.get("prompt")
        if not file or file.filename == '':
            flash("No selected file")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            try:
                filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filename)
                text = extract_text_from_file(filename)
                interview_data = extract_interview_data(text)
                formatted_transcript = process_interview_data(interview_data)
                llm_result = evaluate_with_llm(formatted_transcript, "default_job_title", user_prompt)
                if "error" in llm_result:
                    flash(llm_result["error"])
                    email_content = str(llm_result)
                else:
                    email_content = llm_result.get("email")
                    topic_evaluations = llm_result.get("topic_evaluations")
                    overall_rating = llm_result.get("overall_rating")
            except Exception as e:
                flash(f"An error occurred: {str(e)}")
                email_content = "Error processing file."
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
        else:
            flash("Unsupported file format.")
            return redirect(request.url)
    return render_template("index.html", email_content=email_content, overall_rating=overall_rating)

if __name__ == "__main__":
    app.run(debug=True)