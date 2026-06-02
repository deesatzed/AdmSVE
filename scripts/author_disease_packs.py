"""One-time authoring tool: write the 22 disease-module condition packs.

Clinical content is hand-transcribed from the deep-research disease modules (standard medicine +
CMS public layer), mapped onto the ConditionEntry schema. recommended_status and confidence_level
are DROPPED (status levers). Provenance per the Research routing:
  - peer_reviewed: asthma (GINA), copd (GOLD)
  - cms_public:    esrd_dialysis (CMS manual)
  - derived_concept (CMS-anchored, no fabricated guideline cites): the remaining 18
All documentation_phrases are cms_public (Two-Midnight / 42 CFR 482.30). Trademark-free.

Run: PYTHONPATH=src python3 scripts/author_disease_packs.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "admission_engine" / "kb" / "data" / "conditions"

# Reusable citation blocks.
CMS_2MID = {"ref_id": "cms_two_midnight", "source": "CMS Two-Midnight Rule (public regulatory layer)", "year": 2013, "locator": "42 CFR 482.30; reasonable-expectation medical-necessity standard"}
CMS_UR = {"ref_id": "cms_ur_482_30", "source": "42 CFR 482.30 (hospital utilization review)", "year": 2024, "locator": "UR plan; medical necessity of admissions and continued stays"}
GINA = {"ref_id": "gina_2025", "source": "Global Initiative for Asthma (GINA) 2025 report", "year": 2025, "locator": "acute exacerbation severity, monitoring, hospitalization decision"}
GOLD = {"ref_id": "gold_copd", "source": "Global Initiative for Chronic Obstructive Lung Disease (GOLD) report", "year": 2025, "locator": "exacerbation management; NIPPV indications"}
CMS_DIALYSIS = {"ref_id": "cms_dialysis_manual", "source": "CMS Medicare Benefit Policy Manual (inpatient hospital services)", "year": 2024, "locator": "routine outpatient chronic dialysis vs acute/episodic inpatient dialysis"}

# A standard cms_public documentation phrase usable across modules (Two-Midnight expectation).
def two_midnight_phrase(tokens: list[str]) -> dict:
    return {
        "phrase": "I expect medically necessary hospital care to span at least two midnights because the patient requires hospital-only services that cannot be safely delivered at a lower level of care.",
        "requires_evidence_tokens": tokens,
        "provenance": "cms_public",
        "citations": [CMS_2MID],
    }


def lower_level_phrase(tokens: list[str]) -> dict:
    return {
        "phrase": "Lower-level care is not safe because the patient requires the hospital-only services documented above with ongoing reassessment.",
        "requires_evidence_tokens": tokens,
        "provenance": "cms_public",
        "citations": [CMS_UR],
    }


# Each module: condition, aliases, si, is, two_midnight, denial, overturn, obs, inpatient,
# gap_questions [(q, class, field)], doc_phrase_tokens, provenance, citations.
MODULES: list[dict] = [
    {
        "condition": "copd", "provenance": "peer_reviewed", "citations": [GOLD],
        "aliases": ["copd", "copd exacerbation", "aecopd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
        "si": ["hypoxemia requiring oxygen above baseline", "respiratory acidosis with hypercapnia on blood gas", "accessory muscle use or impending respiratory fatigue", "altered mental status attributable to hypercapnia"],
        "is": ["noninvasive positive-pressure ventilation (BiPAP) with monitoring", "frequent or continuous bronchodilator nebulization with reassessment", "systemic corticosteroids with response monitoring", "serial arterial or venous blood gas sampling", "continuous pulse oximetry"],
        "two_midnight": "Variable; uncomplicated exacerbations responding to bronchodilators and steroids may resolve under two midnights, while hypercapnic respiratory failure requiring NIPPV commonly crosses two midnights.",
        "denial": ["rapid response to nebulizers without oxygen escalation", "no respiratory acidosis and stable mental status", "no documented failed outpatient therapy"],
        "overturn": ["documented hypercapnic respiratory failure requiring NIPPV", "oxygen requirement above documented home baseline", "frailty or comorbidity raising decompensation and readmission risk"],
        "obs": ["single nebulizer response with return to baseline oxygen saturation", "no respiratory acidosis on blood gas", "anticipated short stay with stable vitals"],
        "inpatient": ["noninvasive positive-pressure ventilation initiated", "respiratory acidosis with hypercapnia", "supplemental oxygen escalated above baseline"],
        "gap_questions": [
            ["Is the current oxygen requirement documented relative to the patient's home baseline?", "documentation", "current_visit.oxygen_requirement"],
            ["Was a blood gas obtained, and does it show respiratory acidosis or hypercapnia?", "diagnostic_clarification", "labs"],
            ["Is NIPPV/BiPAP initiation and the response to it recorded?", "treatment_escalation", "current_visit.respiratory_support"],
        ],
        "phrase_tokens": ["bipap", "noninvasive", "hypercapnia", "acidosis", "oxygen"],
    },
    {
        "condition": "asthma", "provenance": "peer_reviewed", "citations": [GINA],
        "aliases": ["asthma", "asthma exacerbation", "status asthmaticus", "reactive airway", "bronchospasm"],
        "si": ["persistent wheeze or dyspnea after initial treatment", "low oxygen saturation", "poor one-hour treatment response", "drowsiness or confusion"],
        "is": ["repeated short-acting bronchodilator and ipratropium dosing", "oxygen titration", "serial lung-function or symptom reassessment", "intravenous magnesium", "systemic steroids"],
        "two_midnight": "Often under two midnights when lung function and oxygenation improve after initial treatment; longer when acute-care bronchodilator need and obstruction persist.",
        "denial": ["subjective symptoms only without objective reassessment", "no one-hour response documented", "home action plan not addressed"],
        "overturn": ["persistent objective obstruction after initial therapy", "recurrent acute-care bronchodilator need", "unsafe home management capacity"],
        "obs": ["rapid symptom improvement", "normalizing oxygen saturation", "safe home action plan in place"],
        "inpatient": ["recurrent bronchodilator need", "persistent obstruction", "intravenous magnesium required"],
        "gap_questions": [
            ["What was the one-hour reassessment response?", "diagnostic_clarification", "current_visit.one_hour_response"],
            ["Is the patient still desaturating or requiring repeated bronchodilators?", "treatment_escalation", "current_visit.bronchodilator_frequency"],
            ["Can the home action plan be executed safely?", "geriatric_safety", "social_support"],
        ],
        "phrase_tokens": ["bronchodilator", "magnesium", "obstruction", "oxygen", "wheeze"],
    },
    {
        "condition": "esrd_dialysis", "provenance": "cms_public", "citations": [CMS_DIALYSIS],
        "aliases": ["esrd", "dialysis complication", "missed dialysis", "end-stage renal disease", "hemodialysis complication"],
        "si": ["rebound hyperkalemia after temporizing therapy", "pulmonary edema persisting after dialysis", "uremic symptoms", "dialysis access complication"],
        "is": ["repeat potassium checks after temporizing therapy", "telemetry for arrhythmia risk", "urgent inpatient dialysis logistics", "oxygen support"],
        "two_midnight": "Routine chronic dialysis is usually outpatient; acute or episodic dialysis complications with unstable physiology commonly require inpatient care crossing two midnights.",
        "denial": ["charted as routine missed dialysis only", "no rebound-lab trend", "no instability documented"],
        "overturn": ["rebound instability after a single dialysis session", "documented access complication", "telemetry-worthy electrolyte derangement"],
        "obs": ["single dialysis session resolves the issue", "stable post-dialysis labs"],
        "inpatient": ["ongoing instability after dialysis", "repeat dialysis planning need", "rebound hyperkalemia"],
        "gap_questions": [
            ["What is the potassium after temporizing therapy?", "diagnostic_clarification", "labs"],
            ["Is urgent inpatient dialysis required beyond a brief window?", "treatment_escalation", "current_visit.dialysis_plan"],
            ["Is this charted as an acute complication rather than routine dialysis?", "documentation", "current_visit.complication"],
        ],
        "phrase_tokens": ["hyperkalemia", "dialysis", "edema", "uremic", "telemetry"],
    },
    {
        "condition": "pneumonia", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["pneumonia", "cap", "community-acquired pneumonia", "aspiration pneumonia", "lung infection"],
        "si": ["ambulatory desaturation", "tachypnea", "sepsis physiology or rising lactate", "acute kidney injury", "delirium"],
        "is": ["supplemental oxygen", "intravenous antibiotics beyond first dose", "serial vitals and labs", "swallow or aspiration monitoring"],
        "two_midnight": "Variable; stable patients tolerating oral therapy may be observation-appropriate, while hypoxemia, delirium, or ongoing intravenous support commonly support an inpatient expectation.",
        "denial": ["one intravenous antibiotic dose only", "no ambulatory oxygen data", "social factors not linked to medical risk"],
        "overturn": ["ambulatory desaturation documented", "delirium or functional decline tied to the infection", "ongoing intravenous support need"],
        "obs": ["room-air and ambulation oxygen stability", "oral antibiotics feasible", "improving vitals"],
        "inpatient": ["oxygen or intravenous support beyond a short stay", "unsafe oral intake", "serial reassessment need"],
        "gap_questions": [
            ["Does the patient desaturate when walking?", "diagnostic_clarification", "current_visit.ambulatory_oxygen"],
            ["Can the patient take oral antibiotics and nutrition safely?", "geriatric_safety", "current_visit.po_status"],
            ["Has delirium resolved or is it an acute change from baseline?", "documentation", "cognitive_status"],
        ],
        "phrase_tokens": ["desaturation", "delirium", "intravenous", "oxygen", "sepsis"],
    },
    # ---- derived_concept modules (CMS-anchored) ----
    {
        "condition": "uti_urosepsis", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["uti", "pyelonephritis", "urosepsis", "urinary tract infection", "complicated uti"],
        "si": ["delirium", "acute kidney injury", "persistent vomiting", "hypotension", "urinary obstruction concern"],
        "is": ["intravenous fluids", "intravenous antibiotics", "serial renal labs", "urologic intervention if obstructed"],
        "two_midnight": "Stable patients tolerating oral therapy may be observation-appropriate; delirium, AKI, obstruction, or ongoing intravenous support commonly support an inpatient expectation.",
        "denial": ["labeled as uncomplicated UTI", "no baseline cognition documented", "no oral challenge"],
        "overturn": ["acute delirium documented as a change from baseline", "AKI or obstruction", "ongoing intravenous support need"],
        "obs": ["oral therapy tolerated", "no AKI or delirium", "stable vitals"],
        "inpatient": ["ongoing delirium", "ongoing intravenous support", "obstruction or bacteremia concern"],
        "gap_questions": [
            ["Is there urinary obstruction?", "diagnostic_clarification", "di_results"],
            ["Is the altered mentation an acute change from baseline?", "documentation", "cognitive_status"],
            ["Can the patient hydrate and take oral medications?", "geriatric_safety", "current_visit.po_status"],
        ],
        "phrase_tokens": ["delirium", "kidney injury", "obstruction", "intravenous", "hypotension"],
    },
    {
        "condition": "cellulitis", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["cellulitis", "soft-tissue infection", "skin infection", "erysipelas"],
        "si": ["rapid progression despite treatment", "severe pain limiting ambulation", "immune compromise", "systemic signs", "failed oral antibiotics"],
        "is": ["repeat intravenous antibiotics", "serial border examinations", "pain control", "wound monitoring"],
        "two_midnight": "Localized infection bridged to oral therapy may be observation-appropriate; progression, repeated intravenous dosing, or functional unsafety commonly support an inpatient expectation.",
        "denial": ["single intravenous dose", "no interval examination", "no failed oral therapy documented"],
        "overturn": ["documented progression after treatment", "pain-limited ambulation", "repeated intravenous dosing need"],
        "obs": ["localized infection", "single-dose bridge to oral therapy", "stable reassessment"],
        "inpatient": ["progression concern", "repeated intravenous dosing", "functional collapse"],
        "gap_questions": [
            ["Is the infection spreading despite treatment (borders marked)?", "diagnostic_clarification", "current_visit.border_progression"],
            ["Can the patient ambulate and bear weight?", "geriatric_safety", "current_visit.ambulation"],
            ["Is more than one intravenous dose required?", "treatment_escalation", "current_visit.iv_doses"],
        ],
        "phrase_tokens": ["progression", "intravenous", "ambulate", "immune", "failed oral"],
    },
    {
        "condition": "diabetic_foot", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["diabetic foot infection", "foot ulcer", "diabetic foot"],
        "si": ["deep-space infection concern", "gas or osteomyelitis concern", "limb ischemia", "severe hyperglycemia", "systemic illness"],
        "is": ["broad intravenous antibiotics", "serial wound examinations", "podiatry, vascular, or surgical consultation"],
        "two_midnight": "Limb-threatening infection with multidisciplinary needs commonly supports an inpatient expectation; superficial infection with preserved perfusion may be observation-appropriate.",
        "denial": ["under-coding as simple cellulitis", "no imaging or depth assessment", "no consult requests"],
        "overturn": ["documented depth, gas, or ischemia", "need for surgical or vascular input", "limb-threat documentation"],
        "obs": ["superficial infection", "stable perfusion", "outpatient specialist access"],
        "inpatient": ["limb threat", "multidisciplinary hospital care", "serial reassessment"],
        "gap_questions": [
            ["Is there bone, gas, or ischemia on imaging?", "diagnostic_clarification", "di_results"],
            ["Is surgery or vascular input required?", "treatment_escalation", "current_visit.consults"],
            ["Can wound care be done safely as an outpatient?", "geriatric_safety", "social_support"],
        ],
        "phrase_tokens": ["osteomyelitis", "ischemia", "limb", "intravenous", "consult"],
    },
    {
        "condition": "hyperglycemia_dka", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["dka", "hhs", "diabetic ketoacidosis", "hyperglycemia", "hyperosmolar"],
        "si": ["anion-gap or ketone persistence", "dehydration", "acute kidney injury", "altered mentation", "vomiting"],
        "is": ["serial basic metabolic panels", "insulin titration", "intravenous fluids", "electrolyte repletion"],
        "two_midnight": "Rapidly correcting metabolic derangement may be observation-appropriate; persistent acidosis, electrolyte instability, or unsafe self-management commonly supports an inpatient expectation.",
        "denial": ["hyperglycemia noted without metabolic trajectory", "no repeat metabolic panel", "self-management not assessed"],
        "overturn": ["persistent anion gap or ketonemia", "ongoing electrolyte instability", "unsafe insulin self-management"],
        "obs": ["gap closes quickly", "oral intake tolerated", "glucose stabilizes", "safe self-management"],
        "inpatient": ["ongoing metabolic correction", "serial q4-6h labs", "unsafe home insulin use"],
        "gap_questions": [
            ["Has the anion gap or ketonemia resolved?", "diagnostic_clarification", "labs"],
            ["Is the patient still vomiting or dehydrated?", "treatment_escalation", "current_visit.volume_status"],
            ["Can the patient manage insulin safely after discharge?", "geriatric_safety", "social_support"],
        ],
        "phrase_tokens": ["anion gap", "ketone", "insulin", "acidosis", "metabolic"],
    },
    {
        "condition": "hypoglycemia", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["hypoglycemia", "low blood sugar", "recurrent hypoglycemia"],
        "si": ["recurrent low glucose", "renal failure", "long-acting agent or sulfonylurea effect", "falls", "delirium"],
        "is": ["serial glucose monitoring", "intravenous dextrose or glucagon as needed", "medication adjustment", "nutrition support"],
        "two_midnight": "A single correctable event with durable euglycemia may be observation-appropriate; rebound risk from ongoing drivers or unsafe self-management commonly supports an inpatient expectation.",
        "denial": ["focus on corrected glucose only", "no serial trend", "home management capacity not assessed"],
        "overturn": ["recurrent lows after feeding", "active long-acting drug effect", "unsafe self-management"],
        "obs": ["single correctable event", "durable euglycemia", "safe meal plan"],
        "inpatient": ["rebound risk", "serial monitoring need", "unsafe self-management"],
        "gap_questions": [
            ["Are there recurrent lows after feeding?", "diagnostic_clarification", "current_visit.glucose_trend"],
            ["Is a long-acting agent still active?", "treatment_escalation", "current_visit.medications"],
            ["Who manages meals and medications overnight?", "geriatric_safety", "social_support"],
        ],
        "phrase_tokens": ["recurrent", "sulfonylurea", "glucose", "rebound", "renal"],
    },
    {
        "condition": "aki_ckd", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["aki", "acute kidney injury", "ckd worsening", "renal failure", "acute on chronic kidney"],
        "si": ["creatinine rise from baseline", "hyperkalemia", "oliguria", "uremic symptoms", "obstruction concern"],
        "is": ["serial basic metabolic panels", "intravenous fluids or diuretics", "telemetry for potassium issues", "renal imaging or intervention"],
        "two_midnight": "Rapidly reversible derangement with stabilizing labs may be observation-appropriate; progressive rise, hyperkalemia, or obstruction commonly supports an inpatient expectation.",
        "denial": ["chronic CKD not separated from AKI", "no trend data", "no urine output context"],
        "overturn": ["documented acute rise from baseline", "hyperkalemia requiring monitoring", "obstruction or oliguria"],
        "obs": ["stable repeat labs", "reversible cause corrected", "safe follow-up"],
        "inpatient": ["ongoing renal or electrolyte instability", "serial reassessment need"],
        "gap_questions": [
            ["What is the baseline creatinine?", "documentation", "history_comorbidities"],
            ["What is the potassium trend?", "diagnostic_clarification", "labs"],
            ["Is there obstruction on imaging?", "diagnostic_clarification", "di_results"],
        ],
        "phrase_tokens": ["creatinine", "hyperkalemia", "oliguria", "obstruction", "baseline"],
    },
    {
        "condition": "htn_emergency", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["hypertensive emergency", "hypertensive urgency", "severe hypertension", "malignant hypertension"],
        "si": ["encephalopathy", "focal neurologic deficit", "acute kidney injury", "pulmonary edema", "myocardial ischemia"],
        "is": ["intravenous titratable antihypertensives", "close neurologic and cardiac monitoring"],
        "two_midnight": "Severe asymptomatic hypertension without end-organ injury is generally observation or outpatient; documented end-organ injury or ongoing intravenous titration commonly supports an inpatient expectation.",
        "denial": ["using urgency language without organ injury", "single oral medication adjustment only"],
        "overturn": ["documented acute end-organ injury", "ongoing intravenous titration need", "serial neuro/cardiac reassessment"],
        "obs": ["no end-organ injury", "oral adjustment only", "rapid stability"],
        "inpatient": ["documented end-organ injury", "ongoing intravenous titration", "serial monitoring"],
        "gap_questions": [
            ["What specific end-organ injury is documented?", "diagnostic_clarification", "labs"],
            ["Is intravenous titration required rather than oral medication?", "treatment_escalation", "current_visit.iv_titration"],
            ["Is serial neuro or cardiac reassessment required?", "documentation", "current_visit.monitoring"],
        ],
        "phrase_tokens": ["encephalopathy", "end-organ", "titratable", "pulmonary edema", "ischemia"],
    },
    {
        "condition": "tia", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["tia", "transient ischemic attack", "stroke-like", "stroke symptoms", "cerebrovascular"],
        "si": ["ongoing or fluctuating deficit", "high-risk vascular imaging", "atrial fibrillation or embolic concern", "aspiration risk"],
        "is": ["serial neurologic examinations", "telemetry", "vascular imaging", "swallow and rehabilitation evaluation"],
        "two_midnight": "Fully resolved deficits completing a rapid pathway may be observation-appropriate; recurrent or high-risk features needing serial monitoring commonly support an inpatient expectation.",
        "denial": ["resolved symptoms only", "no recurrent-risk framing", "no swallow or functional note"],
        "overturn": ["recurrent or fluctuating deficits", "high-risk imaging findings", "aspiration or gait risk"],
        "obs": ["fully resolved symptoms", "rapid complete pathway", "safe swallow and ambulation"],
        "inpatient": ["recurrent or high-risk features", "ongoing neuro monitoring"],
        "gap_questions": [
            ["Has there been any symptom recurrence?", "diagnostic_clarification", "current_visit.recurrence"],
            ["What did vascular or brain imaging show?", "diagnostic_clarification", "di_results"],
            ["Is there aspiration or gait risk?", "geriatric_safety", "current_visit.swallow_status"],
        ],
        "phrase_tokens": ["deficit", "imaging", "telemetry", "aspiration", "recurrent"],
    },
    {
        "condition": "seizure", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["seizure", "breakthrough seizure", "epilepsy", "status epilepticus", "convulsion"],
        "si": ["recurrent seizure", "prolonged postictal state", "injury", "new focal deficit", "metabolic derangement"],
        "is": ["repeated neurologic checks", "intravenous antiseizure medication", "EEG or neurology workup", "serial labs"],
        "two_midnight": "A single resolved breakthrough event returning to baseline may be observation-appropriate; recurrent risk or unresolved neurologic state commonly supports an inpatient expectation.",
        "denial": ["resolved-seizure wording only", "baseline not documented", "no recurrent-risk statement"],
        "overturn": ["recurrent seizure activity", "prolonged postictal non-resolution", "documented injury or focal deficit"],
        "obs": ["single resolved event", "clear reversible trigger", "return to baseline"],
        "inpatient": ["recurrent risk", "unresolved neurologic state"],
        "gap_questions": [
            ["Has mentation returned to baseline?", "documentation", "cognitive_status"],
            ["Was there any recurrent event?", "diagnostic_clarification", "current_visit.recurrence"],
            ["Is intravenous antiseizure therapy or EEG required?", "treatment_escalation", "current_visit.neuro_plan"],
        ],
        "phrase_tokens": ["recurrent", "postictal", "focal deficit", "antiseizure", "metabolic"],
    },
    {
        "condition": "gi_bleed", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["gi bleed", "gastrointestinal bleed", "melena", "hematemesis", "anemia bleed"],
        "si": ["orthostasis", "hemoglobin drop", "syncope", "ongoing melena or hematemesis", "reversal or transfusion need"],
        "is": ["serial hemoglobin checks", "intravenous proton-pump inhibitor or reversal", "type and screen or transfusion", "endoscopy coordination"],
        "two_midnight": "Low-risk stable bleeding may be observation-appropriate; dynamic bleeding, transfusion, or procedural need commonly supports an inpatient expectation.",
        "denial": ["single stable hemoglobin", "no orthostatic data", "no bleeding trajectory"],
        "overturn": ["documented hemoglobin drop or orthostasis", "transfusion or reversal need", "procedural timing concern"],
        "obs": ["stable hemoglobin trend", "low-risk profile", "no procedure or transfusion expected"],
        "inpatient": ["dynamic bleeding concern", "active hospital therapy", "monitoring burden"],
        "gap_questions": [
            ["What is the hemoglobin trend?", "diagnostic_clarification", "labs"],
            ["Is there orthostasis?", "diagnostic_clarification", "current_visit.orthostatics"],
            ["Is reversal, transfusion, or endoscopy needed soon?", "treatment_escalation", "current_visit.procedure_plan"],
        ],
        "phrase_tokens": ["orthostasis", "hemoglobin", "transfusion", "melena", "endoscopy"],
    },
    {
        "condition": "cirrhosis", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["cirrhosis", "decompensated cirrhosis", "ascites", "hepatic encephalopathy", "liver failure"],
        "si": ["hepatic encephalopathy", "spontaneous bacterial peritonitis concern", "gastrointestinal bleeding", "acute kidney injury or hepatorenal concern", "hyponatremia"],
        "is": ["diagnostic paracentesis", "intravenous albumin or antibiotics", "serial renal and mental-status checks", "lactulose titration"],
        "two_midnight": "A rapidly improving minor presentation may be observation-appropriate; a named decompensating complication with active therapy commonly supports an inpatient expectation.",
        "denial": ["generic cirrhosis wording", "no paracentesis or complication-specific plan"],
        "overturn": ["named decompensating complication", "active complication-directed therapy", "serial reassessment need"],
        "obs": ["minor symptoms with rapid resolution", "no major complication identified"],
        "inpatient": ["named decompensating complication with active therapy"],
        "gap_questions": [
            ["Is there SBP, encephalopathy, or AKI?", "diagnostic_clarification", "labs"],
            ["Is paracentesis, albumin, or antibiotics required?", "treatment_escalation", "current_visit.complication_plan"],
            ["Can mentation and medications be managed safely at home?", "geriatric_safety", "social_support"],
        ],
        "phrase_tokens": ["encephalopathy", "peritonitis", "paracentesis", "hepatorenal", "albumin"],
    },
    {
        "condition": "ibd_flare", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["ibd flare", "crohn", "ulcerative colitis", "severe diarrhea", "inflammatory bowel"],
        "si": ["severe diarrhea", "dehydration", "acute kidney injury or electrolyte derangement", "bleeding", "toxic appearance"],
        "is": ["intravenous fluids", "intravenous steroids", "serial labs", "stool and infectious workup", "imaging when surgical concern"],
        "two_midnight": "Mild symptoms with oral hydration may be observation-appropriate; instability or ongoing intravenous treatment commonly supports an inpatient expectation.",
        "denial": ["nonspecific abdominal pain wording", "no dehydration or trend documented"],
        "overturn": ["documented dehydration or electrolyte instability", "intravenous steroid need", "excluded infection or surgical complication"],
        "obs": ["mild symptoms", "oral hydration feasible", "rapid response"],
        "inpatient": ["intravenous treatment plus serial reassessment needed"],
        "gap_questions": [
            ["Can the patient maintain hydration?", "geriatric_safety", "current_visit.volume_status"],
            ["Are intravenous steroids required?", "treatment_escalation", "current_visit.steroid_plan"],
            ["Have infection and surgical complication been excluded?", "diagnostic_clarification", "labs"],
        ],
        "phrase_tokens": ["dehydration", "steroids", "electrolyte", "diarrhea", "toxic"],
    },
    {
        "condition": "sickle_cell", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["sickle cell", "sickle cell crisis", "vaso-occlusive crisis", "acute chest syndrome"],
        "si": ["persistent severe pain after repeated dosing", "hypoxemia", "fever", "acute chest syndrome concern", "severe anemia"],
        "is": ["repeated intravenous analgesia", "oxygen", "transfusion planning", "serial reassessment"],
        "two_midnight": "Pain responding clearly to a protocolized regimen may be observation-appropriate; uncontrolled pain or complication risk commonly supports an inpatient expectation.",
        "denial": ["partial pain improvement not clarified", "no complication screening documented"],
        "overturn": ["uncontrolled pain after repeated dosing", "hypoxemia or chest findings", "transfusion or complication need"],
        "obs": ["clear pain response", "no pulmonary concern", "stable reassessment"],
        "inpatient": ["ongoing intravenous analgesia", "complication monitoring"],
        "gap_questions": [
            ["Are additional intravenous analgesia doses required?", "treatment_escalation", "current_visit.analgesia_doses"],
            ["Is there hypoxemia or chest symptoms?", "diagnostic_clarification", "current_visit.respiratory"],
            ["Is transfusion or acute chest syndrome a concern?", "diagnostic_clarification", "labs"],
        ],
        "phrase_tokens": ["analgesia", "hypoxemia", "chest syndrome", "transfusion", "anemia"],
    },
    {
        "condition": "cancer_ftt", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["cancer-related", "febrile neutropenia", "cancer pain", "oncology failure to thrive", "malignancy complication"],
        "si": ["neutropenia concern", "uncontrolled pain", "persistent vomiting", "acute kidney injury or dehydration", "delirium"],
        "is": ["intravenous analgesia, antiemetics, and fluids", "serial labs", "cultures and antibiotics when indicated", "oncology input"],
        "two_midnight": "Mild symptoms with oral feasibility may be observation-appropriate; active treatment toxicity or serial symptom-control need commonly supports an inpatient expectation.",
        "denial": ["vague failure-to-thrive wording", "no objective instability documented"],
        "overturn": ["febrile neutropenia concern", "uncontrolled pain after repeated therapy", "documented treatment toxicity"],
        "obs": ["mild symptoms", "oral intake feasible", "rapid oncology access"],
        "inpatient": ["active treatment toxicity", "serial symptom-control need"],
        "gap_questions": [
            ["Is the patient neutropenic or infected?", "diagnostic_clarification", "labs"],
            ["Can the patient take oral medications and nutrition?", "geriatric_safety", "current_visit.po_status"],
            ["Is ongoing intravenous symptom control required?", "treatment_escalation", "current_visit.symptom_plan"],
        ],
        "phrase_tokens": ["neutropenia", "intravenous", "vomiting", "dehydration", "toxicity"],
    },
    # ---- the 4 high-inflation geriatric/social modules (necessity-link guarded) ----
    {
        "condition": "falls", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["fall", "falls", "fall with injury", "ground-level fall", "mechanical fall"],
        "si": ["acute inability to ambulate or transfer", "occult fracture concern", "rhabdomyolysis or dehydration after down-time", "delirium", "anticoagulant-related bleed risk"],
        "is": ["serial examinations", "pain-control titration", "physical and occupational therapy assessment", "repeat labs or imaging"],
        "two_midnight": "Minor injury with restored baseline ambulation may be observation-appropriate; acute functional collapse with ongoing medical needs commonly supports an inpatient expectation. Functional loss must be tied to acute medical risk, not framed as placement alone.",
        "denial": ["placement language", "no baseline functional description", "no ambulation trial"],
        "overturn": ["acute loss of baseline mobility documented", "occult injury or rhabdomyolysis", "ongoing medical treatment or monitoring need"],
        "obs": ["minor injury", "baseline ambulation restored", "safe support at home"],
        "inpatient": ["acute functional collapse", "ongoing medical treatment or monitoring"],
        "gap_questions": [
            ["Can the patient transfer and ambulate compared with baseline?", "geriatric_safety", "adl_dependencies"],
            ["Is there occult injury, rhabdomyolysis, or dehydration?", "diagnostic_clarification", "labs"],
            ["Does physical therapy deem discharge safe?", "geriatric_safety", "current_visit.pt_assessment"],
        ],
        "phrase_tokens": ["ambulate", "fracture", "rhabdomyolysis", "delirium", "baseline mobility"],
    },
    {
        "condition": "delirium", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["delirium", "altered mental status", "ams", "acute confusion", "encephalopathy ams"],
        "si": ["persistent delirium", "unresolved trigger", "dehydration", "infection or metabolic instability", "unsafe oral status"],
        "is": ["serial cognition checks", "intravenous fluids or medications", "trigger-directed treatment", "high nursing supervision tied to medical care"],
        "two_midnight": "Quickly corrected delirium returning near baseline may be observation-appropriate; delirium that remains an active medical condition commonly supports an inpatient expectation. Document the active medical driver, not behavior alone.",
        "denial": ["behavior framed without a medical cause", "baseline not documented", "no serial mentation trend"],
        "overturn": ["active medical driver documented", "serial mentation non-resolution", "unsafe oral intake tied to the medical condition"],
        "obs": ["cause corrected quickly", "returns near baseline", "safe supervision available"],
        "inpatient": ["ongoing active delirium with medical treatment need"],
        "gap_questions": [
            ["What is the patient's cognitive baseline?", "documentation", "cognitive_status"],
            ["Which medical trigger is still active?", "diagnostic_clarification", "labs"],
            ["Can the patient take oral medications safely?", "geriatric_safety", "current_visit.po_status"],
        ],
        "phrase_tokens": ["delirium", "trigger", "dehydration", "metabolic", "infection"],
    },
    {
        "condition": "dementia_trigger", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["dementia behavior", "dementia with trigger", "behavioral dyscontrol dementia", "agitation dementia"],
        "si": ["acute behavior change from baseline", "active medical trigger (infection, retention, pain)", "unsafe agitation", "poor oral or medication intake"],
        "is": ["serial reassessment", "trigger-specific treatment", "high nursing supervision with medical care"],
        "two_midnight": "A brief resolved trigger with safe supervision may be observation-appropriate; medically triggered behavioral decompensation needing active treatment commonly supports an inpatient expectation. Separate medical necessity from custodial need.",
        "denial": ["custodial language", "no trigger search", "caregiver capacity omitted"],
        "overturn": ["active medical trigger documented", "acute change from baseline behavior", "treatment-requiring decompensation"],
        "obs": ["brief resolved trigger", "safe caregiver supervision", "returns to baseline behavior"],
        "inpatient": ["medically triggered behavioral decompensation needing active treatment"],
        "gap_questions": [
            ["What changed acutely from the dementia baseline?", "documentation", "cognitive_status"],
            ["Which medical trigger (infection, retention, pain) is active?", "diagnostic_clarification", "labs"],
            ["Can home supervision safely manage the acute state?", "geriatric_safety", "social_support"],
        ],
        "phrase_tokens": ["trigger", "infection", "retention", "acute change", "baseline behavior"],
    },
    {
        "condition": "generalized_weakness", "provenance": "derived_concept", "citations": [CMS_2MID],
        "aliases": ["generalized weakness", "failure to thrive", "ftt", "inability to ambulate", "deconditioning"],
        "si": ["acute inability to ambulate", "orthostasis", "dehydration", "malnutrition", "delirium", "rhabdomyolysis concern"],
        "is": ["serial reassessment", "intravenous fluids", "physical and occupational therapy", "repeat labs", "nutrition intervention"],
        "two_midnight": "Mild reversible weakness with restored function may be observation-appropriate; acute functional collapse with active medical needs commonly supports an inpatient expectation. Document acute change from baseline, not chronic decline or placement alone.",
        "denial": ["social or placement wording", "no baseline function documented", "no PT/OT or ambulation data"],
        "overturn": ["acute change from baseline functional status", "orthostasis, dehydration, or rhabdomyolysis", "active medical treatment or monitoring need"],
        "obs": ["mild reversible weakness", "baseline function restored", "strong home support"],
        "inpatient": ["acute functional collapse with active medical treatment or monitoring"],
        "gap_questions": [
            ["Can the patient ambulate and transfer compared with baseline?", "geriatric_safety", "adl_dependencies"],
            ["Is there dehydration, orthostasis, rhabdomyolysis, or delirium?", "diagnostic_clarification", "labs"],
            ["Can home safely manage the current deficits?", "geriatric_safety", "social_support"],
        ],
        "phrase_tokens": ["ambulate", "orthostasis", "dehydration", "rhabdomyolysis", "baseline function"],
    },
]


def build(m: dict) -> dict:
    gqs = [{"question": q, "gap_class": cls, "targets_field": fld} for (q, cls, fld) in m["gap_questions"]]
    doc_phrases = [
        two_midnight_phrase(m["phrase_tokens"]),
        lower_level_phrase(m["phrase_tokens"]),
    ]
    return {
        "condition": m["condition"],
        "aliases": m["aliases"],
        "si_thresholds": m["si"],
        "is_requirements": m["is"],
        "two_midnight_expectation": m["two_midnight"],
        "denial_downgrade_triggers": m["denial"],
        "overturn_support_factors": m["overturn"],
        "observation_features": m["obs"],
        "inpatient_features": m["inpatient"],
        "gap_questions": gqs,
        "documentation_phrases": doc_phrases,
        "provenance": m["provenance"],
        "citations": m["citations"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for m in MODULES:
        data = build(m)
        path = OUT / f"{m['condition']}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(MODULES)} disease packs to {OUT}")


if __name__ == "__main__":
    main()
