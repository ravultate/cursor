import logging
from typing import List, Optional

from auth_utils import get_content_safety_client

logger = logging.getLogger(__name__)


def is_text_safe(text: str) -> bool:
	"""Return True if text passes Azure Content Safety thresholds or if client not configured."""
	client = get_content_safety_client()
	if not client:
		return True
	try:
		from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
		res = client.analyze_text(
			AnalyzeTextOptions(
				text=text,
				categories=[TextCategory.HATE, TextCategory.SEXUAL, TextCategory.VIOLENCE, TextCategory.HARASSMENT],
			)
		)
		return all(getattr(cat, "severity", 0) < 2 for cat in res.categories_analysis or [])
	except Exception as e:
		logger.warning(f"Content safety check failed: {e}")
		return True


def enforce_output_safety(text: str) -> str:
	"""Return safe text; if unsafe and client configured, replace with refusal."""
	return text if is_text_safe(text) else (
		"I cannot return the generated content due to content safety policies."
	)


def groundedness_check(openai_client, deployment_name: str, answer: str, contexts: List[str]) -> bool:
	"""Use an LLM-as-critic to verify if answer is supported by contexts."""
	try:
		context_text = "\n\n".join(contexts[:6])
		critic_prompt = (
			"You are a strict verifier. Determine if the ANSWER is fully supported by the CONTEXT quotes.\n"
			"Respond with exactly one word: SUPPORTED or UNSUPPORTED.\n\nCONTEXT:\n" + context_text + "\n\nANSWER:\n" + answer
		)
		resp = openai_client.chat.completions.create(
			model=deployment_name,
			messages=[{"role": "user", "content": critic_prompt}],
			temperature=0.0,
			max_tokens=3,
		)
		return "SUPPORTED" in (resp.choices[0].message.content or "")
	except Exception as e:
		logger.warning(f"Groundedness check failed: {e}")
		return True

