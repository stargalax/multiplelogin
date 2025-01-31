from flask import Flask, render_template, request, redirect, url_for, abort, send_file
import firebase_admin
from firebase_admin import credentials, firestore
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)

# Initialize Firebase
#cred = credentials.Certificate('nursebot.json') 
firebase_credentials_path = os.getenv('VARIABLE')  # 'VARIABLE' is the key in .env

if not firebase_credentials_path or not os.path.exists(firebase_credentials_path):
    raise FileNotFoundError(f"Firebase credentials file '{firebase_credentials_path}' not found.")

# Initialize Firebase with the credentials
cred = credentials.Certificate(firebase_credentials_path)
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nurse_id = request.form.get('nurse_id')
        
        # Access the 'NURSE' collection and document
        nurse_ref = db.collection('NURSE').document('nurse_ids')  # Ensure this matches your document ID
        nurse_data = nurse_ref.get()

        if nurse_data.exists:
            # If document exists, get the data
            nurse_data = nurse_data.to_dict()
            print(f"Retrieved nurse data: {nurse_data}")  # Debugging line

            # Check if 'nid' exists and contains the submitted nurse_id
            if nurse_data and 'nid' in nurse_data:
                print(f"Checking if {nurse_id} is in {nurse_data['nid']}")  # Debugging line
                if nurse_id.strip() in nurse_data['nid']:  # Ensure nurse_id is in the 'nid' field
                    return redirect(url_for('dashboard', nurse_id=nurse_id))
                else:
                    print(f"Nurse ID {nurse_id} not found in 'nid'.")  # Debugging line
                    return render_template('login.html', message="Access Denied: Nurse ID not found.", error=True)
            else:
                print("No 'nid' field found in document.")  # Debugging line
                return render_template('login.html', message="Access Denied: Invalid nurse data structure.", error=True)
        else:
            print("Nurse document not found.")  # Debugging line
            return render_template('login.html', message="Access Denied: Nurse document not found.", error=True)

    return render_template('login.html')

#working---> shows all records!
'''
@app.route('/dashboard', methods=['GET'])
def dashboard():
    try:
        nurse_id = request.args.get('nurse_id')  # Get nurse_id from URL parameters
        # Retrieve all patient data from Firestore
        patients_ref = db.collection('PATIENTS')
        patients = patients_ref.stream()

        nurse_data = []
        for patient in patients:
            patient_data = patient.to_dict()
            patient_data['id'] = patient_data.get('patient_id', 'N/A')  # Fetch 'patient_id' or default to 'N/A'
            patient_data['name'] = patient_data.get('subject_name', '')  # Fetch 'subject_name' or default to 'N/A'
            patient_data.pop('responses', None)
            print(patient_data)
            conclusion = patient_data.get('conclusion', '')
            if conclusion == "Unconcluded":
                patient_data['status'] = "Unconcluded"
                patient_data['can_download_pdf'] = False  # Disable PDF download
            elif conclusion == "Eligible":
                patient_data['status'] = "Eligible"
                patient_data['can_download_pdf'] = True  # Enable PDF download
            elif conclusion == "Excluded":
                patient_data['status'] = "Excluded"
                patient_data['can_download_pdf'] = True  # Enable PDF download

            nurse_data.append(patient_data)

    except Exception as e:
        print(f"Error retrieving data from Firestore: {e}")
        nurse_data = [{"Error": "Could not retrieve data"}]

    return render_template('dashboard.html', data=nurse_data, nurse_id=nurse_id)
'''
@app.route('/dashboard', methods=['GET'])
def dashboard():
    try:
        nurse_id = request.args.get('nurse_id')  # Get nurse_id from URL parameters
        
        # Retrieve all patient data from Firestore where nurse_id matches
        patients_ref = db.collection('PATIENTS')
        patients = patients_ref.where('nurse_id', '==', nurse_id).stream()  # Filter by nurse_id
        nurse_data = []
        for patient in patients:
            patient_data = patient.to_dict()
            print(f"Patient data for {nurse_id}: {patient_data}")  # Log patient data for debugging

            # Continue processing as before
            patient_data['id'] = patient_data.get('patient_id', 'N/A')
            patient_data['name'] = patient_data.get('subject_name', '')
            patient_data.pop('responses', None)

            conclusion = patient_data.get('conclusion', '')
            if conclusion == "Unconcluded":
                patient_data['status'] = "Unconcluded"
                patient_data['can_download_pdf'] = False
            elif conclusion == "Eligible":
                patient_data['status'] = "Eligible"
                patient_data['can_download_pdf'] = True
            elif conclusion == "Excluded":
                patient_data['status'] = "Excluded"
                patient_data['can_download_pdf'] = True

            nurse_data.append(patient_data)

        if not nurse_data:
            message = "Please enter details using the chatbot and access the report here."
            return render_template('dashboard.html', message=message)

        return render_template('dashboard.html', data=nurse_data, nurse_id=nurse_id)


    except Exception as e:
        print(f"Error retrieving data from Firestore: {e}")
        nurse_data = [{"Error": "Could not retrieve data"}]

    return render_template('dashboard.html', data=nurse_data, nurse_id=nurse_id)

@app.route('/download_patient_report/<patient_id>/<nurse_id>', methods=['GET'])
def download_patient_report(patient_id, nurse_id):
    try:
        # Retrieve patient data from Firestore
        patient_ref = db.collection('PATIENTS').document(patient_id)
        patient_data = patient_ref.get()

        if patient_data.exists:
            patient_data = patient_data.to_dict()
            conclusion = patient_data.get('conclusion', '')
            if conclusion == "Unconcluded":
                # Don't generate the PDF and just return a message
                return redirect(url_for('dashboard', nurse_id=nurse_id))  # Redirect back to dashboard if unconcluded

            # Generate the PDF and send the file
            pdf_filename = generate_pdf(patient_data, nurse_id, patient_id)
            return send_file(pdf_filename, as_attachment=True, download_name=f"patient_{patient_id}_report.pdf")

        else:
            # Patient not found in Firestore
            return abort(404, f"Patient with ID {patient_id} not found.")
    except Exception as e:
        print(f"Error generating PDF: {e}")
        abort(500, "An error occurred while generating the PDF.")
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas
import os

def generate_pdf(patient_data, nurse_id, patient_id):
    # Ensure the 'Downloads' folder exists
    download_dir = 'Downloads'  # Folder name with a capital 'D'
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)  # Create the directory if it doesn't exist

    # Path to save the PDF file
    pdf_filename = os.path.join(download_dir, f"patient_{patient_id}_report.pdf")
    
    try:
        c = canvas.Canvas(pdf_filename, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica", 14)  # Increased font size to 14

        # Creating styles for alignment
        styles = getSampleStyleSheet()
        style_normal = styles["Normal"]
        style_normal.fontName = "Helvetica"
        style_normal.fontSize = 14  # Increased font size to 14

        # Adding content to the PDF using Paragraph for better alignment
        c.drawString(100, height - 50, f"Patient Report for ID: {patient_id}")
        c.drawString(100, height - 70, f"Nurse ID: {nurse_id}")
        c.drawString(100, height - 90, f"Name: {patient_data.get('patient_name', 'N/A')}")
        c.drawString(100, height - 110, f"Patient ID: {patient_id}")

        conclusion = patient_data.get('conclusion', '')
        
        # List of exclusion questions mapped to their IDs in Firestore
        exclusion_questions = {
            "exclusion_31": "Does the subject have any hypersensitivity or allergic reactions to B-lactam antibiotics?",
            "exclusion_32": "Does the subject have any pre-existing neurological disorders?",
            "exclusion_33": "Has the subject received any prior treatment with antibiotics effective against carbapenem-resistant Gram-negative bacteria?",
            "exclusion_34": "Does the subject have severe sepsis or septic shock requiring high-level vasopressors?",
            "exclusion_35": "Does the subject have a Cr <30 mL/min at screening?",
            "exclusion_36": "Is there a history of chronic kidney disease?",
            "exclusion_37": "Are there any co-infections with specific pathogens (e.g., Gram-positive bacteria, Aspergillosis)?",
            "exclusion_38": "Is there a central nervous system infection present?",
            "exclusion_39": "Does the subject have infections requiring extended antibiotic treatment (e.g., bone infections)?",
            "exclusion_40": "Does the subject have cystic fibrosis or severe bronchiectasis?",
            "exclusion_41": "Does the subject have severe neutropenia?",
            "exclusion_42": "Has the subject tested positive for pregnancy or is lactating?",
            "exclusion_43": "Does the subject have a Sequential Organ Failure Assessment (SOFA) score greater than 6?",
            "exclusion_44": "Is there any condition that might compromise safety or data quality according to the investigator?",
            "exclusion_45": "Has the subject received any investigational drug or device within 30 days prior to entry?",
            "exclusion_46": "Has the subject been previously enrolled in this study or received WCK 5222?",
            "exclusion_47": "Is the subject receiving dialysis, continuous renal replacement therapy, or ECMO?",
            "exclusion_48": "Does the subject have myasthenia gravis or any other neuromuscular disorder?",
            "exclusion_49": "Does the subject have severe liver disease?"
        }

        # Check if the patient is excluded
        if conclusion == "Excluded":
            exclusion_criteria_violations = []
            
            # Get the responses from the 'responses' field
            responses = patient_data.get('responses', {})

            # Check the responses for each exclusion question and add to the list if 'yes'
            for exclusion_key, exclusion_question in exclusion_questions.items():
                response = responses.get(exclusion_key, "").lower()
                if response == "yes":
                    exclusion_criteria_violations.append(f"Question: {exclusion_question}")

            # If there are any violations, add them to the PDF
            if exclusion_criteria_violations:
                c.drawString(100, height - 140, "Exclusion Criteria Violations:")
                y_position = height - 160

                # Using Paragraph for better text wrapping
                for violation in exclusion_criteria_violations:
                    para = Paragraph(violation, style_normal)
                    para_width = width - 200  # Set max width to fit the page
                    para_height = para.wrap(para_width, 100)[1]  # Wrap the text
                    para.drawOn(c, 100, y_position - para_height)
                    y_position -= (para_height + 10)  # Adjust y-position after each paragraph

        elif conclusion == "Eligible":
            para = Paragraph("Patient is eligible.", style_normal)
            para_width = width - 200
            para_height = para.wrap(para_width, 100)[1]
            para.drawOn(c, 100, height - 140 - para_height)

        # Save the PDF
        c.save()
        return pdf_filename
    except Exception as e:
        print(f"Error generating PDF: {e}")
        raise


if __name__ == '__main__':
    app.run(debug=True)
