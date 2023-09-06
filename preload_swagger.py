import yaml
import os

class Preload(yaml.SafeLoader):

    def __init__(self, stream):
        self._root = os.path.split(stream.name)[0]

        super(Preload, self).__init__(stream)

    def include(self, node):
        filename = os.path.join(self._root, self.construct_scalar(node))

        with open(filename, 'r') as f:
            return yaml.load(f, Preload)

Preload.add_constructor('!include', Preload.include)

with open('swagger/swagger.yml', 'r') as f:
    config_api = yaml.load(f, Preload)

# print(config_api)

# yaml.dump(config_api, open('openapi.yml', 'w'))
