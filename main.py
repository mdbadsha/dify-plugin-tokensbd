from dify_plugin import DifyPluginEnv, Plugin

# Long agent turns stream for minutes; tokens.bd's own limits apply on top.
plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=300))

if __name__ == "__main__":
    plugin.run()
