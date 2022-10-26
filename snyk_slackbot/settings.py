import yaml


class Settings:
    @staticmethod
    def from_file(file_name):
        """
        Will load settings from file
        :param file_name: the name of the setting file
        :return: an instance of the Settings class
        """
        with open(file_name, "r", encoding="UTF-8") as file:
            return Settings(yaml.safe_load(file))

    def __init__(self, config):
        self.__conf = config

    def config(self, name):
        """
        Will retrieve a setting
        :param name: the key of the setting
        :return: the setting value
        """
        return self.__conf.get(name)

    def set(self, name, value):
        """
        Setter for a setting
        :param name: name of the setting
        :param value: the value of the setting
        """
        self.__conf[name] = value
