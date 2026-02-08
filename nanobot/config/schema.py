"""Configuration schema using Pydantic."""

from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"


class FeishuConfig(BaseModel):
    """Feishu/Lark channel configuration using WebSocket long connection."""
    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids


class DiscordConfig(BaseModel):
    """Discord channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""
    timeout: int = 60


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory


class Config(BaseSettings):
    """Root configuration for nanobot."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def _match_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Match a provider based on model name."""
        model = (model or self.agents.defaults.model).lower()
        # Map of keywords to provider configs
        providers = {
            "openrouter": self.providers.openrouter,
            "deepseek": self.providers.deepseek,
            "anthropic": self.providers.anthropic,
            "claude": self.providers.anthropic,
            "openai": self.providers.openai,
            "gpt": self.providers.openai,
            "gemini": self.providers.gemini,
            "zhipu": self.providers.zhipu,
            "glm": self.providers.zhipu,
            "zai": self.providers.zhipu,
            "dashscope": self.providers.dashscope,
            "qwen": self.providers.dashscope,
            "groq": self.providers.groq,
            "moonshot": self.providers.moonshot,
            "kimi": self.providers.moonshot,
            "vllm": self.providers.vllm,
        }
        for keyword, provider in providers.items():
            if keyword in model and provider.api_key:
                return provider
        return None

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model (or default model). Falls back to environment variable."""
        import os
        
        model_lower = (model or self.agents.defaults.model).lower()
        
        # Map of keywords to (provider_config, env_var_name)
        provider_env_map = {
            "openrouter": (self.providers.openrouter, "OPENROUTER_API_KEY"),
            "deepseek": (self.providers.deepseek, "DEEPSEEK_API_KEY"),
            "anthropic": (self.providers.anthropic, "ANTHROPIC_API_KEY"),
            "claude": (self.providers.anthropic, "ANTHROPIC_API_KEY"),
            "openai": (self.providers.openai, "OPENAI_API_KEY"),
            "gpt": (self.providers.openai, "OPENAI_API_KEY"),
            "gemini": (self.providers.gemini, "GEMINI_API_KEY"),
            "zhipu": (self.providers.zhipu, "ZHIPU_API_KEY"),
            "glm": (self.providers.zhipu, "ZHIPU_API_KEY"),
            "zai": (self.providers.zhipu, "ZHIPU_API_KEY"),
            "dashscope": (self.providers.dashscope, "DASHSCOPE_API_KEY"),
            "qwen": (self.providers.dashscope, "DASHSCOPE_API_KEY"),
            "groq": (self.providers.groq, "GROQ_API_KEY"),
            "moonshot": (self.providers.moonshot, "MOONSHOT_API_KEY"),
            "kimi": (self.providers.moonshot, "MOONSHOT_API_KEY"),
            "vllm": (self.providers.vllm, "HOSTED_VLLM_API_KEY"),
        }
        
        # Try matching by model name first
        for keyword, (provider, env_var) in provider_env_map.items():
            if keyword in model_lower:
                # Return from config if available, otherwise from env
                if provider.api_key:
                    return provider.api_key
                return os.environ.get(env_var)
        
        # Fallback: return first available key from config or env
        fallback_order = [
            (self.providers.openrouter, "OPENROUTER_API_KEY"),
            (self.providers.deepseek, "DEEPSEEK_API_KEY"),
            (self.providers.anthropic, "ANTHROPIC_API_KEY"),
            (self.providers.openai, "OPENAI_API_KEY"),
            (self.providers.gemini, "GEMINI_API_KEY"),
            (self.providers.zhipu, "ZHIPU_API_KEY"),
            (self.providers.dashscope, "DASHSCOPE_API_KEY"),
            (self.providers.moonshot, "MOONSHOT_API_KEY"),
            (self.providers.vllm, "HOSTED_VLLM_API_KEY"),
            (self.providers.groq, "GROQ_API_KEY"),
        ]
        for provider, env_var in fallback_order:
            if provider.api_key:
                return provider.api_key
            env_key = os.environ.get(env_var)
            if env_key:
                return env_key
        return None
    
    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL based on model name."""
        model = (model or self.agents.defaults.model).lower()
        if "openrouter" in model:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        if any(k in model for k in ("zhipu", "glm", "zai")):
            return self.providers.zhipu.api_base
        if "vllm" in model:
            return self.providers.vllm.api_base
        if "deepseek" in model.lower():
            return self.providers.deepseek.api_base
        return None


    def get_search_api_key(self) -> str | None:
        """Get search API key."""
        import os
        return self.tools.web.search.api_key or os.environ.get("BRAVE_SEARCH_API_KEY")
    
    class Config:
        env_prefix = "NANOBOT_"
        env_nested_delimiter = "__"
