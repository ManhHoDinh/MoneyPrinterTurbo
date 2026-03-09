import json
import logging
import re
import requests
from typing import List

import g4f
from loguru import logger
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletion

from app.config import config

_max_retries = int(config.app.get("llm_retry_attempts", 2) or 2)
_llm_timeout_seconds = int(config.app.get("llm_timeout_seconds", 20) or 20)


def _fallback_terms(video_subject: str, amount: int = 5) -> List[str]:
    subject = (video_subject or "").strip().lower()
    subject_words = [w for w in re.split(r"[^a-z0-9]+", subject) if len(w) > 2]
    core = " ".join(subject_words[:2]).strip()
    seed = core if core else "human behavior"
    terms = [
        f"{seed} close up",
        "crowd walking city",
        "person thinking alone",
        "office conversation",
        "street people portrait",
    ]
    return terms[: max(1, int(amount or 5))]


def _generate_response(prompt: str) -> str:
    try:
        content = ""
        llm_provider = config.app.get("llm_provider", "openai")
        logger.info(f"llm provider: {llm_provider}")
        if llm_provider == "g4f":
            model_name = config.app.get("g4f_model_name", "")
            if not model_name:
                model_name = "gpt-3.5-turbo-16k-0613"
            content = g4f.ChatCompletion.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            api_version = ""  # for azure
            if llm_provider == "moonshot":
                api_key = config.app.get("moonshot_api_key")
                model_name = config.app.get("moonshot_model_name")
                base_url = "https://api.moonshot.cn/v1"
            elif llm_provider == "ollama":
                # api_key = config.app.get("openai_api_key")
                api_key = "ollama"  # any string works but you are required to have one
                model_name = config.app.get("ollama_model_name")
                base_url = config.app.get("ollama_base_url", "")
                if not base_url:
                    base_url = "http://localhost:11434/v1"
            elif llm_provider == "openai":
                api_key = config.app.get("openai_api_key")
                model_name = config.app.get("openai_model_name")
                base_url = config.app.get("openai_base_url", "")
                if not base_url:
                    base_url = "https://api.openai.com/v1"
            elif llm_provider == "oneapi":
                api_key = config.app.get("oneapi_api_key")
                model_name = config.app.get("oneapi_model_name")
                base_url = config.app.get("oneapi_base_url", "")
            elif llm_provider == "azure":
                api_key = config.app.get("azure_api_key")
                model_name = config.app.get("azure_model_name")
                base_url = config.app.get("azure_base_url", "")
                api_version = config.app.get("azure_api_version", "2024-02-15-preview")
            elif llm_provider == "gemini":
                api_key = config.app.get("gemini_api_key")
                model_name = config.app.get("gemini_model_name")
                base_url = config.app.get("gemini_base_url", "")
            elif llm_provider == "qwen":
                api_key = config.app.get("qwen_api_key")
                model_name = config.app.get("qwen_model_name")
                base_url = "***"
            elif llm_provider == "cloudflare":
                api_key = config.app.get("cloudflare_api_key")
                model_name = config.app.get("cloudflare_model_name")
                account_id = config.app.get("cloudflare_account_id")
                base_url = "***"
            elif llm_provider == "deepseek":
                api_key = config.app.get("deepseek_api_key")
                model_name = config.app.get("deepseek_model_name")
                base_url = config.app.get("deepseek_base_url")
                if not base_url:
                    base_url = "https://api.deepseek.com"
            elif llm_provider == "modelscope":
                api_key = config.app.get("modelscope_api_key")
                model_name = config.app.get("modelscope_model_name")
                base_url = config.app.get("modelscope_base_url")
                if not base_url:
                    base_url = "https://api-inference.modelscope.cn/v1/"
            elif llm_provider == "ernie":
                api_key = config.app.get("ernie_api_key")
                secret_key = config.app.get("ernie_secret_key")
                base_url = config.app.get("ernie_base_url")
                model_name = "***"
                if not secret_key:
                    raise ValueError(
                        f"{llm_provider}: secret_key is not set, please set it in the config.toml file."
                    )
            elif llm_provider == "pollinations":
                try:
                    base_url = config.app.get("pollinations_base_url", "")
                    if not base_url:
                        base_url = "https://text.pollinations.ai/openai"
                    model_name = config.app.get("pollinations_model_name", "openai-fast")
                   
                    # Prepare the payload
                    payload = {
                        "model": model_name,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "seed": 101  # Optional but helps with reproducibility
                    }
                    
                    # Optional parameters if configured
                    if config.app.get("pollinations_private"):
                        payload["private"] = True
                    if config.app.get("pollinations_referrer"):
                        payload["referrer"] = config.app.get("pollinations_referrer")
                    
                    headers = {
                        "Content-Type": "application/json"
                    }
                    
                    # Make the API request
                    response = requests.post(
                        base_url,
                        headers=headers,
                        json=payload,
                        verify=False,
                        timeout=(10, _llm_timeout_seconds),
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    if result and "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"]
                        return content.replace("\n", "")
                    else:
                        raise Exception(f"[{llm_provider}] returned an invalid response format")
                        
                except requests.exceptions.RequestException as e:
                    raise Exception(f"[{llm_provider}] request failed: {str(e)}")
                except Exception as e:
                    raise Exception(f"[{llm_provider}] error: {str(e)}")

            if llm_provider not in ["pollinations", "ollama", "gemini"]:  # Skip validation for providers that don't require API key
                if not api_key:
                    raise ValueError(
                        f"{llm_provider}: api_key is not set, please set it in the config.toml file."
                    )
                if not model_name:
                    raise ValueError(
                        f"{llm_provider}: model_name is not set, please set it in the config.toml file."
                    )
                if not base_url:
                    raise ValueError(
                        f"{llm_provider}: base_url is not set, please set it in the config.toml file."
                    )

            if llm_provider == "qwen":
                import dashscope
                from dashscope.api_entities.dashscope_response import GenerationResponse

                dashscope.api_key = api_key
                response = dashscope.Generation.call(
                    model=model_name, messages=[{"role": "user", "content": prompt}]
                )
                if response:
                    if isinstance(response, GenerationResponse):
                        status_code = response.status_code
                        if status_code != 200:
                            raise Exception(
                                f'[{llm_provider}] returned an error response: "{response}"'
                            )

                        content = response["output"]["text"]
                        return content.replace("\n", "")
                    else:
                        raise Exception(
                            f'[{llm_provider}] returned an invalid response: "{response}"'
                        )
                else:
                    raise Exception(f"[{llm_provider}] returned an empty response")

            if llm_provider == "gemini":
                import google.generativeai as genai

                # mask API key for logs (show only last 4 chars)
                def _mask_key(key: str) -> str:
                    if not key:
                        return "<empty>"
                    if len(key) <= 8:
                        return "*" * (len(key) - 2) + key[-2:]
                    return key[:4] + "*" * (len(key) - 8) + key[-4:]

                # prepare and validate
                if not api_key:
                    logger.error("gemini: api_key is not set")
                    return ""
                if not model_name:
                    logger.error("gemini: model_name is not set")
                    return ""

                # ensure base_url is either None or root host without trailing slash
                if base_url:
                    # normalize: remove trailing slash
                    base_url = base_url.rstrip("/")

                # generation and safety configs (log these)
                generation_config = {
                    "temperature": 0.5,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 2048,
                }

                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                ]

                # Log prompt and parameters (prompt truncated to avoid huge logs)
                try:
                    prompt_preview = prompt if len(prompt) <= 1000 else prompt[:1000] + "...[truncated]"
                except Exception:
                    prompt_preview = "[unprintable prompt]"

                logger.info("gemini: calling model")
                logger.debug(f"gemini: model_name={model_name}, base_url={base_url or '<default>'}, api_key_mask={_mask_key(api_key)}")
                logger.debug(f"gemini: generation_config={generation_config}")
                logger.debug(f"gemini: safety_settings={safety_settings}")
                logger.debug(f"gemini: prompt_preview={prompt_preview}")


                # configure client (do not print secrets)
                try:
                        genai.configure(api_key=api_key)
                except Exception:
                    logger.exception("gemini: failed to configure genai client")
                    return ""

                # create model handle
                try:
                    model = genai.GenerativeModel(model_name=model_name)
                except Exception:
                    logger.exception("gemini: failed to create GenerativeModel")
                    return ""

                # call generate_content and capture detailed errors
                try:
                    response = model.generate_content(
                        prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings,
                    )
                except Exception as e:
                    # log exception and any HTTP response info if present
                    logger.exception("gemini: request failed: %s", e)
                    try:
                        resp = getattr(e, "response", None)
                        if resp is not None:
                            # some SDK exceptions expose status_code/text
                            status = getattr(resp, "status_code", None)
                            body = getattr(resp, "text", None)
                            logger.error("gemini: HTTP status=%s, body=%s", status, body)
                    except Exception:
                        logger.debug("gemini: no http response attached to exception or failed to read it")
                    return ""

                # robust extraction + logging of response shape
                generated_text = ""
                try:
                    logger.debug("gemini: raw response repr: %s", repr(response)[:2000])  # truncate long repr
                except Exception:
                    logger.debug("gemini: cannot repr response")

                try:
                    if hasattr(response, "candidates") and response.candidates:
                        candidate = response.candidates[0]
                        content = getattr(candidate, "content", None)

                        # common shape: content.parts[0].text
                        parts = getattr(content, "parts", None)
                        if parts and len(parts) > 0 and hasattr(parts[0], "text"):
                            generated_text = parts[0].text
                            logger.debug("gemini: extracted from content.parts[0].text")
                        elif isinstance(content, list) and len(content) > 0 and isinstance(content[0], str):
                            generated_text = content[0]
                            logger.debug("gemini: extracted from content list")
                        elif hasattr(content, "text"):
                            generated_text = content.text
                            logger.debug("gemini: extracted from content.text")
                        else:
                            logger.warning("gemini: candidate.content has unexpected shape: %s", type(content))
                    else:
                        logger.warning("gemini: no candidates in response or empty response object")

                    # fallback fields
                    if not generated_text:
                        if hasattr(response, "text") and response.text:
                            generated_text = response.text
                            logger.debug("gemini: extracted from response.text")
                        elif hasattr(response, "output_text") and response.output_text:
                            generated_text = response.output_text
                            logger.debug("gemini: extracted from response.output_text")

                except Exception:
                    logger.exception("gemini: error extracting text from response")
                    return ""

                if not generated_text:
                    logger.error("gemini: no text found in response object; returning empty string")
                    return ""

                # final cleanup and return
                return generated_text.replace("\n", "")


            if llm_provider == "cloudflare":
                response = requests.post(
                    f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_name}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a friendly assistant",
                            },
                            {"role": "user", "content": prompt},
                        ]
                    },
                )
                result = response.json()
                logger.info(result)
                return result["result"]["response"]

            if llm_provider == "ernie":
                response = requests.post(
                    "https://aip.baidubce.com/oauth/2.0/token", 
                    params={
                        "grant_type": "client_credentials",
                        "client_id": api_key,
                        "client_secret": secret_key,
                    }
                )
                access_token = response.json().get("access_token")
                url = f"{base_url}?access_token={access_token}"

                payload = json.dumps(
                    {
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.5,
                        "top_p": 0.8,
                        "penalty_score": 1,
                        "disable_search": False,
                        "enable_citation": False,
                        "response_format": "text",
                    }
                )
                headers = {"Content-Type": "application/json"}

                response = requests.request(
                    "POST", url, headers=headers, data=payload,
                verify=False).json()
                return response.get("result")

            if llm_provider == "azure":
                client = AzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=base_url,
                    max_retries=0,
                    timeout=_llm_timeout_seconds,
                )

            if llm_provider == "modelscope":
                content = ''
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    max_retries=0,
                    timeout=_llm_timeout_seconds,
                )
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    extra_body={"enable_thinking": False},
                    stream=True
                )
                if response:
                    for chunk in response:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            content += delta.content
                    
                    if not content.strip():
                        raise ValueError("Empty content in stream response")
                    
                    return content.replace("\n", "")
                else:
                    raise Exception(f"[{llm_provider}] returned an empty response")

            else:
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    max_retries=0,
                    timeout=_llm_timeout_seconds,
                )

            response = client.chat.completions.create(
                model=model_name, messages=[{"role": "user", "content": prompt}]
            )
            if response:
                if isinstance(response, ChatCompletion):
                    content = response.choices[0].message.content
                else:
                    raise Exception(
                        f'[{llm_provider}] returned an invalid response: "{response}", please check your network '
                        f"connection and try again."
                    )
            else:
                raise Exception(
                    f"[{llm_provider}] returned an empty response, please check your network connection and try again."
                )

        return content.replace("\n", "")
    except Exception as e:
        return f"Error: {str(e)}"


def generate_script(
    video_subject: str, language: str = "", paragraph_number: int = 1,
    video_style: str = ""
) -> str:
    # Build style-specific instructions
    style_instructions = ""
    hook_examples = ""
    if video_style:
        from app.services import style_presets
        preset = style_presets.get_preset(video_style)
        if preset:
            style_instructions = f"""
## Style & Tone:
{preset['script_tone']}
"""
            hooks = preset.get("hook_examples", [])
            if hooks:
                hook_examples = "\n".join(f"- \"{h}\"" for h in hooks)
                hook_examples = f"""
## Hook Examples (use similar style, do NOT copy verbatim):
{hook_examples}
"""

    prompt = f"""
# Role: Viral Video Script Generator

## Goals:
Generate a VIRAL short-form video script that maximizes viewer RETENTION, ENGAGEMENT and SHARES.
The script must be optimized for TikTok, Instagram Reels, and YouTube Shorts.

## Script Structure (MUST follow this exact flow):

### 1. HOOK (first 1-2 sentences) - THE most critical part
- Create an irresistible CURIOSITY GAP or EMOTIONAL TRIGGER in the first 3 seconds
- Use pattern: shocking claim, bold question, counterintuitive statement, or vivid scenario
- The viewer must feel they CANNOT scroll away
- AVOID overused templates like "they don't want you to know" or "nobody is talking about this"
- Instead use SPECIFIC hooks: reference a real brand, a real statistic, or a vivid scenario

### 2. PATTERN INTERRUPT (after hook)
- Shift tone, pace, or topic angle slightly to re-grab attention
- Example: pause, reframe, or say something unexpected

### 3. VALUE DELIVERY (3-5 short segments)
- Deliver content in SHORT, PUNCHY sentences (5-10 words MAXIMUM per sentence)
- Each point should be 1-2 sentences max
- Use SPECIFIC facts: name real brands, cite real studies, give exact numbers
- Example: "Amazon does this with lightning deals" NOT "stores do this"
- Create OPEN LOOPS: hint at what's coming next so viewers keep watching

### 4. COMMENT BAIT (near the end)
- Insert a POLARIZING statement or QUESTION that forces viewers to comment
- Make it personal: "Which one has happened to YOU?"

### 5. CTA / CLOSE
- End with a direct question that drives comments
- Keep it under 2 sentences
{style_instructions}{hook_examples}
## Hard Rules:
1. Return ONLY the raw script text - no titles, headers, labels, or formatting
2. Do NOT reference this prompt, the video format, or production details
3. Do NOT start with "welcome", "hey guys", or generic greetings
4. Do NOT use markdown, asterisks, hashtags, or bullet points
5. Do NOT include stage directions like "voiceover", "narrator", "cut to"
6. MAXIMUM 10 words per sentence - shorter is always better
7. Use conversational, SPOKEN language - write how people TALK, not write
8. Total script MUST be under 150 words (aim for 100-130 words for 60-second format)
9. Create at least one OPEN LOOP (tease what's coming)
10. Respond in the SAME language as the video subject
11. Include at least ONE specific brand name, study reference, or exact statistic
12. The script should be {paragraph_number} paragraph(s) when read naturally

# Initialization:
- video subject: {video_subject}
- number of paragraphs: {paragraph_number}
""".strip()
    if language:
        prompt += f"\n- language: {language}"

    final_script = ""
    logger.info(f"subject: {video_subject}")

    def format_response(response):
        # Clean the script
        response = response.replace("*", "")
        response = response.replace("#", "")

        # Remove markdown syntax
        response = re.sub(r"\[.*?\]", "", response)
        response = re.sub(r"\(.*?\)", "", response)

        # Split and rejoin paragraphs
        paragraphs = response.split("\n\n")
        return "\n\n".join(paragraphs)

    for i in range(_max_retries):
        try:
            response = _generate_response(prompt=prompt)
            if response:
                final_script = format_response(response)
            else:
                logging.error("gpt returned an empty response")

            # g4f may return an error message
            if final_script and "当日额度已消耗完" in final_script:
                raise ValueError(final_script)

            if final_script:
                break
        except Exception as e:
            logger.error(f"failed to generate script: {e}")

        if i < _max_retries:
            logger.warning(f"failed to generate video script, trying again... {i + 1}")
    if "Error: " in final_script:
        logger.error(f"failed to generate video script: {final_script}")
    else:
        logger.success(f"completed: \n{final_script}")
    return final_script.strip()


def generate_terms(video_subject: str, video_script: str, amount: int = 5) -> List[str]:
    prompt = f"""
# Role: Cinematic Video Search Terms Generator

## Goals:
Generate {amount} search terms for stock video footage (Pexels/Pixabay) that VISUALLY MATCH the script.

## CRITICAL Rules for Stock Footage Search:
1. Return ONLY a JSON array of strings - nothing else
2. Each term should be 1-3 SIMPLE words in English
3. Terms MUST find real results on Pexels.com - test mentally: "would this search work?"
4. Use COMMON, FILMABLE subjects: people, places, objects, actions
5. AVOID poetic/abstract terms that won't exist as stock footage
6. Each term should find DIFFERENT footage - maximize visual variety

## GOOD terms (will find footage on Pexels):
- "person scrolling phone" - common, filmable
- "crowd walking city" - common scene
- "close up eyes" - simple, exists in stock
- "office meeting" - standard stock footage
- "dark corridor" - simple, atmospheric
- "sunrise timelapse" - popular stock footage

## BAD terms (will NOT find footage on Pexels):
- "shadow figure whispering" - too specific/staged
- "brain neural network" - too abstract
- "puppet master controlling" - too conceptual
- "empty stock warning label" - too niche

## Match script mood:
- Dark/dramatic: "dark room silhouette", "rain window", "close up eyes"
- Motivational: "runner sunrise", "mountain summit", "gym workout"
- Luxury: "luxury car", "penthouse view", "gold jewelry"
- Calm: "ocean waves", "forest path", "morning coffee"

## Context:
### Video Subject
{video_subject}

### Video Script
{video_script}

Generate {amount} Pexels-friendly, visually diverse search terms.
""".strip()

    logger.info(f"subject: {video_subject}")

    search_terms = []
    response = ""
    for i in range(_max_retries):
        try:
            response = _generate_response(prompt)
            if "Error: " in response:
                logger.error(f"failed to generate video terms: {response}")
                if "quota" in response.lower() or "429" in response:
                    logger.warning("LLM quota/rate issue detected, using fallback terms")
                    return _fallback_terms(video_subject, amount)
                continue
            search_terms = json.loads(response)
            if not isinstance(search_terms, list) or not all(
                isinstance(term, str) for term in search_terms
            ):
                logger.error("response is not a list of strings.")
                continue

        except Exception as e:
            logger.warning(f"failed to generate video terms: {str(e)}")
            if response:
                match = re.search(r"\[.*]", response)
                if match:
                    try:
                        search_terms = json.loads(match.group())
                    except Exception as e:
                        logger.warning(f"failed to generate video terms: {str(e)}")
                        pass

        if search_terms and len(search_terms) > 0:
            break
        if i < _max_retries:
            logger.warning(f"failed to generate video terms, trying again... {i + 1}")

    if not search_terms:
        search_terms = _fallback_terms(video_subject, amount)
        logger.warning(f"using fallback search terms: {search_terms}")

    logger.success(f"completed: \n{search_terms}")
    return search_terms


def translate_content(text: str, target_language: str) -> str:
    """
    Translate arbitrary content to a target language.

    Falls back to the original text if translation fails.
    """
    if not text or not target_language or target_language.lower() == "en":
        return text

    prompt = (
        f"Translate the following text to {target_language}. "
        "Return only the translated text without notes:\n\n"
        f"{text}"
    )
    result = _generate_response(prompt)
    if not result or result.startswith("Error:"):
        return text
    return result.strip()

    
