"""
Configuration settings for the ECLA AI Customer Support Agent.
Handles environment variable loading and validation.
"""

import os
from typing import Optional, List
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

class Settings:
    """
    Configuration settings class for the ECLA AI Customer Support Agent.
    Validates and provides access to all required environment variables.
    """
    
    def __init__(self):
        """Initialize settings and validate required variables."""
        self.validate_required_vars()
        self.setup_logging()
    
    # OpenAI Configuration
    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key from environment."""
        return os.getenv("OPENAI_API_KEY", "")
    
    # Database Configuration
    @property
    def database_url(self) -> str:
        """Get database URL from environment."""
        return os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/ecla_agent_db")
    
    # Chroma Configuration
    @property
    def chroma_persist_directory(self) -> str:
        """Get Chroma persistence directory from environment."""
        return os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
    
    # LangSmith Configuration
    @property
    def langsmith_api_key(self) -> Optional[str]:
        """Get LangSmith API key from environment (optional)."""
        return os.getenv("LANGSMITH_API_KEY")
    
    @property
    def langsmith_project(self) -> str:
        """Get LangSmith project name from environment."""
        return os.getenv("LANGSMITH_PROJECT", "ECLA-AI-Customer-Support-Agent")
    
    # Agent Configuration
    @property
    def agent_temperature(self) -> float:
        """Get agent temperature from environment."""
        return float(os.getenv("AGENT_TEMPERATURE", "0.1"))
    
    @property
    def agent_max_tokens(self) -> int:
        """Get agent max tokens from environment."""
        return int(os.getenv("AGENT_MAX_TOKENS", "1000"))
    
    @property
    def agent_timeout(self) -> int:
        """Get agent timeout from environment."""
        return int(os.getenv("AGENT_TIMEOUT", "30"))
    
    # API Configuration
    @property
    def api_host(self) -> str:
        """Get API host from environment."""
        return os.getenv("API_HOST", "0.0.0.0")
    
    @property
    def api_port(self) -> int:
        """Get API port from environment."""
        return int(os.getenv("API_PORT", "8000"))
    
    @property
    def api_reload(self) -> bool:
        """Get API reload setting from environment."""
        return os.getenv("API_RELOAD", "true").lower() == "true"
    
    # Security Configuration
    @property
    def secret_key(self) -> str:
        """Get secret key from environment."""
        return os.getenv("SECRET_KEY", "your-secret-key-here")
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins from environment."""
        origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,https://eclasmile.com")
        return [origin.strip() for origin in origins_str.split(",")]

    # Logging Configuration
    @property
    def log_level(self) -> str:
        """Get log level from environment."""
        return os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def log_file(self) -> str:
        """Get log file path from environment."""
        return os.getenv("LOG_FILE", "./logs/agent.log")
    
    # Infobip Configuration
    @property
    def infobip_api_key(self) -> str:
        """Get Infobip API key from environment."""
        return os.getenv("INFOBIP_API_KEY", "")

    @property
    def infobip_base_url(self) -> str:
        """Get Infobip base URL from environment."""
        return os.getenv("INFOBIP_BASE_URL", "")

    @property
    def whatsapp_sender(self) -> str:
        """Get WhatsApp sender number from environment."""
        return os.getenv("WHATSAPP_SENDER", "")

    # Environment Configuration
    @property
    def environment(self) -> str:
        """Get environment type from environment."""
        return os.getenv("ENVIRONMENT", "development")
    
    def validate_required_vars(self) -> None:
        """
        Validate that all required environment variables are set.
        Raises ValueError if any required variable is missing.
        """
        required_vars = [
            ("OPENAI_API_KEY", self.openai_api_key),
            ("DATABASE_URL", self.database_url),
            ("INFOBIP_API_KEY", self.infobip_api_key),
            ("INFOBIP_BASE_URL", self.infobip_base_url),
            ("WHATSAPP_SENDER", self.whatsapp_sender),
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value or var_value == "":
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please check your .env file or environment configuration."
            )
    
    def setup_logging(self) -> None:
        """Setup logging configuration based on environment variables."""
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

# Global settings instance
settings = Settings()

# Export commonly used settings for convenience
OPENAI_API_KEY = settings.openai_api_key
DATABASE_URL = settings.database_url
CHROMA_PERSIST_DIRECTORY = settings.chroma_persist_directory 