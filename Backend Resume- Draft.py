import os
import io
import random
import requests
from flask import Flask, request, render_template, send_file
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import re
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference import ChatCompletionsClient

app = Flask(__name__)

# Constants for Azure credentials
TOKEN = os.environ.get("GITHUB_TOKEN")
ENDPOINT = "https://models.inference.ai.azure.com"  # Adjust this to your Azure endpoint
MODEL_NAME = "DeepSeek-R1"

# Folder containing templates
TEMPLATES_FOLDER = 'resume_templates/'


# Function to remove <think> sections from
def remove_think_section(text):
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)


# Function to improve resume text using AI
def improve_resume_text(text):
    prompt = (
        "Improve the following resume text by fixing grammar errors and enhancing clarity and professional tone. "
        "Return only the corrected text without any additional commentary or internal thought process:\n\n"
        f"{text}"
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
    }

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500
    }

    try:
        response = requests.post(
            f"{ENDPOINT}/openai/deployments/{MODEL_NAME}/completions?api-version=2023-03-15-preview",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            response_data = response.json()
            improved_text = response_data['choices'][0]['message']['content'].strip()
            improved_text = remove_think_section(improved_text)
            return improved_text
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return text
    except Exception as e:
        print(f"Error during AI processing: {e}")
        return text


# Function to randomly pick a PDF template from the resume_templates folder
def get_random_template():
    # Get all .pdf files in the resume_templates folder
    templates = [f for f in os.listdir(TEMPLATES_FOLDER) if f.endswith('.pdf')]
    if not templates:
        raise Exception("No templates found in the resume_templates folder.")

    # Randomly select a template
    selected_template = random.choice(templates)
    template_path = os.path.join(TEMPLATES_FOLDER, selected_template)
    return template_path


# Function to overlay text on the PDF template
def overlay_on_pdf_template(pdf_data, overlay_text):
    """Overlay text on the PDF template."""

    # First, read the original template PDF
    reader = PdfReader(io.BytesIO(pdf_data))
    writer = PdfWriter()

    # Create a temporary PDF to overlay the resume text
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)

    # Position and font styling for the overlay text (adjust as needed)
    c.setFont("Helvetica", 10)
    y_position = 750  # Adjust starting position for text

    # Split the resume text into lines and add to the PDF canvas
    lines = overlay_text.split('\n')
    for line in lines:
        c.drawString(50, y_position, line)  # Adjust coordinates as needed
        y_position -= 12  # Line spacing

    c.save()

    # Move to the beginning of the packet (which contains the overlay text)
    packet.seek(0)
    overlay_pdf = PdfReader(packet)

    # Overlay the newly created PDF onto the original template
    page = reader.pages[0]  # Assuming one-page template, adjust if multi-page
    page.merge_page(overlay_pdf.pages[0])

    # Add the modified page to the writer
    writer.add_page(page)

    # Save the final output PDF
    output_path = "modified_template.pdf"
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Handle form data
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        summary = request.form['summary']
        experience = request.form['experience']
        education = request.form['education']
        skills = request.form['skills']
        ai_fix = request.form.get('ai_fix') == "yes"

        resume_text = (
            f"Name: {name}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\n\n"
            f"Professional Summary:\n{summary}\n\n"
            f"Work Experience:\n{experience}\n\n"
            f"Education:\n{education}\n\n"
            f"Skills:\n{skills}\n"
        )

        if ai_fix:
            improved_text = improve_resume_text(resume_text)
            final_resume = improved_text
        else:
            final_resume = resume_text

        # Fetch a random PDF template
        selected_template_path = get_random_template()

        # Read the selected template
        with open(selected_template_path, 'rb') as f:
            pdf_data = f.read()

        # Overlay the resume data on the PDF template
        modified_pdf_path = overlay_on_pdf_template(pdf_data, final_resume)

        # Send the modified PDF document as an attachment to the user
        return send_file(modified_pdf_path, as_attachment=True)

    return render_template("index.html")


if __name__ == '__main__':
    app.run(debug=True)
