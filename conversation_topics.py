import os
import logging
from typing import Optional
from openai import OpenAI

# Configure logging to output to STDOUT
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # This outputs to STDOUT
)

# Static base prompt that gets prepended to all user requests
BASE_PROMPT = """Generate 15 conversation prompts for me and my wife that match
the tone and style we've used previously: emotionally grounded but lightly
playful, introspective without being heavy, and attuned to the everyday
realities of life with young kids. Prioritize depth over novelty—questions that
reveal growth, shared values, small joys, or evolving connection. We're
thoughtful, dry-humored, and candid, with a preference for prompts that feel
personal, specific, and gently surprising. Keep them low-effort to engage with,
high-signal in payoff, and phrased in plain ASCII-safe language suitable for
thermal printing. IMPORTANT: Do not use any emojis, unicode symbols, or special
characters - only plain ASCII text.

Here is an example:
1. What's a small choice we made that quietly shaped our life in a big way?
2. What's something we've adapted to that used to feel like a dealbreaker?
3. What's a way we've helped each other become more ourselves?
4. What's something about you that's hard to explain but you know I get?
5. What's one way we've protected each other's energy lately?
6. What's a tension we've figured out how to live with instead of fix?
7. What's something we've made easier for each other — even if it's still hard?
8. What's one thing I do that reminds you we're on the same team?
9. What's something we're learning together, even if we're learning it slowly?
10. What's something that's still hard to say out loud, but getting easier?
11. What's a moment when you realized we'd changed — in a good way?
12. What's something you're holding onto right now that you don't want to rush past?
13. What's a shared memory that still teaches you something?
14. What's one truth we've earned the right to hold, just by going through life together?
15. What's a part of our story we might underestimate, but will probably mean a lot in hindsight?
"""


class ConversationTopicGenerator:
    """Handles OpenAI API calls for generating conversation topics."""

    def __init__(self):
        """Initialize with OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required. "
                "Set it with: export OPENAI_API_KEY='your-key-here'"
            )

        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4.1-nano"

    def generate_topics(
        self,
        user_prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        timeout: int = 30,
    ) -> str:
        """
        Generate conversation topics using OpenAI GPT.

        Args:
            user_prompt: Optional user input to append to base prompt (e.g., "make them about travel")
            system_prompt: Optional custom system prompt to use instead of BASE_PROMPT
            timeout: Request timeout in seconds

        Returns:
            Formatted string with 15 numbered conversation prompts

        Raises:
            Exception: On API errors, timeouts, or formatting issues
        """
        # Construct the full prompt
        full_prompt = (
            system_prompt if system_prompt and system_prompt.strip() else BASE_PROMPT
        )
        if user_prompt and user_prompt.strip():
            full_prompt += "\n\nTHIS IS VERY IMPORTANT: the user has specified that beyond base instructions, it should be influenced by these additional instructions:\n"
            full_prompt += f" {user_prompt.strip()}"

        logging.info(f"Full prompt: {full_prompt}")

        try:
            logging.info(f"Calling OpenAI API with model: {self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=800,  # Enough for ~15 prompts
                temperature=0.7,  # Some creativity but consistent
                timeout=timeout,
            )

            # Extract the generated text
            generated_text = response.choices[0].message.content.strip()

            # Clean and format for thermal printing
            formatted_topics = self._format_for_thermal_print(generated_text)

            logging.info("Successfully generated conversation topics")
            return formatted_topics

        except Exception as e:
            logging.error(f"OpenAI API call failed: {e}")
            raise Exception(f"Failed to generate conversation topics: {str(e)}")

    def _format_for_thermal_print(self, text: str) -> str:
        """
        Clean and format GPT response for thermal printing.

        Args:
            text: Raw GPT response text

        Returns:
            Clean, formatted text suitable for receipt printer
        """
        # Strip any emojis and non-ASCII characters
        ascii_text = self._strip_non_ascii(text)

        # Basic cleaning - remove extra whitespace
        lines = ascii_text.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                # Ensure line starts with a number (1., 2., etc.) or add numbering if missing
                if not line[0].isdigit():
                    # If this looks like a prompt but isn't numbered, skip for now
                    # GPT should return numbered items, but we'll be permissive
                    cleaned_lines.append(line)
                else:
                    cleaned_lines.append(line)

        # Join with newlines and add some spacing for readability
        formatted = "\n".join(cleaned_lines)

        # Add date line
        from datetime import datetime
        import pytz

        pdt = pytz.timezone("America/Los_Angeles")
        today = datetime.now(pdt).strftime("%B %d, %Y")

        # Add header and footer spacing for thermal printing
        formatted = f"\nCONVERSATION TOPICS\n{'='*40}\nPrinted on: {today}\n\n{formatted}\n\n{'='*40}\n"

        return formatted

    def _strip_non_ascii(self, text: str) -> str:
        """
        Remove non-ASCII characters including emojis.

        Args:
            text: Input text that may contain emojis or unicode

        Returns:
            ASCII-only text safe for thermal printing
        """
        # Keep only ASCII printable characters (32-126) plus newlines and tabs
        return "".join(
            char
            for char in text
            if ord(char) < 128 and (char.isprintable() or char in "\n\t")
        )


# Convenience function for easy importing
def generate_conversation_topics(
    user_prompt: Optional[str] = None, system_prompt: Optional[str] = None
) -> str:
    """
    Generate conversation topics using the default generator.

    Args:
        user_prompt: Optional user guidance (e.g., "make them about travel")
        system_prompt: Optional custom system prompt to use instead of BASE_PROMPT

    Returns:
        Formatted conversation topics ready for printing

    Raises:
        Exception: On generation failures
    """
    generator = ConversationTopicGenerator()
    return generator.generate_topics(user_prompt, system_prompt)
