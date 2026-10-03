import json
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # Application
    APP_NAME: str = "SkyPulse"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Security & Auth
    SECRET_KEY: str = "skypulse-super-secret-key-change-in-production-min-32-chars"
    JWT_SECRET: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: Optional[str] = None

    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/skypulse"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Kafka / Redpanda
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"
    KAFKA_SASL_MECHANISM: str = "SCRAM-SHA-256"
    KAFKA_SASL_USERNAME: Optional[str] = None
    KAFKA_SASL_PASSWORD: Optional[str] = None
    KAFKA_SSL_CA_CERT: Optional[str] = None

    # OpenSearch
    OPENSEARCH_URL: str = "http://localhost:9200"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "skypulse-media"
    MINIO_SECURE: bool = False

    # Firebase Cloud Storage (Citizen Media & Evidence Archival)
    FIREBASE_STORAGE_ENABLED: bool = False
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_STORAGE_BUCKET: Optional[str] = None
    FIREBASE_CLIENT_EMAIL: Optional[str] = None
    FIREBASE_PRIVATE_KEY: Optional[str] = None
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    STORAGE_DEFAULT_PROVIDER: str = "AUTO"  # AUTO (Firebase if configured, else MinIO/Fallback), FIREBASE, MINIO, LOCAL
    MAX_MEDIA_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_MEDIA_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/webm",
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
    ]
    ALLOWED_MEDIA_EXTENSIONS: List[str] = [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".mp4",
        ".mov",
        ".webm",
        ".mp3",
        ".wav",
        ".ogg",
    ]

    # External APIs & Government Feeds
    WEATHERAPI_KEY: str = ""
    OPENWEATHERMAP_KEY: str = ""
    IMD_ENABLED: bool = False
    IMD_API_BASE_URL: str = ""
    IMD_API_KEY: str = ""
    IMD_POLL_INTERVAL_SECONDS: int = 300

    # data.gov.in Open Government Data Platform
    DATA_GOV_ENABLED: bool = False
    DATA_GOV_API_BASE_URL: str = "https://api.data.gov.in"
    DATA_GOV_API_KEY: str = ""
    DATA_GOV_POLL_INTERVAL_SECONDS: int = 600
    DATA_GOV_RESOURCES: str = ""

    # Social Media Weather Ingestion (SIH Step 1)
    SOCIAL_INGESTION_ENABLED: bool = True
    SOCIAL_POLL_INTERVAL_SECONDS: int = 60
    SOCIAL_HASHTAGS: str = (
        "#IMD,#Weather,#WeatherAlert,#HeavyRain,#Rainfall,#Thunderstorm,#Flood,#Heatwave,#Fog,#DustStorm,"
        "#StrongWinds,#Cyclone,#Monsoon,#IndiaWeather,#IndianWeather,#Monsoon2026,#MumbaiRain,#DelhiWeather,"
        "#OdishaWeather,#BengaluruRain,#HyderabadRain,#KolkataRain,#ChennaiRain,#FloodIndia,#HeatwaveIndia"
    )
    MASTODON_ENABLED: bool = True
    MASTODON_BASE_URL: str = "https://mastodon.social"
    MASTODON_MAX_POSTS_PER_HASHTAG: int = 20
    MASTODON_REQUEST_TIMEOUT_SECONDS: float = 10.0
    MASTODON_USER_AGENT: str = "SkyPulse-WeatherAnalytics/1.0.0 (+https://skypulse.gov.in)"

    # Search Discovery Ingestion Layer (Phase 1)
    SEARCH_DISCOVERY_ENABLED: bool = True
    SEARCH_DISCOVERY_POLL_INTERVAL_SECONDS: int = 120
    SEARCH_DISCOVERY_PROVIDER: str = "duckduckgo"  # duckduckgo, searxng, google_cse, custom
    SEARCH_DISCOVERY_MAX_RESULTS_PER_QUERY: int = 10
    SEARCH_DISCOVERY_REQUEST_TIMEOUT_SECONDS: float = 10.0
    SEARCH_DISCOVERY_USER_AGENT: str = "SkyPulse-SearchDiscovery/1.0.0 (+https://skypulse.gov.in)"
    SEARCH_DISCOVERY_LOCATIONS: str = "Mumbai,Delhi,Odisha,Assam,Bengaluru,Chennai,Kolkata,Hyderabad,Kerala,Uttarakhand,Himachal Pradesh,Gujarat,Rajasthan,Bihar,Goa"
    SEARCH_DISCOVERY_CUSTOM_QUERIES: str = ""
    SEARXNG_BASE_URL: str = ""
    GOOGLE_CSE_API_KEY: str = ""
    GOOGLE_CSE_CX: str = ""

    # News Website Ingestion Layer
    NEWS_INGESTION_ENABLED: bool = True
    NEWS_POLL_INTERVAL_SECONDS: int = 180
    NEWS_MAX_ARTICLES_PER_FEED: int = 25
    NEWS_REQUEST_TIMEOUT_SECONDS: float = 10.0
    NEWS_USER_AGENT: str = "SkyPulse-NewsWeatherIntelligence/1.0.0 (+https://skypulse.gov.in)"

    # Open Government Data (data.gov.in) Ingestion Layer
    DATA_GOV_ENABLED: bool = True
    DATA_GOV_API_KEY: Optional[str] = None
    DATA_GOV_API_BASE_URL: str = "https://api.data.gov.in"
    DATA_GOV_POLL_INTERVAL_SECONDS: int = 600
    DATA_GOV_RESOURCES: str = ""

    # IndianAPI Weather Integration Layer (Third-Party Meteorological Service)
    INDIANAPI_ENABLED: bool = True
    INDIANAPI_API_KEY: Optional[str] = None
    INDIANAPI_BASE_URL: str = "https://weather.indianapi.in"
    INDIANAPI_POLL_INTERVAL_SECONDS: int = 600
    INDIANAPI_CITIES: str = "New Delhi,Mumbai,Kolkata,Chennai,Bengaluru,Hyderabad,Bhubaneswar,Guwahati,Ahmedabad,Jaipur,Patna,Lucknow"

    # Open-Meteo Operational Weather Integration Layer (Free Non-Commercial Meteorological Service)
    OPEN_METEO_ENABLED: bool = True
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_POLL_INTERVAL_SECONDS: int = 600
    OPEN_METEO_TIMEOUT_SECONDS: float = 15.0
    OPEN_METEO_LOCATIONS: str = (
        "New Delhi:28.6139:77.2090:Delhi:New Delhi,"
        "Mumbai:19.0760:72.8777:Maharashtra:Mumbai City,"
        "Kolkata:22.5726:88.3639:West Bengal:Kolkata,"
        "Chennai:13.0827:80.2707:Tamil Nadu:Chennai,"
        "Bengaluru:12.9716:77.5946:Karnataka:Bengaluru Urban,"
        "Hyderabad:17.3850:78.4867:Telangana:Hyderabad,"
        "Bhubaneswar:20.2961:85.8245:Odisha:Khurda,"
        "Guwahati:26.1445:91.7362:Assam:Kamrup Metropolitan,"
        "Jaipur:26.9124:75.7873:Rajasthan:Jaipur,"
        "Lucknow:26.8467:80.9462:Uttar Pradesh:Lucknow,"
        "Ahmedabad:23.0225:72.5714:Gujarat:Ahmedabad,"
        "Srinagar:34.0837:74.7973:Jammu and Kashmir:Srinagar"
    )

    # Ingestion History & Persistent Cloud Telemetry
    INGESTION_HISTORY_RETENTION_DAYS: int = 90
    INGESTION_HISTORY_AUTO_CLEANUP_ENABLED: bool = False

    # AI / LLM Integration Layer
    AI_PROVIDER: str = "auto"  # auto (Groq if configured, else ML/Fallback), groq, openai, fallback
    LLM_PROVIDER: str = "disabled"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_API_KEY: str = ""

    # Groq LLM Integration (High-Speed Meteorological Reasoning)
    GROQ_ENABLED: bool = True
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_TIMEOUT_SECONDS: float = 15.0
    GROQ_MAX_RETRIES: int = 2
    GROQ_TEMPERATURE: float = 0.1
    GROQ_MAX_TOKENS: int = 1024

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CLASSIFICATION_MODEL: str = "facebook/bart-large-mnli"

    # Real AI/ML Intelligence Layer (Step 5)
    ML_ENABLED: bool = True
    ML_MODEL_DIR: str = "/app/models"
    WEATHER_CLASSIFIER_MODEL: str = "weather_event_classifier"
    WEATHER_CLASSIFIER_VERSION: str = "1.0.0"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CREDIBILITY_MODEL: str = "credibility_model"
    CREDIBILITY_MODEL_VERSION: str = "1.0.0"
    ANOMALY_MODEL: str = "anomaly_model"
    ANOMALY_MODEL_VERSION: str = "1.0.0"
    ML_CLASSIFICATION_THRESHOLD: float = 0.65
    ML_CREDIBILITY_THRESHOLD: float = 0.60
    ML_DUPLICATE_THRESHOLD: float = 0.82
    ML_ANOMALY_THRESHOLD: float = 0.70

    # Demo Mode
    DEMO_MODE: bool = True
    SYNTHETIC_STREAM_INTERVAL_SECONDS: int = 10

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    return json.loads(v_stripped)
                except Exception:
                    pass
            return [i.strip() for i in v_stripped.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def post_process_settings(self):
        # Support JWT_SECRET alias for SECRET_KEY
        if self.JWT_SECRET and not self.SECRET_KEY.startswith("skypulse-super-secret-key"):
            pass
        elif self.JWT_SECRET:
            self.SECRET_KEY = self.JWT_SECRET

        # Append FRONTEND_URL to CORS_ORIGINS if provided
        if self.FRONTEND_URL:
            origins = list(self.CORS_ORIGINS) if isinstance(self.CORS_ORIGINS, list) else []
            clean_frontend = self.FRONTEND_URL.strip().rstrip("/")
            if clean_frontend and clean_frontend not in origins:
                origins.append(clean_frontend)
            self.CORS_ORIGINS = origins

        return self


settings = Settings()

