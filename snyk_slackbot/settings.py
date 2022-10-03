import yaml


class Settings:
    @staticmethod
    def from_file(file_name):
        with open(file_name, "r") as file:
            return Settings(yaml.safe_load(file))

    def __init__(self, config):
        self.__conf = config

    def config(self, name):
        return self.__conf[name]

    def set(self, name, value):
        self.__conf[name] = value
