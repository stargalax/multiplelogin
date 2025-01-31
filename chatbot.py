from langchain import LLMChain, PromptTemplate
import time
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, send_file

# Initialize Firebase
cred = credentials.Certificate('nursebot.json')  # Replace with your Firebase credentials file
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Define the inclusion and exclusion criteria questions
inclusion_criteria = [
    "Is the subject aged between 18 and 75 years at Screening?",
    "Has informed consent been obtained?",
    "Is the infection (HABP/VABP ± ccBSI) caused by a suspected or documented carbapenem-resistant Gram-negative pathogen?",
    "Does the subject have CrCL (>30 mL/min)?",

    # HABP/VABP Specific Inclusion Criteria
    "Does the subject have hospital-acquired or ventilator-associated bacterial pneumonia with or without concurrent bloodstream infection?",
    "Does the subject have a new onset or worsening of pulmonary symptoms, such as cough, dyspnea, tachypnea (e.g., respiratory rate > 25 breaths per minute), or expectorated sputum production?",
    "Is there a need for mechanical ventilation or an increase in ventilator support to enhance oxygenation?",
    "Has the subject’s partial pressure of oxygen dropped below 60 mmHg while breathing room air, or has the PaO2/FiO2 ratio worsened?",
    "Is there a new onset or increase in suctioned respiratory secretions?",
    "Does the subject have documented fever (e.g., core body temperature ≥ 38°C) or hypothermia (e.g., core body temperature ≤ 35°C)?",
    "Does the subject have leukocytosis with a WBC count ≥ 10,000 cells/mm³, leukopenia with a WBC count ≤ 4,500 cells/mm³, or more than 15% immature neutrophils (bands) on a peripheral blood smear?",

    # cIAI Specific Inclusion Criteria
    "Does the subject meet specific criteria for cIAI inclusion?",
    "Does the subject have cholecystitis with gangrenous rupture or infection progression beyond the gallbladder wall?",
    "Does the subject have diverticular disease with perforation or abscess?",
    "Does the subject have appendiceal perforation or a peri-appendiceal abscess?",
    "Does the subject have acute gastric or duodenal perforation (if operated on more than 24 hours after perforation)?",
    "Does the subject have traumatic perforation of the intestines (if operated on more than 12 hours after perforation)?",
    "Does the subject have secondary peritonitis (excluding spontaneous peritonitis associated with cirrhosis and chronic ascites)?",
    "Does the subject have an intra-abdominal abscess with evidence of intraperitoneal involvement?",

    # ccBSI Specific Inclusion Criteria
    "Does the subject have one or more positive blood cultures identifying a carbapenem-resistant Gram-negative pathogen that is consistent with the subject’s clinical condition?",
    "Does the subject have signs or symptoms associated with bacteremia?",

    # cUTI or AP Specific Inclusion Criteria
    "Is there a confirmed cUTI or AP with or without concurrent bloodstream infection?",
    "Has the subject had an indwelling urinary catheter or recent instrumentation of the urinary tract (within 14 days prior to Screening)?",
    "Does the subject have urinary retention with 100 mL or more of residual urine after voiding (neurogenic bladder)?",
    "Does the subject have obstructive uropathy (e.g., nephrolithiasis or fibrosis)?",
    "Does the subject have azotemia caused by intrinsic renal disease (BUN and creatinine values greater than normal clinical laboratory values)?",
    "Does the subject present with at least two signs or symptoms: chills, rigors, or warmth associated with fever (temperature ≥ 38°C); flank pain or suprapubic/pelvic pain; nausea or vomiting; dysuria, urinary frequency, or urgency; or costovertebral angle tenderness on physical examination?",
    "Does the subject’s urinalysis show evidence of pyuria, demonstrated by either a positive dipstick analysis for leukocyte esterase or ≥ 10 WBCs/µL in unspun urine, or ≥ 10 WBCs/high-power field in spun urine?",
    "Did the subject have a positive urine culture within 48 hours before WCK 5222 treatment initiation, showing ≥ 10⁵ CFU/mL of a carbapenem-resistant Gram-negative uropathogen?",
    "Is the subject receiving antibiotic prophylaxis for cUTI but presenting with signs and symptoms consistent with an active new cUTI?"
]

exclusion_criteria = [
    "Does the subject have any hypersensitivity or allergic reactions to B-lactam antibiotics?",
    "Does the subject have any pre-existing neurological disorders?",
    "Has the subject received any prior treatment with antibiotics effective against carbapenem-resistant Gram-negative bacteria?",
    "Does the subject have severe sepsis or septic shock requiring high-level vasopressors?",
    "Does the subject have a Cr <30 mL/min at screening?",
    "Is there a history of chronic kidney disease?",
    "Are there any co-infections with specific pathogens (e.g., Gram-positive bacteria, Aspergillosis)?",
    "Is there a central nervous system infection present?",
    "Does the subject have infections requiring extended antibiotic treatment (e.g., bone infections)?",
    "Does the subject have cystic fibrosis or severe bronchiectasis?",
    "Does the subject have severe neutropenia?",
    "Has the subject tested positive for pregnancy or is lactating?",
    "Does the subject have a Sequential Organ Failure Assessment (SOFA) score greater than 6?",
    "Is there any condition that might compromise safety or data quality according to the investigator?",
    "Has the subject received any investigational drug or device within 30 days prior to entry?",
    "Has the subject been previously enrolled in this study or received WCK 5222?",
    "Is the subject receiving dialysis, continuous renal replacement therapy, or ECMO?",
    "Does the subject have myasthenia gravis or any other neuromuscular disorder?",
    "Does the subject have severe liver disease?"
]
# Dictionary mapping keywords to explanations
explanations = {
    "Is the subject aged between 18 and 75 years at Screening?": "The age range of 18 to 75 years is chosen to ensure the study includes adult patients without age-related vulnerabilities that could skew results.",
    "Has informed consent been obtained?": "Informed consent means the patient has agreed to participate in the study with an understanding of the risks and benefits.",
    "Is the infection (HABP/VABP ± ccBSI) caused by a suspected or documented carbapenem-resistant Gram-negative pathogen?": "Carbapenem-resistant Gram-negative pathogens are bacteria that resist a broad spectrum of antibiotics, including carbapenems, and are often serious infections.",
    "Does the subject have CrCL (>30 mL/min)?": "Creatinine clearance (CrCL) measures kidney function by assessing how well creatinine is cleared from the blood, with a CrCL of more than 30 mL/min indicating sufficient kidney function for this study.",

    # HABP/VABP Specific Inclusion Criteria
    "Does the subject have hospital-acquired or ventilator-associated bacterial pneumonia with or without concurrent bloodstream infection?": "Hospital-acquired bacterial pneumonia (HABP) or ventilator-associated bacterial pneumonia (VABP) refers to pneumonia that develops in a healthcare setting or due to ventilation.",
    "Does the subject have a new onset or worsening of pulmonary symptoms, such as cough, dyspnea, tachypnea (e.g., respiratory rate > 25 breaths per minute), or expectorated sputum production?": "Pulmonary symptoms like cough, dyspnea, and tachypnea are indicators of respiratory infection severity.",
    "Is there a need for mechanical ventilation or an increase in ventilator support to enhance oxygenation?": "Mechanical ventilation provides oxygen support for patients who cannot breathe independently or require increased oxygenation.",
    "Has the subject’s partial pressure of oxygen dropped below 60 mmHg while breathing room air, or has the PaO2/FiO2 ratio worsened?": "The PaO2/FiO2 ratio assesses oxygen levels, with lower values indicating potential respiratory compromise.",
    "Is there a new onset or increase in suctioned respiratory secretions?": "Increased or altered secretions can indicate worsening infection or inflammation in the respiratory tract.",
    "Does the subject have documented fever (e.g., core body temperature ≥ 38°C) or hypothermia (e.g., core body temperature ≤ 35°C)?": "Fever or hypothermia can both be indicators of infection, where high temperatures reflect an immune response, and low temperatures could indicate severe infection.",
    "Does the subject have leukocytosis with a WBC count ≥ 10,000 cells/mm³, leukopenia with a WBC count ≤ 4,500 cells/mm³, or more than 15% immature neutrophils (bands) on a peripheral blood smear?": "A high WBC count (leukocytosis) or low count (leukopenia), along with immature neutrophils, indicates infection or immune response imbalance.",

    # cIAI Specific Inclusion Criteria
    "Does the subject meet specific criteria for cIAI inclusion?": "Complicated Intra-Abdominal Infection (cIAI) involves infections in the abdominal organs that spread beyond their original location.",
    "Does the subject have cholecystitis with gangrenous rupture or infection progression beyond the gallbladder wall?": "Cholecystitis with gangrenous rupture means the gallbladder is inflamed and has ruptured, spreading infection to other areas.",
    "Does the subject have diverticular disease with perforation or abscess?": "Diverticular disease with perforation involves small bulging pouches in the digestive tract that tear, leading to infection.",
    "Does the subject have appendiceal perforation or a peri-appendiceal abscess?": "Appendiceal perforation indicates a burst appendix, often requiring surgery and indicating serious infection.",
    "Does the subject have acute gastric or duodenal perforation (if operated on more than 24 hours after perforation)?": "Gastric or duodenal perforation, treated 24 hours post-perforation, indicates severe infection and risk of spreading to other areas.",
    "Does the subject have traumatic perforation of the intestines (if operated on more than 12 hours after perforation)?": "Traumatic perforation occurs due to injury and allows intestinal contents to leak into the abdomen, causing infection.",
    "Does the subject have secondary peritonitis (excluding spontaneous peritonitis associated with cirrhosis and chronic ascites)?": "Secondary peritonitis results from an infection spreading to the peritoneum, the abdominal lining.",
    "Does the subject have an intra-abdominal abscess with evidence of intraperitoneal involvement?": "An intra-abdominal abscess is a collection of pus within the abdomen, indicating a localized infection needing treatment.",

    # ccBSI Specific Inclusion Criteria
    "Does the subject have one or more positive blood cultures identifying a carbapenem-resistant Gram-negative pathogen that is consistent with the subject’s clinical condition?": "Positive blood cultures identifying a resistant pathogen confirm the presence of a bloodstream infection.",
    "Does the subject have signs or symptoms associated with bacteremia?": "Symptoms of bacteremia, or bacteria in the blood, include fever, chills, and other signs of infection.",

    # cUTI or AP Specific Inclusion Criteria
    "Is there a confirmed cUTI or AP with or without concurrent bloodstream infection?": "Complicated Urinary Tract Infection (cUTI) or Acute Pyelonephritis (AP) involve urinary tract infections that are more severe or have spread to the kidneys.",
    "Has the subject had an indwelling urinary catheter or recent instrumentation of the urinary tract (within 14 days prior to Screening)?": "An indwelling urinary catheter is a tube inserted into the bladder for urine drainage, potentially introducing infection.",
    "Does the subject have urinary retention with 100 mL or more of residual urine after voiding (neurogenic bladder)?": "Urinary retention is the inability to completely empty the bladder, possibly due to nerve or muscle issues.",
    "Does the subject have obstructive uropathy (e.g., nephrolithiasis or fibrosis)?": "Obstructive uropathy refers to any blockage in the urinary system, such as kidney stones or scar tissue.",
    "Does the subject have azotemia caused by intrinsic renal disease (BUN and creatinine values greater than normal clinical laboratory values)?": "Azotemia is an increase of urea and creatinine in the blood due to impaired kidney function, often seen in renal diseases.",
    "Does the subject present with at least two signs or symptoms: chills, rigors, or warmth associated with fever (temperature ≥ 38°C); flank pain or suprapubic/pelvic pain; nausea or vomiting; dysuria, urinary frequency, or urgency; or costovertebral angle tenderness on physical examination?": "Symptoms like fever, flank pain, and dysuria (painful urination) are common in urinary tract infections.",
    "Does the subject’s urinalysis show evidence of pyuria, demonstrated by either a positive dipstick analysis for leukocyte esterase or ≥ 10 WBCs/µL in unspun urine, or ≥ 10 WBCs/high-power field in spun urine?": "Pyuria indicates white blood cells in the urine, often suggesting infection.",
    "Did the subject have a positive urine culture within 48 hours before WCK 5222 treatment initiation, showing ≥ 10⁵ CFU/mL of a carbapenem-resistant Gram-negative uropathogen?": "A urine culture with high colony counts of a pathogen indicates an active urinary infection needing treatment.",
    "Is the subject receiving antibiotic prophylaxis for cUTI but presenting with signs and symptoms consistent with an active new cUTI?": "Prophylactic antibiotics for cUTI are used to prevent infection in patients at high risk, but active symptoms may suggest a breakthrough infection."
   
}
IDD = {'1001', '1002', '1003'}  # Example nurse IDs

# Function to find relevant explanation based on question keywords
def get_explanation(question):
    for keyword, explanation in explanations.items():
        if keyword.lower() in question.lower():
            return explanation
    return "No specific information is available for this question."

# Simulate the function to forward a question to the doctor
def forward_to_doctor(question, nurse_id):
    print(f"\nForwarding question to doctor: '{question}' (from Nurse ID: {nurse_id})")
    time.sleep(1)  # Simulate delay
    print("The doctor has been notified.\n")

# Define the function to handle each response
def handle_response(question, nurse_id):
    not_sure_count = 0  # Track consecutive "Not Sure" responses

    while True:
        response = input("Please respond with 'Yes', 'No', or 'Not Sure': ").strip().lower()
        if response == "not sure":
            not_sure_count += 1

            # First "Not Sure" - provide explanation
            if not_sure_count == 1:
                explanation = get_explanation(question)
                print(f"\nExplanation: {explanation}")
                print("\nPlease review the information and respond again.")

            # Second "Not Sure" - forward to doctor and move on
            elif not_sure_count == 2:
                forward_to_doctor(question, nurse_id)
                return "Question forwarded to doctor.", "unconcluded"

        elif response in ["yes", "no"]:
            return "Response recorded.", response
        else:
            print("Invalid response. Please reply with 'Yes', 'No', or 'Not Sure'.")

# Main loop for asking questions
'''
def run_chatbot():
    nurse_id = int(input("Please enter the ID of the nurse: "))
    if nurse_id not in IDD:
        print("You cannot access the chatbot. Please contact the admin.")
        return
    else:
        exclusion_flag = False
        unconcluded_flag = False
        exclusion_reasons = []

        print("Welcome to the Eligibility Criteria Chatbot!")
        subject_name = input("Please enter the name of the subject: ")
        patient_id = input("Please enter the ID of the patient: ")
        print(f"Subject's name recorded: {subject_name}")

        # Prepare the data to be saved in Firestore
        patient_data = {
            'nurse_id': nurse_id,
            'patient_id': patient_id,
            'subject_name': subject_name,
            'responses': {},
            'conclusion': '',
        }

        # Inclusion Criteria
        print("\n--- Inclusion Criteria ---")
        for idx, question in enumerate(inclusion_criteria, start=1):
            print("\n" + question)
            result, response = handle_response(question, nurse_id)
            print(result)
            patient_data['responses'][f'inclusion_{idx}'] = response  # Save response in the dictionary
            if response == "unconcluded":
                unconcluded_flag = True

        # Exclusion Criteria
        print("\n--- Exclusion Criteria ---")
        for idx, question in enumerate(exclusion_criteria, start=len(inclusion_criteria) + 1):
            print("\n" + question)
            result, response = handle_response(question, nurse_id)
            print(result)
            patient_data['responses'][f'exclusion_{idx}'] = response  # Save response in the dictionary
            if response == "unconcluded":
                unconcluded_flag = True
            if response == "yes":
                exclusion_flag = True
                exclusion_reasons.append(question)

        # Final Decision
        if unconcluded_flag:
            patient_data['conclusion'] = "Unconcluded"
        elif exclusion_flag:
            patient_data['conclusion'] = "Excluded"
        else:
            patient_data['conclusion'] = "Eligible"

        # Store the patient data in Firestore
        patients_ref = db.collection('PATIENTS')
        patients_ref.add(patient_data)  # Add patient data as a new document

        print("Chatbot has finished recording responses and the data has been stored.")

# Run the chatbot
run_chatbot()
'''
def run_chatbot():
    nurse_id = input("Please enter the ID of the nurse: ")
    if nurse_id not in IDD:
        print("You cannot access the chatbot. Please contact the admin.")
        return
    else:
        exclusion_flag = False
        unconcluded_flag = False
        exclusion_reasons = []

        print("Welcome to the Eligibility Criteria Chatbot!")
        subject_name = input("Please enter the name of the subject: ")
        patient_id = input("Please enter the ID of the patient: ")
        print(f"Subject's name recorded: {subject_name}")

        # Prepare the data to be saved in Firestore
        patient_data = {
            'nurse_id': nurse_id,
            'patient_id': patient_id,
            'subject_name': subject_name,
            'responses': {},
            'conclusion': '',
        }

        # Inclusion Criteria
        print("\n--- Inclusion Criteria ---")
        for idx, question in enumerate(inclusion_criteria, start=1):
            print("\n" + question)
            result, response = handle_response(question, nurse_id)
            print(result)
            patient_data['responses'][f'inclusion_{idx}'] = response  # Save response in the dictionary
            if response == "unconcluded":
                unconcluded_flag = True

        # Exclusion Criteria
        print("\n--- Exclusion Criteria ---")
        for idx, question in enumerate(exclusion_criteria, start=len(inclusion_criteria) + 1):
            print("\n" + question)
            result, response = handle_response(question, nurse_id)
            print(result)
            patient_data['responses'][f'exclusion_{idx}'] = response  # Save response in the dictionary
            if response == "unconcluded":
                unconcluded_flag = True
            if response == "yes":
                exclusion_flag = True
                exclusion_reasons.append(question)

        # Final Decision
        if unconcluded_flag:
            patient_data['conclusion'] = "Unconcluded"
        elif exclusion_flag:
            patient_data['conclusion'] = "Excluded"
        else:
            patient_data['conclusion'] = "Eligible"

        # Store the patient data in Firestore with patient_id as the document ID
        patients_ref = db.collection('PATIENTS')
        patients_ref.document(patient_id).set(patient_data)  # Use patient_id as document ID

        print("Chatbot has finished recording responses and the data has been stored.")

run_chatbot()
