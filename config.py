import yaml
import logging


class Config:
    def __init__(self, config):
        self.config = config

    @classmethod
    def from_file(cls, config_name="config.yaml"):
        with open(config_name) as conf_file:
            return Config(yaml.load(conf_file))

    def __str__(self):
        return "<BotConfig(discord={discord}, web={web}, db={db}, logging_level={logging_level})>".format(**self.config)

    @property
    def discord(self):
        return self.config["discord"]

    @property
    def web(self):
        return self.config["web"]

    @property
    def db(self):
        return self.config["db"]

    @property
    def logging_level(self):
        return getattr(logging, self.config["logging_level"])
