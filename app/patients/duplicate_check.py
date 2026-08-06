from difflib import SequenceMatcher
from app.patients.models import Patient
from app.patients.security import mask_aadhaar

def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculates fuzzy similarity between two names (0.0 to 1.0)"""
    if not name1 or not name2:
        return 0.0
    n1 = name1.strip().lower()
    n2 = name2.strip().lower()
    return SequenceMatcher(None, n1, n2).ratio()


def check_for_duplicates(first_name, last_name, dob, mobile, aadhaar_raw=None):
    """
    Scans database for possible duplicate patient records.
    Returns a tuple: (is_duplicate_flag, list_of_matches)
    
    Match dictionary format:
    {
        'patient': Patient,
        'similarity_score': float, # 0 to 100%
        'match_reasons': list of strings
    }
    """
    full_name_intake = f"{first_name} {last_name}".strip().lower()
    existing_patients = Patient.query.all()
    potential_matches = []

    clean_new_mobile = str(mobile).strip().replace('-', '').replace(' ', '')
    clean_new_aadhaar = str(aadhaar_raw).strip().replace('-', '').replace(' ', '') if aadhaar_raw else ""

    for patient in existing_patients:
        reasons = []
        score = 0.0

        # Check 1: Mobile number exact match
        clean_exist_mobile = str(patient.mobile).strip().replace('-', '').replace(' ', '')
        if clean_new_mobile and clean_exist_mobile and clean_new_mobile == clean_exist_mobile:
            reasons.append("Exact Mobile Number match")
            score += 40.0

        # Check 2: Date of Birth exact match
        if dob and patient.dob and dob == patient.dob:
            reasons.append("Exact Date of Birth match")
            score += 30.0

        # Check 3: Fuzzy Name similarity
        name_sim = calculate_name_similarity(full_name_intake, patient.full_name)
        if name_sim >= 0.80:
            reasons.append(f"High Name Similarity ({int(name_sim * 100)}%)")
            score += 30.0
        elif name_sim >= 0.65:
            reasons.append(f"Moderate Name Similarity ({int(name_sim * 100)}%)")
            score += 15.0

        # Check 4: Aadhaar exact match if provided
        if clean_new_aadhaar and patient.aadhaar_encrypted:
            decrypted_exist_aadhaar = patient.get_decrypted_aadhaar()
            if decrypted_exist_aadhaar and clean_new_aadhaar == decrypted_exist_aadhaar:
                reasons.append("Exact Aadhaar Number match")
                score = 100.0 # Instant 100% match

        # Flag threshold: if score >= 60% or (Aadhaar match or (Mobile match + DOB match))
        if score >= 60.0 or ("Exact Mobile Number match" in reasons and "Exact Date of Birth match" in reasons):
            potential_matches.append({
                'patient': patient,
                'similarity_score': min(int(score), 100),
                'match_reasons': reasons
            })

    # Sort matches by highest similarity score first
    potential_matches.sort(key=lambda x: x['similarity_score'], reverse=True)

    is_duplicate = len(potential_matches) > 0
    return is_duplicate, potential_matches
