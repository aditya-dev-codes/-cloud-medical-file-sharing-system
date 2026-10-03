import os
import re
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod

class BaseAIService(ABC):
    """Abstract base class for modular AI summarization services."""

    @abstractmethod
    def summarize(self, document_text, filename="document"):
        """
        Summarizes extracted medical document text.
        Must return a dict:
        {
            'summary_text': str,
            'extracted_conditions': str,
            'extracted_allergies': str,
            'extracted_medications': str,
            'is_mock': bool
        }
        """
        pass

class MockAIService(BaseAIService):
    """
    Intelligent offline mock AI service for development and college demonstrations.
    Extracts clinical information directly from document text using rule-based parsing.
    Guarantees reliable testing without requiring paid external API credentials.
    """

    def summarize(self, document_text, filename="document"):
        text = document_text.strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        conditions = []
        allergies = []
        medications = []
        test_results = []
        procedures = []

        # Clinical keyword extraction rules
        for line in lines:
            line_lower = line.lower()

            # Allergies
            if any(k in line_lower for k in ['allergy', 'allergies', 'allergic']):
                # Clean prefix
                cleaned = re.sub(r'^(known\s+)?allerg(y|ies)\s*:\s*', '', line, flags=re.IGNORECASE).strip('- ')
                if cleaned and cleaned.lower() not in ['none', 'none reported']:
                    allergies.append(cleaned)

            # Medications
            elif any(k in line_lower for k in ['medication', 'medications', 'prescribed', 'mg ', 'mcg', 'po ', 'bid', 'prn']):
                cleaned = re.sub(r'^(current\s+)?medications?\s*:\s*', '', line, flags=re.IGNORECASE).strip('- ')
                if cleaned and not any(h in cleaned.lower() for h in ['allerg', 'diagnos', 'result']):
                    medications.append(cleaned)

            # Diagnoses / Conditions
            elif any(k in line_lower for k in ['diagnos', 'condition', 'assessment', 'hypertension', 'diabetes', 'asthma']):
                cleaned = re.sub(r'^(clinical\s+)?(diagnos(is|es)|assessment|conditions?)\s*:\s*', '', line, flags=re.IGNORECASE).strip('- ')
                if cleaned and len(cleaned) > 3:
                    conditions.append(cleaned)

            # Test Results
            elif any(k in line_lower for k in ['glucose', 'cholesterol', 'hba1c', 'creatinine', 'blood pressure', 'hemoglobin', 'mg/dl', 'mmhg']):
                cleaned = line.strip('- ')
                test_results.append(cleaned)

            # Procedures / Surgeries
            elif any(k in line_lower for k in ['surgery', 'surgeries', 'procedure', 'appendectomy', 'arthroscopy', 'operation']):
                cleaned = re.sub(r'^(previous\s+)?(surgeries|procedures?)\s*:\s*', '', line, flags=re.IGNORECASE).strip('- ')
                if cleaned:
                    procedures.append(cleaned)

        # Fallback if specific sections were not matched
        if not conditions:
            conditions = ["None explicitly listed in document headers"]
        if not allergies:
            allergies = ["No known drug allergies explicitly documented"]
        if not medications:
            medications = ["No ongoing medications explicitly specified"]

        # Build clean bulleted summary
        summary_parts = [
            f"CLINICAL SUMMARY FOR: {filename}",
            "-" * 45,
            "1. CONDITIONS / DIAGNOSES IDENTIFIED:",
            "\n".join([f"   • {c}" for c in conditions[:4]]),
            "",
            "2. DOCUMENTED ALLERGIES:",
            "\n".join([f"   • {a}" for a in allergies[:3]]),
            "",
            "3. MEDICATIONS MENTIONED:",
            "\n".join([f"   • {m}" for m in medications[:5]]),
        ]

        if test_results:
            summary_parts.extend([
                "",
                "4. KEY TEST / LAB RESULTS EXTRACTED:",
                "\n".join([f"   • {t}" for t in test_results[:4]])
            ])

        if procedures:
            summary_parts.extend([
                "",
                "5. DOCUMENTED PROCEDURES / SURGERIES:",
                "\n".join([f"   • {p}" for p in procedures[:3]])
            ])

        summary_parts.extend([
            "",
            "-" * 45,
            "[DEVELOPMENT MOCK AI SUMMARY - Generated Offline without external API dependency]"
        ])

        return {
            'summary_text': "\n".join(summary_parts),
            'extracted_conditions': "; ".join(conditions[:3]),
            'extracted_allergies': "; ".join(allergies[:3]),
            'extracted_medications': "; ".join(medications[:4]),
            'is_mock': True
        }

class GeminiAIService(BaseAIService):
    """
    Live AI Service connecting to Google Gemini REST API.
    Enforces strict summarization guardrails to prevent clinical diagnosis.
    """

    def __init__(self, api_key, model_name="gemini-1.5-flash"):
        self.api_key = api_key
        self.model_name = model_name or "gemini-1.5-flash"
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def summarize(self, document_text, filename="document"):
        # Truncate text if excessively long for prompt safety
        max_chars = 12000
        safe_text = document_text[:max_chars]

        system_prompt = (
            "You are an AI medical report summarizer for a college exhibition prototype.\n"
            "STRICT MEDICAL GUARDRAILS:\n"
            "1. You MUST NOT diagnose illnesses or diseases.\n"
            "2. You MUST NOT prescribe medicines, drugs, or dosages.\n"
            "3. You MUST NOT recommend treatments, remedies, or clinical decisions.\n"
            "4. You MUST NOT invent, guess, or hallucinate information not explicitly present in the document.\n"
            "5. Only extract facts explicitly stated in the provided document.\n\n"
            "Format your response as a valid JSON object with exactly these keys:\n"
            "{\n"
            '  "summary_text": "A concise, objective bullet-point summary of the document for an attending doctor",\n'
            '  "extracted_conditions": "Comma-separated list of explicitly mentioned conditions/diagnoses",\n'
            '  "extracted_allergies": "Comma-separated list of explicitly mentioned allergies",\n'
            '  "extracted_medications": "Comma-separated list of explicitly mentioned medications"\n'
            "}\n"
            "Do NOT output any markdown backticks, explanations, or commentary outside the JSON object."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\nDocument Name: {filename}\nDocument Content:\n{safe_text}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.endpoint,
                data=req_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                raw_text = res_body['candidates'][0]['content']['parts'][0]['text'].strip()

                # Clean markdown code blocks if returned
                if raw_text.startswith("```"):
                    raw_text = re.sub(r'^```(json)?\s*', '', raw_text, flags=re.IGNORECASE)
                    raw_text = re.sub(r'\s*```$', '', raw_text)

                parsed = json.loads(raw_text)

                summary_text = parsed.get('summary_text', '').strip()
                if not summary_text:
                    summary_text = "Clinical summary generated successfully."

                return {
                    'summary_text': summary_text,
                    'extracted_conditions': str(parsed.get('extracted_conditions', '')).strip(),
                    'extracted_allergies': str(parsed.get('extracted_allergies', '')).strip(),
                    'extracted_medications': str(parsed.get('extracted_medications', '')).strip(),
                    'is_mock': False
                }
        except urllib.error.HTTPError as e:
            err_msg = f"HTTP Error {e.code}: {e.reason}"
            try:
                e.close()
            except Exception:
                pass
            # Seamless fallback to Mock service without crashing
            mock = MockAIService()
            res = mock.summarize(document_text, filename)
            res['summary_text'] = (
                f"[NOTE: Gemini API call failed ({err_msg}). Switched to Local Mock Summarizer.]\n\n"
                + res['summary_text']
            )
            res['is_mock'] = True
            return res
        except Exception as e:
            # Seamless fallback to Mock service
            mock = MockAIService()
            res = mock.summarize(document_text, filename)
            res['summary_text'] = (
                f"[NOTE: Gemini API unavailable ({type(e).__name__}). Switched to Local Mock Summarizer.]\n\n"
                + res['summary_text']
            )
            res['is_mock'] = True
            return res

def get_ai_service(config):
    """Factory to provide the appropriate AI summarizer service based on app config."""
    api_key = config.get('GEMINI_API_KEY', '').strip()
    is_mock = config.get('AI_MOCK_MODE', True)
    model_name = config.get('GEMINI_MODEL', 'gemini-1.5-flash').strip()

    if not api_key or is_mock:
        return MockAIService()
    return GeminiAIService(api_key, model_name=model_name)
