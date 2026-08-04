class Station:
    def __init__(self, raw):
        self.name = raw ['name']

class Camera:
    def __init__(self, raw):
        self.index = raw ['index']

class Scanner:
    def __init__(self, raw):
        self.device = raw ['device']

class Storage:
    def __init__(self, raw):
        self.loc_dir = raw ['local_directory']

class sharepoint:
    def __init__(self, raw):
        self.url = raw ['drive_id']
        self.username = raw ['client_id']
        self.password = raw ['client_secret']
        self.folder = raw ['folder']
        self.enabled = raw ['enabled']

config = Config(yaml.safe_load(open('config.example.yaml')))
