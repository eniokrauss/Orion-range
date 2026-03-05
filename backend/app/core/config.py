from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../deploy/.env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Orion Range Core"
    app_version: str = "0.1.0"
    app_description: str = "Open-source Cyber Range Orchestrator (Core)"
    orion_env: str = Field(default="dev", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Application log level")
    log_format: str = Field(default="", description="Force log format: 'json' or '' (auto)")
    database_url: str = Field(default="sqlite:///./orion.db", description="Database connection URL")
    hypervisor_provider: str = Field(default="proxmox", description="Hypervisor adapter provider")

    # ── Auth ──────────────────────────────────────────────────────────────────
    api_key: str = Field(default="", description="Legacy API key for protected endpoints")
    jwt_secret: str = Field(default="", description="HS256 secret for JWT tokens.")
    jwt_secret_fallbacks: str = Field(
        default="",
        description="Comma-separated HS256 fallback secrets accepted for JWT verification.",
    )
    jwt_issuer: str = Field(default="", description="Optional expected JWT issuer (iss).")
    jwt_audience: str = Field(default="", description="Optional expected JWT audience (aud).")
    jwt_clock_skew_seconds: int = Field(
        default=30,
        ge=0,
        description="Allowed clock skew in seconds for exp/iat validation.",
    )

    # ── Proxmox connection ────────────────────────────────────────────────────
    proxmox_host: str = Field(default="", description="Proxmox host/IP")
    proxmox_port: int = Field(default=8006, description="Proxmox API port")
    proxmox_user: str = Field(default="root@pam", description="Proxmox API user")
    proxmox_token_name: str = Field(default="", description="API token name")
    proxmox_token_value: str = Field(default="", description="API token secret value")
    proxmox_verify_ssl: bool = Field(default=False, description="Verify TLS certificate")
    proxmox_node: str = Field(default="pve", description="Default Proxmox node name")

    # ── Proxmox timeouts (seconds) ────────────────────────────────────────────
    proxmox_task_poll_interval: float = Field(default=3.0)
    proxmox_task_timeout: float = Field(default=300.0)
    proxmox_provision_timeout: float = Field(default=600.0)
    proxmox_snapshot_timeout: float = Field(default=120.0)
    proxmox_reset_timeout: float = Field(default=180.0)

    # ── Resource naming ───────────────────────────────────────────────────────
    proxmox_vm_name_prefix: str = Field(default="orion")
    proxmox_storage: str = Field(default="local-lvm")
    proxmox_default_template_vmid: int = Field(default=9000)

    # ── Garbage collector ─────────────────────────────────────────────────────
    gc_interval_seconds: float = Field(
        default=0,
        description="Seconds between automatic GC runs. 0 = disabled.",
    )


settings = Settings()
