"""
Configuration management for the text-to-SQL agent.
"""
import os
from typing import Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Neo4j Configuration
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", env="NEO4J_USERNAME")
    neo4j_password: str = Field(default="password", env="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", env="NEO4J_DATABASE")
    
    # Oracle Configuration
    oracle_dsn: str = Field(default="localhost:1521/xe", env="ORACLE_DSN")
    oracle_username: str = Field(default="hr", env="ORACLE_USERNAME")
    oracle_password: str = Field(default="password", env="ORACLE_PASSWORD")
    
    # Oracle Thick Client Configuration
    oracle_use_thick_client: bool = Field(default=False, env="ORACLE_USE_THICK_CLIENT")
    oracle_lib_dir: Optional[str] = Field(default=None, env="ORACLE_LIB_DIR")
    oracle_use_kerberos: bool = Field(default=False, env="ORACLE_USE_KERBEROS")
    
    # Database Parameterization Configuration
    default_database_name: str = Field(default="oracle_main", env="DEFAULT_DATABASE_NAME")
    support_multiple_databases: bool = Field(default=True, env="SUPPORT_MULTIPLE_DATABASES")
    
    # OpenAI Configuration
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", env="OPENAI_MODEL")
    
    # FastAPI Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Query Configuration
    max_query_timeout: int = Field(default=30, env="MAX_QUERY_TIMEOUT")
    max_results_limit: int = Field(default=1000, env="MAX_RESULTS_LIMIT")
    
    # Schema Inference Configuration
    enable_fk_inference: bool = Field(default=True, env="ENABLE_FK_INFERENCE")
    fk_inference_similarity_threshold: float = Field(default=0.7, env="FK_INFERENCE_SIMILARITY_THRESHOLD")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings() 