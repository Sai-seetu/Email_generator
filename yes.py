import os
from flask import Flask, jsonify, render_template, request, redirect, flash
from docx import Document
import pdfplumber
import re
import json
import ollama

app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    return '\n'.join(para.text for para in doc.paragraphs)

def extract_text_from_pdf(filename: str) -> str:
    with pdfplumber.open(filename) as pdf:
        return ''.join(page.extract_text() for page in pdf.pages if page.extract_text())

def extract_text_from_txt(filename: str) -> str:
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

def extract_interview_data(text: str):
    interview_data = []
    pattern = re.compile(r"(\w+ \w+|\w+)\s+(\d+:\d+)\s*(.*?)(?=\n\w+ \w+|\n\w+|\Z)", re.DOTALL)
    matches = pattern.findall(text)
    for speaker, timestamp, line in matches:
        interview_data.append({"speaker": speaker.strip(), "time": timestamp.strip(), "text": line.strip()})
    return interview_data

def process_interview_data(interview_data):
    return "\n".join([f"{item['speaker']} ({item['time']}): {item['text']}" for item in interview_data])

    
    
def handle_test_file(test_file):
    if test_file and test_file.filename != "":
        file_path = os.path.join(UPLOAD_FOLDER, "test_" + test_file.filename)
        test_file.save(file_path)
        return file_path
    return None

def evaluate_with_llm(transcript: str, test_content: str, job_title: str, user_prompt=None):
    prompt = f"""
    You are an expert interviewer evaluating a candidate for the {job_title} position.
    Analyze the following interview transcript and test results, then generate a professional evaluation email.

    **Interview Transcript(Summarize before analyzing):**
    {transcript}

    **Test Responses(Summarize before analyzing):**
    {test_content}

    The email should:
    - Summarize strengths and weaknesses.
    - Provide ratings for key evaluation topics.
    - Give an overall performance rating.
    - Offer a clear hire/no-hire recommendation.

    Output the email only, no extra text.
    """
    if user_prompt:
        prompt += f"\n\nAdditional Instructions: {user_prompt}"
    try:
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.5}
        )
        return {"email": response['message']['content']}
    except Exception as e:
        return {"error": f"Error during LLM evaluation: {str(e)}"}

@app.route("/", methods=["GET", "POST"])
def index():
    email_content = None
    overall_rating = None
    
    if request.method == "POST":
        if 'file' not in request.files or 'test_file' not in request.files:
            flash("Both interview and test files are required.")
            return redirect(request.url)

        file = request.files['file']
        test_file = request.files['test_file']
        user_prompt = request.form.get("prompt")

        if not file.filename or not test_file.filename:
            flash("Both files must be selected.")
            return redirect(request.url)

        if allowed_file(file.filename) and allowed_file(test_file.filename):
            try:
                # Save and process interview file
                interview_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(interview_path)
                interview_text = extract_text_from_file(interview_path)
                interview_data = extract_interview_data(interview_text)
                formatted_transcript = process_interview_data(interview_data)

                # Save and process test file
                test_file_path = handle_test_file(test_file)
                test_text = extract_text_from_file(test_file_path) if test_file_path else ""

                # Evaluate with LLM
                
                llm_result = evaluate_with_llm(formatted_transcript, test_text, "default_job_title", user_prompt)

                if "error" in llm_result:
                    flash(llm_result["error"])
                    email_content = str(llm_result)
                else:
                    email_content = llm_result.get("email")

            except Exception as e:
                flash(f"An error occurred: {str(e)}")
                email_content = "Error processing file."

            finally:
                if os.path.exists(interview_path):
                    os.remove(interview_path)
                if test_file_path and os.path.exists(test_file_path):
                    os.remove(test_file_path)

        else:
            flash("Unsupported file format.")
            return redirect(request.url)
    
    return render_template("index.html", email_content=email_content, overall_rating=overall_rating)

if __name__ == "__main__":
    app.run(debug=True)
