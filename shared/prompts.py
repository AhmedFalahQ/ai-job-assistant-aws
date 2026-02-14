"""
Prompt templates for all the agents
provides prompt logic and clear contracts
"""
import json
from typing import Dict,Any

class PropmtTemplates:
    # Centralized templates for all agents 

    @staticmethod
    def job_analyzer(job_description:str,job_title:str,company_name:str)-> str:
        
        """
        prompt for analyzing a job requirements -Agent 1-
        returns a Json with job requirements
        """
        return f"""You are a job requirements extraction system. Analyze the job description and extract key information.

JOB TITLE: {job_title}
COMPANY: {company_name}

JOB DESCRIPTION:
{job_description}

Extract the following information and return ONLY valid JSON (no markdown, no explanation):

{{
  "required_skills": ["skill1", "skill2"],
  "preferred_skills": ["skill1", "skill2"],
  "required_experience_years": number or null,
  "education_requirements": ["degree1", "degree2"],
  "key_responsibilities": ["responsibility1", "responsibility2"],
  "technical_tools": ["tool1", "tool2"],
  "soft_skills": ["skill1", "skill2"],
  "company_values": ["value1", "value2"],
  "role_level": "entry|mid|senior|lead|executive"
}}

Rules:
- Only include information explicitly mentioned in the job description
- If a field has no data, use empty array [] or null
- Keep items concise (5-10 words max each)
- Extract 3-8 items per category
- Prioritize skills mentioned multiple times"""
    
    @staticmethod
    def resume_tailor(
        original_resume:str,
        job_analysis:Dict[str,Any],
        job_title:str,
        company_name:str
    ) -> str:
        """ 
        Prompt for tailoring resume -Agent 2-
        returns json with rewritten experince bullets
        """
        return f"""You are an ATS-optimized resume tailoring system. Rewrite the candidate's experience section to emphasize relevance to the target role.

TARGET ROLE: {job_title} at {company_name}

JOB REQUIREMENTS:
{json.dumps(job_analysis, indent=2)}

ORIGINAL RESUME:
{original_resume}

TASK: Rewrite ONLY the experience bullet points to highlight skills and achievements relevant to this job.

RULES:
1. Keep all facts truthful - do NOT fabricate experience
2. Reorder bullet points to put most relevant first
3. Incorporate keywords from required_skills and technical_tools
4. Quantify achievements where possible (use existing numbers)
5. Use action verbs: designed, implemented, optimized, led, developed
6. Keep bullets concise: 1-2 lines max
7. Maintain ATS-friendly formatting (no special characters)
8. Do NOT modify: education, contact info, or certifications

Return ONLY valid JSON (no markdown):

{{
  "tailored_experience": [
    {{
      "company": "Company Name",
      "title": "Job Title",
      "dates": "MMM YYYY - MMM YYYY",
      "bullets": [
        "Rewritten bullet point 1",
        "Rewritten bullet point 2"
      ]
    }}
  ],
  "keywords_added": ["keyword1", "keyword2"],
  "relevance_score": 85
}}

Focus on these priority skills: {", ".join(job_analysis.get("required_skills", [])[:5])}"""
    
    @staticmethod
    def cover_letter(
        candidate_name:str,
        candidate_background:str,
        job_title:str,
        company_name:str,
        job_analysis:Dict[str,Any],
        tailored_experience:Dict[str,Any]
    )-> str:
        """
        Prompt for generating cover letter (Agent 3)
        
        Returns JSON with complete cover letter
        """
        return f"""You are a professional cover letter writer. Generate a one-page cover letter for this job application.

CANDIDATE: {candidate_name}
BACKGROUND: {candidate_background}
TARGET ROLE: {job_title} at {company_name}

JOB REQUIREMENTS:
{json.dumps(job_analysis, indent=2)}

CANDIDATE'S RELEVANT EXPERIENCE:
{json.dumps(tailored_experience, indent=2)}

TASK: Write a compelling, professional cover letter.

STRUCTURE:
1. Opening paragraph: Express interest and mention specific role
2. Body paragraph 1: Highlight 2-3 most relevant technical skills
3. Body paragraph 2: Demonstrate cultural fit and soft skills
4. Closing paragraph: Express enthusiasm and call to action

TONE: Professional, confident, specific (avoid generic phrases)

LENGTH: 250-350 words (fit on one page)

RULES:
- Address company by name, not "your company"
- Reference specific requirements from the job description
- Use concrete examples from candidate's experience
- No clichés ("passionate about", "team player", "hit the ground running")
- End with clear next step

Return ONLY valid JSON (no markdown):

{{
  "cover_letter": "Full letter text with paragraph breaks as \\n\\n",
  "key_points_covered": ["point1", "point2", "point3"],
  "word_count": 287
}}"""
    
    @staticmethod
    def interview_prep(
        job_title:str,
        company_name:str,
        job_analysis:Dict[str,Any],
        candidate_experience:str
    ) -> str:
        """
        Prompt for generating interview questions Agent 4

        returns json with questions and star format answers
        """
        return f"""You are an interview preparation system. Generate likely interview questions for this role with structured answer frameworks.

ROLE: {job_title} at {company_name}

JOB REQUIREMENTS:
{json.dumps(job_analysis, indent=2)}

CANDIDATE EXPERIENCE:
{candidate_experience}

TASK: Generate 5-7 interview questions with STAR-format answer frameworks.

QUESTION TYPES:
- 2 behavioral questions (teamwork, problem-solving, conflict)
- 2-3 technical questions (specific to required_skills)
- 1 situational question (role-specific scenario)
- 1 company/culture fit question

Return ONLY valid JSON (no markdown):

{{
  "questions": [
    {{
      "question": "Full question text",
      "type": "behavioral|technical|situational|culture_fit",
      "answer_framework": {{
        "situation": "Brief context from candidate's experience",
        "task": "What needed to be done",
        "action": ["Specific action 1", "Specific action 2"],
        "result": "Quantifiable outcome"
      }},
      "key_points_to_mention": ["point1", "point2", "point3"]
    }}
  ]
}}

Focus on required skills: {", ".join(job_analysis.get("required_skills", [])[:5])}"""
    
    def get_prompt_template(agent_type:str)-> callable:
        # Factory function to get prompt by agent type
        templates={
            'job_analyzer':PropmtTemplates.job_analyzer,
            'resume_tailor':PropmtTemplates.resume_tailor,
            'cover_letter':PropmtTemplates.cover_letter,
            'interview_prep':PropmtTemplates.interview_prep
        }
        if agent_type not in templates:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return templates[agent_type]