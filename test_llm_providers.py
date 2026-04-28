"""
Test script to verify LLM provider integration.

Demonstrates that you can easily switch between:
- Google Gemini
- LM Studio
- OpenAI
- Anthropic Claude
- Ollama

Usage:
    # Test with default provider (from .env)
    python test_llm_providers.py
    
    # Test specific provider
    LLM_PROVIDER=gemini GEMINI_API_KEY=... python test_llm_providers.py
    LLM_PROVIDER=lmstudio python test_llm_providers.py
"""
import logging
from querygpt.config import config
from querygpt.factory import build_llm_provider
from querygpt.llm.base import LLMMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_llm_provider():
    """Test the configured LLM provider."""
    provider_name = config.llm.provider.upper()
    
    print("=" * 80)
    print(f"Testing LLM Provider: {provider_name}")
    print("=" * 80)
    
    # Build the LLM provider
    llm_kwargs = {}
    if config.llm.provider == "anthropic":
        llm_kwargs["api_key"] = config.llm.anthropic_api_key
        llm_kwargs["model"] = config.llm.model_anthropic
    elif config.llm.provider == "openai":
        llm_kwargs["api_key"] = config.llm.openai_api_key
        llm_kwargs["model"] = config.llm.model_openai
    elif config.llm.provider == "gemini":
        llm_kwargs["api_key"] = config.llm.gemini_api_key
        llm_kwargs["model"] = config.llm.model_gemini
    elif config.llm.provider == "lmstudio":
        llm_kwargs["model"] = config.llm.model_lmstudio
    elif config.llm.provider == "ollama":
        llm_kwargs["model"] = config.llm.model_ollama
    
    try:
        llm = build_llm_provider(config.llm.provider, **llm_kwargs)
        print(f"✅ Successfully built {provider_name} provider")
        print(f"   Model: {llm_kwargs.get('model', 'default')}")
    except Exception as e:
        print(f"❌ Failed to build {provider_name} provider:")
        print(f"   Error: {e}")
        return False
    
    # Test completion
    print(f"\n📝 Testing SQL generation...")
    messages = [
        LLMMessage(role="system", content="You are a SQL expert. Return valid JSON."),
        LLMMessage(
            role="user",
            content='Generate a simple SQL query. Return ONLY valid JSON with key "sql".'
        ),
    ]
    
    try:
        response = llm.complete(messages, response_format="json")
        print(f"✅ Received response from {provider_name}:")
        print(f"   {response[:100]}...")
    except Exception as e:
        print(f"❌ Failed to get completion from {provider_name}:")
        print(f"   Error: {e}")
        return False
    
    return True

def list_available_providers():
    """List available LLM providers."""
    print("\n" + "=" * 80)
    print("Available LLM Providers")
    print("=" * 80)
    
    providers = {
        "gemini": {
            "setup": "GEMINI_API_KEY from https://ai.google.dev/",
            "free_tier": "✅ Yes (15 req/min)",
            "offline": "❌ No",
            "quality": "⭐⭐⭐⭐⭐",
        },
        "lmstudio": {
            "setup": "Run LM Studio locally",
            "free_tier": "✅ Yes",
            "offline": "✅ Yes",
            "quality": "⭐⭐⭐",
        },
        "openai": {
            "setup": "OPENAI_API_KEY from https://platform.openai.com/",
            "free_tier": "❌ No (Paid)",
            "offline": "❌ No",
            "quality": "⭐⭐⭐⭐⭐",
        },
        "anthropic": {
            "setup": "ANTHROPIC_API_KEY from https://console.anthropic.com/",
            "free_tier": "❌ No (Paid)",
            "offline": "❌ No",
            "quality": "⭐⭐⭐⭐⭐",
        },
        "ollama": {
            "setup": "Run Ollama locally",
            "free_tier": "✅ Yes",
            "offline": "✅ Yes",
            "quality": "⭐⭐⭐",
        },
    }
    
    for provider, info in providers.items():
        print(f"\n🔹 {provider.upper()}")
        for key, value in info.items():
            print(f"   {key.replace('_', ' ').title()}: {value}")

if __name__ == "__main__":
    list_available_providers()
    
    print("\n" + "=" * 80)
    print(f"Current Configuration")
    print("=" * 80)
    print(f"LLM_PROVIDER={config.llm.provider}")
    print(f"Model={getattr(config.llm, f'model_{config.llm.provider}', 'N/A')}")
    
    print("\n")
    success = test_llm_provider()
    
    if success:
        print("\n✅ LLM Provider Test Successful!")
        print("\nYou can now use Text2Query with this provider.")
        print("To switch providers, update .env and restart the application.")
    else:
        print("\n❌ LLM Provider Test Failed!")
        print("Please check your configuration and try again.")
