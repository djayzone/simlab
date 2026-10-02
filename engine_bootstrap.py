import hot_mechanics_engine
from social_engine import Engine as SocialEngine
from agent_compat import ensure_persisted_agent_rule_defaults

# Compose the social/civilization layer above climate + gameplay before the
# runtime is instantiated. The transport layer is imported only afterwards.
hot_mechanics_engine.Engine = SocialEngine

# Persist additive compatibility defaults before simulation_runtime constructs
# the Engine. This keeps startup catch-up safe for worlds created by older code.
ensure_persisted_agent_rule_defaults()

from http_server import main  # noqa: E402


if __name__ == '__main__':
    main()
