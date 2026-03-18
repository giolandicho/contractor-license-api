from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    api_keys: str = "test-free-key"
    basic_keys: str = ""
    pro_keys: str = ""
    enterprise_keys: str = ""
    rapidapi_proxy_secret: Optional[str] = None
    port: int = 8000
    env: str = "development"
    disabled_states: str = "NY"
    cache_ttl_verify: int = 1200
    cache_ttl_search: int = 900
    redis_url: Optional[str] = None

    @property
    def api_keys_list(self) -> List[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def basic_keys_list(self) -> List[str]:
        return [k.strip() for k in self.basic_keys.split(",") if k.strip()]

    @property
    def pro_keys_list(self) -> List[str]:
        return [k.strip() for k in self.pro_keys.split(",") if k.strip()]

    @property
    def enterprise_keys_list(self) -> List[str]:
        return [k.strip() for k in self.enterprise_keys.split(",") if k.strip()]

    @property
    def all_valid_keys(self) -> List[str]:
        return (
            self.api_keys_list
            + self.basic_keys_list
            + self.pro_keys_list
            + self.enterprise_keys_list
        )

    @property
    def disabled_states_list(self) -> List[str]:
        return [s.strip().upper() for s in self.disabled_states.split(",") if s.strip()]

    model_config = {"env_file": ".env"}


settings = Settings()
