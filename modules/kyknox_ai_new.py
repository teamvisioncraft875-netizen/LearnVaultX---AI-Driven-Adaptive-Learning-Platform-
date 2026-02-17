import os
import requests
import logging
import markdown
from markdown.extensions import fenced_code, tables, nl2br

logger = logging.getLogger(__name__)

class KyKnoX:
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.1-8b-instant"

    def get_system_prompt(self, mode, role):
        """Generate system prompt based on mode and role"""
        base_prompt = """You are KyKnoX (pronounced 'Kai-nox'), an advanced AI tutor for LearnVaultX platform. 
You are intelligent, helpful, and adaptive to student needs."""
        
        if role == 'teacher':
            base_prompt += """ You are assisting a teacher. Provide pedagogical insights, help with class management, 
            suggest assessment strategies, and offer data-driven recommendations for student interventions."""
        else:
            base_prompt += """ You are assisting a student. Help them learn effectively through personalized guidance."""
            
        if mode == 'socratic':
            return base_prompt + """ 
            
**Your Socratic Mode Instructions:**
- Use the Socratic method: Ask guiding questions instead of giving direct answers
- Help students discover solutions themselves through thoughtful questioning
- Break complex problems into smaller, manageable questions
- Encourage critical thinking and self-reflection
- Be patient and supportive"""
        elif mode == 'coach':
            return base_prompt + """
            
**Your Coach Mode Instructions:**
- Act as a supportive, motivational coach
- Provide encouragement and positive reinforcement
- Break tasks into achievable steps
- Celebrate progress and effort
- Build confidence while maintaining high standards
- Be empathetic and understanding"""
        else:  # expert mode
            return base_prompt + """
            
**Your Expert Mode Instructions:**
- Act as a subject matter expert
- Provide detailed, accurate, and comprehensive explanations
- Use examples and analogies to clarify concepts
- Offer step-by-step solutions when appropriate
- Be precise and technical when needed
- Cite relevant resources or suggest further reading"""

    def build_context_message(self, context):
        """Build contextual message from student data"""
        if not context or not isinstance(context, dict):
            return ""
        
        context_parts = []
        
        if context.get('weak_topics'):
            topics_str = ', '.join(context['weak_topics'][:3])
            context_parts.append(f"Student is struggling with: {topics_str}")
        
        if context.get('performance_level'):
            context_parts.append(f"Performance level: {context['performance_level']}")
        
        if context.get('engagement'):
            context_parts.append(f"Engagement: {context['engagement']}")
        
        if context_parts:
            return "\n\n**Student Context:** " + " | ".join(context_parts)
        
        return ""

    def generate_response(self, prompt, mode='expert', context=None, role='student', language='english'):
        """Generate AI response using Groq API with multilingual support"""
        system_prompt = self.get_system_prompt(mode, role)
        context_message = self.build_context_message(context)
        
        # Add language instruction
        language = language.lower() if language else 'english'
        
        # Dynamic strict language instruction
        if language == 'english':
             lang_instruction = ""
        else:
             # Map common language codes/names to full names for the prompt
             lang_map = {
                 'hindi': 'Hindi (हिंदी)',
                 'hi': 'Hindi (हिंदी)',
                 'odia': 'Odia (ଓଡ଼ିଆ)',
                 'or': 'Odia (ଓଡ଼ିଆ)',
                 'bengali': 'Bengali (বাংলা)',
                 'bn': 'Bengali (বাংলা)',
                 'telugu': 'Telugu (తెలుగు)',
                 'te': 'Telugu (తెలుగు)',
                 'tamil': 'Tamil (தமிழ்)',
                 'ta': 'Tamil (தமிழ்)',
                 'marathi': 'Marathi (मराठी)',
                 'mr': 'Marathi (मराठी)'
             }
             target_lang = lang_map.get(language, language.title())
             
             lang_instruction = f"""
            
**IMPORTANT: LANGUAGE ENFORCEMENT**
You must respond STRICTLY in **{target_lang}**.
- Do NOT use English words unless absolutely necessary for technical terms.
- Use the native script for {target_lang}.
- Do NOT mix languages (no Hinglish/Odlish).
- If you are unsure of a translation, explain simply in {target_lang}.
"""

        # Append language instruction to system prompt
        system_prompt += lang_instruction
        
        # Construct messages
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add context if available
        if context_message:
            messages.append({"role": "system", "content": context_message})
        
        # Add user prompt (with reminder)
        messages.append({"role": "user", "content": f"Answer in {language}: {prompt}"})
        
        try:
            if self.api_key:
                response = requests.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 2048
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result['choices'][0]['message']['content']
                    logger.info(f"KyKnoX responded successfully ({mode} mode)")
                    return answer, "Groq"
                else:
                    logger.error(f"Groq API Error {response.status_code}: {response.text}")
                    return self._fallback_response(prompt, mode), "Fallback"
            else:
                logger.warning("No GROQ_API_KEY found, using fallback mode")
                return self._fallback_response(prompt, mode), "Local"
                
        except requests.exceptions.Timeout:
            logger.error("Groq API timeout")
            return "I'm taking a bit longer than usual to respond. Please try again.", "Error"
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API request failed: {e}")
            return self._fallback_response(prompt, mode), "Error"
        except Exception as e:
            logger.error(f"Unexpected error in AI generation: {e}")
            return "I apologize, but I encountered an unexpected error. Please try asking your question again.", "Error"

    def _fallback_response(self, prompt, mode):
        """Generate fallback response when API is unavailable"""
        responses_by_mode = {
            'socratic': f"""I'm KyKnoX, currently in **local mode**. Let me help you think through this:

**Your question:** "{prompt}"

Here are some guiding questions to help you explore this topic:
1. What do you already know about this topic?
2. What specific part is challenging you?
3. Can you break this problem into smaller steps?

💡 *To unlock my full AI capabilities, please configure your GROQ_API_KEY in the environment settings.*""",
            
            'coach': f"""Great question! I'm KyKnoX in **local mode**, and I'm here to support you! 🌟

**You asked:** "{prompt}"

Here's my encouragement:
- You're taking the right step by asking questions!
- Learning is a journey, and every question brings you closer to understanding
- Remember: confusion is a natural part of growth

💪 Keep going! You've got this!

💡 *Configure GROQ_API_KEY for personalized AI coaching.*""",
            
            'expert': f"""Hello! I'm KyKnoX running in **local mode**.

**Your question:** "{prompt}"

I'd love to provide you with detailed expert guidance, but I need to be configured first. Here's what I can tell you:
- Make sure to check your course materials and lecture notes
- Consider breaking down complex topics into fundamentals
- Practice with examples to reinforce concepts

💡 *To get comprehensive, AI-powered answers, please ask your administrator to configure the GROQ_API_KEY.*"""
        }
        
        return responses_by_mode.get(mode, responses_by_mode['expert'])

    def render_markdown(self, text):
        """Convert markdown to HTML with syntax highlighting support"""
        if not text:
            return ""
        
        # Configure markdown extensions
        extensions = [
            'fenced_code',
            'tables',
            'nl2br',
            'codehilite',
            'extra'
        ]
        
        extension_configs = {
            'codehilite': {
                'css_class': 'highlight',
                'linenums': False
            }
        }
        
        try:
            html = markdown.markdown(
                text,
                extensions=extensions,
                extension_configs=extension_configs
            )
            return html
        except Exception as e:
            logger.error(f"Markdown rendering error: {e}")
            # Fallback: return text with basic formatting
            return text.replace('\n', '<br>')
